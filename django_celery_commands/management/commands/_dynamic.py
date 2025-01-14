from django.core.management.base import BaseCommand, CommandError
from django.core.management import _commands  # Internal registry: {command_name: (app_name, cmd_name)}
import re


def _slugify_command_name(name: str) -> str:
    """
    Make sure the command name is a valid identifier for Django management.
    For example: 'my_app.tasks.add' -> 'my_app_tasks_add'
    or simply use the function name if you want it shorter, e.g. 'add'.
    """
    return re.sub(r'\W+', '_', name)


def register_command(command_name, task_info, task_obj):
    """
    Dynamically create a Django management command class, inject it into
    Django's command registry so that `python manage.py command_name` works.
    """
    class DynamicCeleryCommand(BaseCommand):
        help = task_info['docstring'] or "No description available."

        def add_arguments(self, parser):
            for param in task_info['params']:
                arg_name = f"--{param['name']}"
                help_text = f"Type: {param['annotation']} | Default: {param['default']}"
                parser.add_argument(
                    arg_name,
                    required=param['required'],
                    default=param['default'],
                    help=help_text,
                )

        def handle(self, *args, **options):
            # Convert (string) options into typed arguments based on the annotation
            final_kwargs = {}
            for param in task_info['params']:
                p_name = param['name']
                p_type = param['annotation']
                val = options.get(p_name, None)

                # If there's a type annotation, try casting
                if val is not None and p_type is not None:
                    try:
                        # If it's a builtin type (int, float, bool, str, etc.)
                        # For more complex types (List[int], etc.), you'd need more logic
                        val = p_type(val)
                    except Exception as e:
                        raise CommandError(
                            f"Could not cast argument {p_name}='{val}' to {p_type}: {e}"
                        )

                final_kwargs[p_name] = val

            # Call the Celery task asynchronously
            result = task_obj.delay(**final_kwargs)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Called task '{task_info['name']}' with id: {result.id}"
                )
            )

    # Finalize the command class name & register
    dynamic_name = _slugify_command_name(command_name)
    DynamicCeleryCommand.__name__ = f"Command_{dynamic_name}"

    # Inject into Django's command registry
    _commands[dynamic_name] = (
        'django_celery_commands.management.commands._dynamic',
        dynamic_name
    )

    # Also place it in our module's globals so Django can `load_command_class`
    globals()[dynamic_name] = DynamicCeleryCommand
