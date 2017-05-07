import importlib
import os
from glob import glob


def auto_discover():
    cwd = os.getcwd()

    paths = os.path.join(cwd, '**', '*.py')

    # Find all files
    all_files = glob(paths)

    for path in all_files:
        # TODO: fails on Windows
        path = os.path.relpath(path).replace('.py', '').split('/')
        module = '.'.join(path)

        # print('Importing module', module)
        importlib.import_module(module)

    return


def list_tasks(args, tm):
    tm.verbose = args.verbose
    auto_discover()

    print('#Tasks\tUp-to-date')
    for task in tm.get_all_tasks():
        status = 'yes' if task.outputs_up_to_date else 'no'
        print('%s\t%s' % (task.name,
                          status))


def list_files(args, tm):
    tm.verbose = args.verbose
    auto_discover()

    file_list = []
    provider_list = []
    dep_list = []

    for f, dobj in tm.get_all_data():
        manager = tm.get_task_by_data(dobj)
        dependencies = tm.get_dep_by_data(dobj)
        file_list.append(str(f))
        provider_list.append(str(manager))
        dep_list.append('; '.join([str(_) for _ in dependencies]))

    def format_to_width(s, l):
        spaces = l - len(s)
        return s + ' '*spaces

    maxwf = max((len(f) for f in file_list))
    maxwp = max((len(f) for f in provider_list))

    print('%s\t%s\t%s' % (format_to_width('# File', maxwf),
                      format_to_width('Provider', maxwp),
                      'Dependencies'))

    for fs, ps, ds in zip(file_list, provider_list, dep_list):
        print('%s\t%s\t%s' % (format_to_width(fs, maxwf),
                          format_to_width(ps, maxwp),
                          ds))


def generate(args, tm):
    tm.verbose = args.verbose
    auto_discover()
    dobjs = (tm.get_data_by_path(d) for d in args.files)

    tasks = [tm.get_task_by_data(dobj) for dobj in dobjs]

    tm.execute(tasks)


def run(args, tm):
    tm.verbose = args.verbose
    auto_discover()
    tm.execute(tm.get_task_by_name(args.tasks))


def dependency(args, tm):
    tm.verbose = args.verbose
    auto_discover()

    print('calling print as dot method')
    tm.print_as_dot(args.output)
