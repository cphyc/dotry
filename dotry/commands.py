
def auto_discover():
    # tm = TaskManager(data_dir=os.path.join(cwd, 'data'))
    from tests.test_1 import foo
    return


def list_tasks(args, tm):
    auto_discover()
    print('#Tasks\tUp-to-date')
    for task in tm.get_all_tasks():
        status = 'yes' if task.outputs_up_to_date else 'no'
        print('%s\t%s' % (task.name,
                          status))


def list_files(args, tm):
    auto_discover()
    print('#File\tProvider\tRequired by')
    for f, dobj in tm.get_all_data():
        manager = tm.get_task_by_data(dobj)
        dependencies = tm.get_dep_by_data(dobj)
        print('%s\t%s\t%s' % (f, manager,
                              ';'.join([str(_) for _ in dependencies])))


def generate(args, tm):
    auto_discover()
    dobjs = (tm.get_data_by_path(d) for d in args.files)

    for dobj in dobjs:
        task = tm.get_task_by_data(dobj)
        if args.verbose:
            print('Running %s' % task)
        if task.need_run:
            task()


def run(args, tm):
    tm.verbose = args.verbose
    auto_discover()
    tm.execute(tm.get_task_by_name(args.tasks))


def dependency(args, tm):
    tm.verbose = args.verbose
    auto_discover()

    tm.print_as_dot(args.output)
