
import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "setup.settings")

app = Celery(
    "setup",
    include=["core.tasks"],
)

app.config_from_object("django.conf:settings", namespace="CELERY")

# Discover tasks lazily, after Django's app registry is ready.
app.autodiscover_tasks()
