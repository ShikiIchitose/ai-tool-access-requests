from .settings import *  # noqa: F403

STORAGES["staticfiles"] = {  # noqa: F405
    "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
}

WHITENOISE_AUTOREFRESH = True
