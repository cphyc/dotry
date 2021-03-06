import inspect
import hashlib
import re
import networkx as nx
from datetime import datetime
import os
from functools import wraps
import matplotlib as mpl
from .commands import list_tasks, list_files, generate, run, dependency
import pickle


mpl.use('agg')
import matplotlib.pyplot as plt


STATE_FILE = 'state.pickle'


def find_dotry_path():
    def check_path(path):
        dotrypath = os.path.join(path, '.dotry')
        if os.path.isdir(dotrypath):
            return dotrypath
        else:
            return None

    path = os.getcwd()
    dotrypath = check_path(path)
    if dotrypath:
        return dotrypath

    while path != '/':
        path, tail = os.path.split(path)
        dotrypath = check_path(path)
        if dotrypath:
            return dotrypath

    raise Exception('Could not find a dotry path.')


DOTRY_PATH = find_dotry_path()
TASK_MANAGER = None


def load_state():
    path = os.path.join(DOTRY_PATH, STATE_FILE)
    with open(path, 'br') as f:
        tm = pickle.load(f)

    return tm


def get_task_manager():
    global TASK_MANAGER
    if TASK_MANAGER is not None:
        return TASK_MANAGER

    TASK_MANAGER = TaskManager()

    return TASK_MANAGER


def dummyfun():
    raise Exception('Not specified')

origin_time = datetime.fromtimestamp(0)

class Task:
    '''Represent a task'''
    def __init__(self, name, desc=None,
                 provides=[], requires=[], timestamp=None, **kwa):
        self.name = name
        self.desc = desc
        self.provides = provides
        self.requires = requires
        self.fun = dummyfun
        self.original_fun = dummyfun
        self.creation_time = datetime.now()
        self.call_time = origin_time
        self.hash = None

        for key in kwa:
            if hasattr(self, key):
                setattr(self, key, kwa[key])

    def __repr__(self):
        status = 'R' if self.has_run else ' '
        status += 'U' if self.outputs_up_to_date else ' '
        s = 'Task: %s (%s)' % (self.name, status)
        return s

    @property
    def state(self):
        '''Return a dictionary objet that can be used to instantiate another
        Task object with the same caracteristic (only missing the
        fun/original_fun).
        '''
        return dict(name=self.name,
                    desc=self.desc,
                    creation_time=self.creation_time,
                    call_time=self.call_time,
                    hash=self.hash)

    @property
    def outputs_up_to_date(self):
        '''True if all outputs are up-to-date with the inputs (does not check
        that the inputs file exist), which means they have been generated
        later than the inputs and after the last function call.
        '''
        latest_input = datetime.fromtimestamp(
            max([inp.mtime
                 for inp in self.requires if inp.exists],
                default=0))

        first_output = datetime.fromtimestamp(
            min([out.mtime
                 for out in self.provides if out.exists],
                default=self.call_time.timestamp()))
        flag = all((dt.exists for dt in self.provides))
        flag &= (latest_input <= self.call_time)
        flag &= (self.call_time <= first_output)
        return flag

    @property
    def need_run(self):
        '''True if the task need to be run, which is True whenever it has
        never been run or the output(s) are not up to date with the
        input(s).

        '''
        dont_need_run = self.has_run and self.outputs_up_to_date
        return not dont_need_run

    @property
    def has_run(self):
        return self.call_time > origin_time

    def call_original_fun(self, *args, **kwargs):
        # Important: set the call time *before* calling the function
        self.call_time = datetime.now()
        ret = self.original_fun(*args, **kwargs)
        return ret

    def __call__(self, *args, **kwargs):
        # Important: set the call time *before* calling the function
        self.call_time = datetime.now()
        ret = self.fun(*args, **kwargs)
        return ret

    def reset_time(self):
        self.call_time = origin_time
        self.creation_time = datetime.now()


class Data:
    '''Representation of an object.

    '''
    def __init__(self, datafile):
        self.datafile = datafile
        self.desc = 'Data: %s' % datafile

    @property
    def mtime(self):
        '''The modification time of the datafile.'''
        return os.path.getmtime(self.datafile)

    @property
    def exists(self):
        '''True if the file exists'''
        return os.path.isfile(self.datafile)

    def __repr__(self):
        return self.desc


DOUT_RE = '%s\.dout\([\'"]{1,3}([^\'"]+)[\'"]{1,3}\)'
DIN_RE = '%s\.din\([\'"]{1,3}([^\'"]+)[\'"]{1,3}\)'


class NotRegisteredError(Exception):
    pass


class TaskManager:
    '''A class to handle dependencies between python functions.'''

    def __init__(self, data_dir='data'):
        self.tasks = set()
        self.graph = nx.DiGraph()
        self._data_to_task = dict()
        self._data_to_dep = dict()
        self._path_to_data = dict()
        self.data_dir = os.path.join(os.getcwd(), data_dir)
        if not os.path.isdir(self.data_dir):
            os.mkdir(self.data_dir)

        self.verbose = False
        self.load_state()

    def dump_state(self):
        '''Basically dumps the hash of the files'''
        state = {t.name: t.state for t in self.tasks}
        path = os.path.join(DOTRY_PATH, STATE_FILE)

        if not os.path.isdir(DOTRY_PATH):
            os.mkdir(DOTRY_PATH)

        with open(path, 'wb') as f:
            pickle.dump(state, f)

    def load_state(self):
        path = os.path.join(DOTRY_PATH, STATE_FILE)
        if os.path.isfile(path):
            with open(path, 'br') as f:
                state = pickle.load(f)

            for k in state:
                newTask = Task(**state[k])
                self.tasks.add(newTask)
                self.graph.add_node(newTask.name, task=newTask)

    def get_or_register_data(self, raw_datafile):
        '''Get or create the Data object for a given filename'''
        try:
            return self.get_data_by_path(raw_datafile)
        except NotRegisteredError:
            datafile = os.path.join(self.data_dir, raw_datafile)
            data_obj = Data(datafile)
            self.set_data_by_path(raw_datafile, data_obj)
            return data_obj

    def get_task_by_data(self, data_obj):
        if not isinstance(data_obj, Data):
            raise TypeError('«%s» is not of type Data' % data_obj)

        if data_obj in self._data_to_task:
            return self._data_to_task[data_obj]
        else:
            raise NotRegisteredError('«%s» is not managed.' % data_obj)

    def get_dep_by_data(self, data_obj):
        if not isinstance(data_obj, Data):
            raise TypeError('«%s» is not of type Data' % data_obj)

        if data_obj in self._data_to_dep:
            return self._data_to_dep[data_obj]
        else:
            return []

    def set_task_by_data(self, data_obj, task_obj):
        self._data_to_task[data_obj] = task_obj

    def set_dep_by_data(self, data_obj, task_obj):
        if data_obj in self._data_to_dep:
            prev = self._data_to_dep[data_obj]
        else:
            self._data_to_dep[data_obj] = prev = set()

        prev.add(task_obj)

    def get_data_by_path(self, fname):
        if fname in self._path_to_data:
            return self._path_to_data[fname]
        else:
            raise NotRegisteredError('«%s» is not managed.' % fname)

    def set_data_by_path(self, fname, data_obj):
        if not isinstance(data_obj, Data):
            raise TypeError('«%s» is not of type Data' % data_obj)

        self._path_to_data[fname] = data_obj

    def get_all_data(self):
        '''Yields tuple of data file name, data file object'''
        for fname in self._path_to_data:
            yield fname, self.get_data_by_path(fname)

    def get_all_tasks(self):
        for task in self.tasks:
            yield task

    def register(self, fun):
        '''Register a function in the task manager. The task manager
        ensures that all the calls of the function are made with
        the inputs file up-to-date. If not, it calls other registered functions
        that can provide it.

        Note:
        The detection of the inputs/outputs is done by finding all
        lines calling `tm.din` (inputs) and `tm.dout` (outputs), where
        `tm` is an instance of task manager. For now, only pure string
        arguments are supported. This is due to the fact that the
        dependency checking process is static.

        Example:
        tm = TaskManager()
        @tm.register
        def foo():
            input_file = open(tm.din('inputs.dat'), 'r')
            # do something with the input_file, store it in output
            with open(tm.dout('outputs.dat'), 'w') as f:
                f.write(output)

        '''
        desc = inspect.getdoc(fun)
        src = inspect.getsource(fun)
        first_line = inspect.getsourcelines(fun)[0][0]
        hsh = hashlib.sha256(src.encode('utf-8')).hexdigest()
        fun_name = fun.__name__

        prefix = re.match('@(\w+)\.register', first_line).groups()[0]
        if self.verbose:
            print('Found function «%s» with prefix «%s»' % (fun_name, prefix))
            if desc is not None:
                pre = '\tdesc:'
                print(pre, end='')
                print(desc.replace('\n', '\n\t' + ' '*(len(pre)-2) + '|' + ' '))

        data_in = [self.get_or_register_data(dt)
                   for dt in set(re.findall(DIN_RE % prefix, src))]
        data_out = [self.get_or_register_data(dt)
                    for dt in set(re.findall(DOUT_RE % prefix, src))]

        if self.verbose:
            print('\tdata input: %s\n\tdata output:%s' % (data_in, data_out))

        def set_task(task):
            task.hash = hsh
            task.src = src
            task.desc = desc
            task.original_fun = fun

            task.requires = data_in
            task.provides = data_out

            for d in data_out:
                self.set_task_by_data(d, task)
            for d in data_in:
                self.set_dep_by_data(d, task)

            self.tasks.add(task)

        if fun_name in self.graph:
            task = self.graph.node[fun_name]['task']
            if task.hash != hsh:
                if self.verbose:
                    print('W: overriding %s' % fun_name)

                set_task(task)
                task.reset_time()
            else:
                if self.verbose:
                    print('W: same redefinition of %s' % fun_name)
                set_task(task)
        else:
            task = Task(fun_name, desc, requires=data_in, provides=data_out)
            set_task(task)

        # self.tasks[fun_name] = task

        # Add current node to the graph
        if task.name in self.graph:
            self.graph.remove_node(task.name)
        self.graph.add_node(task.name, task=task)

        # Add edges to parent tasks
        for din in data_in:
            provider_task = self.get_task_by_data(din)

            self.graph.add_edge(provider_task.name, task.name)

        @wraps(fun)
        def wrap(*args, **kwargs):
            self.execute(task, *args, **kwargs)

        task.fun = wrap
        return wrap

    def execute(self, tasks, *args, **kwargs):
        ret = None

        reversed_graph = self.graph.reverse()

        if not isinstance(tasks, (tuple, list)):
            tasks = [tasks]
        g = nx.ego_graph(reversed_graph, tasks[0].name, radius=100)

        for t in tasks[1:]:
            g = nx.compose(g, nx.ego_graph(reversed_graph, t.name,
                                           radius=100))

        node_order = nx.topological_sort(g, reverse=True)
        for node in node_order:
            task_obj = self.graph.node[node]['task']
            if task_obj.need_run:
                # or task_obj.name in [t.name for t in tasks]:
                print('Calling «%s»' % task_obj)

                # Execute the task
                ret = task_obj.call_original_fun()

        return ret

    def din(self, fname):
        '''Use this function to access the full path of an input data file.'''
        return self.dany(fname)

    def dout(self, fname):
        '''Use this function to access the full path of an output data file.'''
        return self.dany(fname)

    def dany(self, fname):
        '''Use this function to access the full path of an any data file.'''
        data_obj = self.get_data_by_path(fname)
        return data_obj.datafile

    def __repr__(self):
        arr = []
        for node in self.graph.nodes():
            task = self.graph.node[node]['task']
            arr.append('%s, %s, %s' %
                       (task.name,
                        'has_run' if task.has_run else 'need to run',
                        'files up to date' if task.outputs_up_to_date
                        else 'files not up to date'))
        return '\n'.join(arr)

    def __getitem__(self, tnames):
        return [t for t in self.tasks if t.name in tnames]

    def get_task_by_name(self, tnames):
        ret = [t for t in self.tasks if t.name in tnames]
        if not len(tnames) == len(ret):
            raise Exception("Could't find matching task for names", tnames)

        return ret

    def print_as_dot(self, fname):
        g = self.graph

        layout = nx.spring_layout(g)
        nx.draw(g, pos=layout)
        nx.draw_networkx_labels(g, pos=layout)
        plt.savefig(fname)


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description='')
    parser.set_defaults(cb=lambda *args: parser.print_help())
    sp = parser.add_subparsers()

    list_files_parser = sp.add_parser('list-files',
                                      help='List the files managed.')
    list_files_parser.add_argument('-v', '--verbose', action='store_true')
    list_files_parser.set_defaults(cb=list_files)

    list_tasks_parser = sp.add_parser('list-tasks',
                                      help='List the tasks managed.')
    list_tasks_parser.add_argument('-v', '--verbose', action='store_true')
    list_tasks_parser.set_defaults(cb=list_tasks)

    generate_parser = sp.add_parser('generate', help='Generate files.')
    generate_parser.add_argument('files', nargs='+', help='Generate file.')
    generate_parser.add_argument('-v', '--verbose', action='store_true')
    generate_parser.set_defaults(cb=generate)

    run_parser = sp.add_parser('run', help='Run a given task.')
    run_parser.add_argument('tasks', nargs='+', help='Run task.')
    run_parser.add_argument('-v', '--verbose', action='store_true')
    run_parser.set_defaults(cb=run)

    dep_parser = sp.add_parser('dependency', help='Print a dependency tree.')
    dep_parser.add_argument('output',
                            help='Destination of the graph representation.')
    dep_parser.add_argument('-v', '--verbose', action='store_true')
    dep_parser.set_defaults(cb=dependency)

    return parser.parse_args()


def main():
    args = parse_args()
    tm = get_task_manager()

    try:
        args.cb(args, tm)
    finally:
        tm.dump_state()
