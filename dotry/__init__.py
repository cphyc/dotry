from .main import Task, Data, TaskManager, auto_discover

__all__ = [Task, Data, TaskManager, auto_discover]


if __name__ == '__main__':
    tm = auto_discover()
