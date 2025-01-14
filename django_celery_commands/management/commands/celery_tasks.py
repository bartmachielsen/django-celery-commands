import inspect
from typing import get_type_hints, get_origin, get_args
from django.core.management.base import BaseCommand, CommandError
from celery import current_app


class Command(BaseCommand):
    help = "Call Celery tasks by name, with advanced type parsing from function annotations."

    def add_arguments(self, parser):
        parser.add_argument(
            "task_name",
            nargs="?",
            default=None,
            help="Full dotted name of the Celery task to run (e.g., 'my_app.tasks.add'). "
                 "If omitted, lists all tasks in the registry."
        )
        parser.add_argument(
            "--args",
            nargs="*",
            help="Positional arguments for the task, e.g. --args 10 20",
        )
        parser.add_argument(
            "--kwargs",
            nargs="*",
            help="Keyword arguments (format key=value), e.g. --kwargs a=1 b=2",
        )

    def handle(self, *args, **options):
        task_name = options["task_name"]
        if not task_name:
            # No task name => list all tasks
            self.list_all_tasks()
            return

        # Otherwise, we attempt to run the specified task
        self.run_task(task_name, options)

    def list_all_tasks(self):
        tasks = current_app.tasks  # dict of {task_name: task_obj}
        task_names = sorted(tasks.keys())
        self.stdout.write("Celery Task Registry:\n")
        for name in task_names:
            self.stdout.write(f"  {name}")
        self.stdout.write(
            "\nUsage: python manage.py celery_tasks <task_name> "
            "[--args X Y] [--kwargs foo=bar]"
        )

    def run_task(self, task_name, options):
        tasks = current_app.tasks
        if task_name not in tasks:
            raise CommandError(f"Task '{task_name}' not found in Celery registry.")

        task = tasks[task_name]
        if not hasattr(task, "run"):
            raise CommandError(f"Task '{task_name}' has no .run method?")

        # Introspect the .run() method to get signature and type hints
        func = task.run
        signature = inspect.signature(func)
        type_hints = get_type_hints(func)  # {param_name: type, ...}

        # Parse the user-provided arguments
        positional_args_raw = options["args"] or []
        kwargs_raw = options["kwargs"] or []

        # We'll build two lists: final_args and final_kwargs
        final_args = []
        final_kwargs = {}

        # Get the parameter list in order for positional arguments
        sig_params = list(signature.parameters.values())  # e.g. [<Param "a">, <Param "b=...">, ...]
        # 1) Handle positional arguments
        for i, raw_value in enumerate(positional_args_raw):
            if i >= len(sig_params):
                # The user passed more positional args than the function expects
                final_args.append(raw_value)
                continue
            param = sig_params[i]
            param_name = param.name
            param_type = type_hints.get(param_name, None)
            cast_value = self._cast_value(raw_value, param_type)
            final_args.append(cast_value)

        # 2) Handle keyword arguments
        for raw_kv in kwargs_raw:
            if "=" not in raw_kv:
                raise CommandError("Invalid --kwargs format. Must be key=value.")
            k, v = raw_kv.split("=", 1)
            param_type = type_hints.get(k, None)
            cast_value = self._cast_value(v, param_type)
            final_kwargs[k] = cast_value

        # Fire the task asynchronously
        result = task.delay(*final_args, **final_kwargs)
        self.stdout.write(
            self.style.SUCCESS(
                f"Task '{task_name}' called. Task ID: {result.id}"
            )
        )

    def _cast_value(self, value: str, annotation):
        """
        Attempt to cast the string 'value' to the Python type given by 'annotation'.
        If no annotation is provided, or if casting fails, we just return the original string
        (or raise an error if that is appropriate).
        """
        if annotation is None:
            # No type hint => treat as raw string
            return value

        # e.g. annotation could be int, bool, float, str, or something more complex
        origin = get_origin(annotation)  # e.g. list, Union, etc.
        args = get_args(annotation)      # e.g. (int,) if it's List[int]

        # Basic built-ins
        if annotation == str:
            return value
        elif annotation == int:
            try:
                return int(value)
            except ValueError as e:
                raise CommandError(f"Cannot cast '{value}' to int: {e}")
        elif annotation == float:
            try:
                return float(value)
            except ValueError as e:
                raise CommandError(f"Cannot cast '{value}' to float: {e}")
        elif annotation == bool:
            # Accept common variants for boolean
            lower_val = value.lower()
            if lower_val in ["true", "1", "yes"]:
                return True
            elif lower_val in ["false", "0", "no"]:
                return False
            else:
                raise CommandError(f"Cannot cast '{value}' to bool (expected true/false/1/0).")

        # Example for a List[...] type
        if origin == list and args:
            # We'll assume a comma-separated list for this example, e.g. "1,2,3"
            inner_type = args[0]  # e.g. int if annotation is List[int]
            items = value.split(",")

            casted_items = []
            for item in items:
                casted_items.append(self._cast_value(item.strip(), inner_type))
            return casted_items

        # If we get here, it's a more complex type we haven't explicitly handled
        # or a generic "list" with no sub-type. Return the string or raise an error.
        # For advanced usage, consider using pydantic or your own logic for e.g. Union, Dict, etc.
        return value
