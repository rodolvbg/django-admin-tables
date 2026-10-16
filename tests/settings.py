"""The demo's settings, plus the apps and templates only the tests use."""

from pathlib import Path

from example.settings import *  # noqa: F403
from example.settings import INSTALLED_APPS, TEMPLATES

# The foreign key links' test models (Author, Book).
INSTALLED_APPS = [*INSTALLED_APPS, "tests.core"]

TEMPLATES[0]["DIRS"] = [Path(__file__).parent / "templates"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
