"""The demo's settings, plus the apps and templates only the tests use."""

import tempfile
from pathlib import Path

from example.settings import *  # noqa: F403
from example.settings import INSTALLED_APPS, TEMPLATES

# The foreign key links' test models (Author, Book).
INSTALLED_APPS = [*INSTALLED_APPS, "tests.core"]

TEMPLATES[0]["DIRS"] = [Path(__file__).parent / "templates"]

# A file, not in memory: the end-to-end tests' server answers from several
# threads, and an in-memory database is one connection they'd all share
# (closing it as the server stops, a request's thread would fail).
_DB = str(Path(tempfile.mkdtemp(prefix="django-admin-tables-")) / "test.sqlite3")
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _DB,
        "TEST": {"NAME": _DB},
    }
}
