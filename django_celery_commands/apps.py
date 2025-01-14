from django.apps import AppConfig

class DjangoCeleryCommandsConfig(AppConfig):
    name = 'django_celery_commands'
    verbose_name = 'Django Celery Commands'

    def ready(self):
        # This method runs once Django finishes initializing.
        from django_celery_commands.discover import get_celery_tasks, parse_task_signature
        from django_celery_commands.management.commands._dynamic import register_command

        # Discover all Celery tasks
        tasks = get_celery_tasks()

        # For each task, parse its signature and register a separate Django command
        for task_name, task_obj in tasks.items():
            # e.g. task_name='my_app.tasks.add'
            task_info = parse_task_signature(task_obj)

            # Create a command name from the last part of the path or something unique
            # e.g. 'add' from 'my_app.tasks.add'
            command_name = task_info['func_name']  # or any slug you prefer

            # Register the command dynamically
            register_command(command_name, task_info, task_obj)
