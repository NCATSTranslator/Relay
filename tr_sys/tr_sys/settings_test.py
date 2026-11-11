"""Settings for the unit tests: the normal settings with an in-memory SQLite database.

The unit tests need a database but nothing MySQL-specific, so this lets them
run anywhere with no services. pytest.ini selects this module by default; to
run against MySQL instead, pass --ds=tr_sys.settings.
"""
from .settings import *

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}
