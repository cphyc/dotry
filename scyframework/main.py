import inspect
import hashlib
import re
import networkx as nx
import time
import os
from functools import wraps


class Task:
    '''Represent a task'''
    def __init__(self, name, desc, provides, requires):
        self.name = name
        self.desc = desc
        self.provides = provides
        self.requires = requires
        self.has_run = False

    def __repr__(self):
        status = 'R' if self.has_run else ' '
        status += 'U' if self.outputs_up_to_date else ' '
        s = 'Task: %s (%s)' % (self.name, status)
        return s

    @property
    def outputs_up_to_date(self):
        '''True if all outputs are up-to-date with the inputs (does not check
        that the inputs file exist), which means they are younger.

        '''
        latest_input = max([inp.mtime
                            for inp in self.requires if inp.exists],
                           default=0)

        first_output = min([out.mtime
                            for out in self.provides if out.exists],
                           default=time.time())
        flag = all((dt.exists for dt in self.provides))
        flag = flag and (latest_input < first_output)
        return flag

    @property
    def need_run(self):
        '''True if the task need to be run, which is True whenever it has
        never been run or the output(s) are not up to date with the
        input(s).

        '''
        dont_need_run = self.has_run and self.outputs_up_to_date
        return not dont_need_run

    def __call__(self):
        ret = self.fun()
        # Mark as runned and out file up to date
        # print('setting %s.has_run = True' % self)
        self.has_run = True
        return ret


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

    def __init__(self, data_dir='./data'):
        self.tasks = dict()
        self.graph = nx.DiGraph()
        self._data_to_task = dict()
        self._path_to_data = dict()
        self.data_dir = os.path.join(os.getcwd(), data_dir)
        if not os.path.isdir(self.data_dir):
            os.mkdir(self.data_dir)

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

    def set_task_by_data(self, data_obj, task_obj):
        self._data_to_task[data_obj] = task_obj

    def get_data_by_path(self, fname):
        if fname in self._path_to_data:
            return self._path_to_data[fname]
        else:
            raise NotRegisteredError('«%s» is not managed.' % fname)

    def set_data_by_path(self, fname, data_obj):
        if not isinstance(data_obj, Data):
            raise TypeError('«%s» is not of type Data' % data_obj)

        self._path_to_data[fname] = data_obj

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
        print(prefix, src)
        data_in = [self.get_or_register_data(dt)
                   for dt in set(re.findall(DIN_RE % prefix, src))]
        data_out = [self.get_or_register_data(dt)
                    for dt in set(re.findall(DOUT_RE % prefix, src))]

        print(data_in, data_out)

        def set_task(task):
            task.hash = hsh
            task.src = src
            task.desc = desc
            task.fun = fun
            # Invalidate data provided
            for d in data_out:
                self.set_task_by_data(d, task)

        if fun_name in self.graph:
            task = self.graph.node[fun_name]['task']
            if task.hash != hsh:
                print('W: overriding %s' % fun_name)
                set_task(task)
            else:
                print('W: same redefinition of %s' % fun_name)
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

            # print('Linking %s to %s' % (task.name, provider_task.name))
            self.graph.add_edge(provider_task.name, task.name)

        @wraps(fun)
        def wrap(*args, **kwargs):
            ret = None
            # Build dep tree
            g = nx.ego_graph(self.graph.reverse(), task.name, radius=100)
            node_order = nx.topological_sort(g, reverse=True)
            # print('order: ', node_order)
            for node in node_order:
                task_obj = self.graph.node[node]['task']
                if task_obj.need_run or task_obj.name == task.name:
                    print('Calling «%s»' % task_obj)
                    ret = task_obj()

                    # Mark the children to run them
                    for child in self.graph.neighbors(node):
                        self.graph.node[child]['task'].has_run = False

            return ret

        return wrap

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
