from celery import current_app
import inspect
from typing import get_type_hints


def get_celery_tasks():
    """
    Return a dict of {task_name: task_object} for all registered Celery tasks.
    Example of task_name: 'my_app.tasks.add'
    """
    return dict(current_app.tasks)


def parse_task_signature(task_object):
    """
    Introspect the underlying .run function:
      - Parameter names, defaults, type hints
      - Docstring for help text
    """
    func = task_object.run
    signature = inspect.signature(func)
    type_hints = get_type_hints(func)
    docstring = inspect.getdoc(func) or ''

    params_info = []
    for param_name, param in signature.parameters.items():
        annotation = type_hints.get(param_name, None)
        default = param.default if param.default is not inspect._empty else None
        required = (param.default == inspect._empty)  # True if no default

        params_info.append({
            'name': param_name,
            'annotation': annotation,
            'default': default,
            'required': required,
        })

    return {
        'name': task_object.name,         # e.g. 'my_app.tasks.add'
        'func_name': func.__name__,       # e.g. 'add'
        'params': params_info,
        'docstring': docstring,
    }
