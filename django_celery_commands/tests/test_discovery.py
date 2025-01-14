from django.test import TestCase
from unittest.mock import patch
from django_celery_commands.discover import get_celery_tasks, parse_task_signature

class TestDiscover(TestCase):
    @patch("django_celery_commands.discover.current_app")
    def test_get_celery_tasks(self, mock_app):
        mock_app.tasks = {
            "my_app.tasks.test_task": "fake_task_object"
        }
        tasks = get_celery_tasks()
        self.assertIn("my_app.tasks.test_task", tasks)
        self.assertEqual(tasks["my_app.tasks.test_task"], "fake_task_object")

    def test_parse_task_signature(self):
        # We'll define a sample function to mimic a Celery task
        def sample_run(a: int, b: int = 3):
            """Sample docstring."""
            return a + b

        # We can wrap it in a "fake" Celery task object:
        class FakeTask:
            name = "my_app.tasks.sample_run"
            run = sample_run

        fake_task = FakeTask()
        info = parse_task_signature(fake_task)

        self.assertEqual(info["name"], "my_app.tasks.sample_run")
        self.assertEqual(info["func_name"], "sample_run")
        self.assertEqual(info["docstring"], "Sample docstring.")
        self.assertEqual(len(info["params"]), 2)
