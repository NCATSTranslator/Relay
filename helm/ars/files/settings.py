"""
Django settings for tr_sys, as deployed by the helm/ars chart.

This file is mounted over tr_sys/tr_sys/settings.py (same mechanism as the
production deploy/ chart) but takes every connection parameter and credential
from environment variables, which the chart supplies from values.yaml and its
Secret. It should track tr_sys/tr_sys/settings.py apart from those env reads.
"""

import os
from .otel_config import configure_opentelemetry

configure_opentelemetry()

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'ars-dev-insecure-secret-key')

DEBUG = os.environ.get('DJANGO_DEBUG', 'true').lower() in ('1', 'true', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',') if h.strip()]

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
#    'channels',
    'tr_ars.apps.ARSConfig',
    'tr_ara_aragorn.aragorn_app.AppConfig',
    'tr_ara_arax.arax_app.AppConfig',
    'tr_ara_bte.bte_app.AppConfig',
    'tr_ara_improving.improving_app.AppConfig',
    'tr_ara_unsecret.unsecret_app.AppConfig',
    'tr_ara_wfr.wfr_app.AppConfig',
    'tr_ara_cqs.cqs_app.AppConfig',
    'tr_ara_shepherd_aragorn.shepherd_aragorn_app.AppConfig',
    'tr_ara_shepherd_arax.shepherd_arax_app.AppConfig',
    'tr_ara_shepherd_bte.shepherd_bte_app.AppConfig',
    'tr_kp_genetics.genetics_app.AppConfig',
    'tr_kp_clinical.clinical_app.AppConfig',
    'tr_kp_drug.drug_app.AppConfig',
    'tr_kp_molecular.molecular_app.AppConfig',
    'tr_kp_cam.cam_app.AppConfig',
    'tr_kp_textmining.textmining_app.AppConfig',
    'tr_kp_openpredict.openpredict_app.AppConfig',
    'tr_kp_cohd.cohd_app.AppConfig',
    'tr_kp_chp.chp_app.AppConfig',
    'django_celery_results',
    'markdownify',
    'django_celery_beat',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tr_sys.urls'

CORS_ORIGIN_ALLOW_ALL = True # for further customization see https://pypi.org/project/django-cors-headers/

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'tr_ars','templates')],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'tr_sys.wsgi.application'
# Channels
ASGI_APPLICATION = 'tr_sys.routing.application'

CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            "hosts": [(os.environ.get('ARS_REDIS_HOST', '127.0.0.1'), 6379)],
        },
    },
}

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': os.environ.get('ARS_DB_NAME', 'arsdb'),
        'USER': os.environ.get('ARS_DB_USER', 'ars'),
        'PASSWORD': os.environ.get('ARS_DB_PASSWORD', ''),
        'HOST': os.environ.get('ARS_DB_HOST', 'localhost'),
        'PORT': os.environ.get('ARS_DB_PORT', '3306'),
    }
}

DJANGO_LOG_LEVEL = os.environ.get('DJANGO_LOG_LEVEL', 'DEBUG')
LOGGING = {
    'formatters': {
        'simple': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        }
    },
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        }
    },
    'root': {
        'handlers': ['console'],
        'level': DJANGO_LOG_LEVEL,
    },
    'loggers': {
        'tr_ars.tasks': {
            'level': DJANGO_LOG_LEVEL,
            'handlers': ['console'],
        },
        'tr_ars.default_ars_app.api': {
            'level': DJANGO_LOG_LEVEL,
            'handlers': ['console']
        }
    }
}

# Password validation
# https://docs.djangoproject.com/en/1.11/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/1.11/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# markdowninfy

MARKDOWNIFY_STRIP = False
MARKDOWNIFY_WHITELIST_TAGS = {
    'a', 'p',
    'h1', 'h2', 'h3','h4', 'h5', 'h6', 'h7',
    'ul', 'li', 'span',
}

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.11/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, "static")

# Celery settings

CELERY_RESULT_BACKEND = 'django-db'
CELERY_CACHE_BACKEND = 'django-cache'
CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'amqp://localhost')
CELERY_IMPORTS = [
    'tr_ars.tasks',
]
# Other important shared settings
DATA_UPLOAD_MAX_MEMORY_SIZE=1073741824
CELERY_TASK_ALWAYS_EAGER=False
CELERY_TASK_ACKS_LATE = True

USE_CELERY = True
DEFAULT_HOST = os.environ.get('ARS_DEFAULT_HOST', 'http://localhost:8000')
