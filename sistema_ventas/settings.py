import sys
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ============================================================
# CARGAR .env AUTOMÁTICAMENTE (antes de cualquier otra cosa)
# ============================================================
try:
    from dotenv import load_dotenv
    ENV_FILE = BASE_DIR / '.env'
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
    else:
        print(f"⚠️  ADVERTENCIA: No se encontró el archivo .env en {ENV_FILE}")
except ImportError:
    print("⚠️  ADVERTENCIA: python-dotenv no está instalado. pip install python-dotenv")


# Agrega la carpeta apps al path para evitar problemas con las importaciones cruzadas
sys.path.insert(0, str(BASE_DIR / 'apps'))


# ============================================================
# HELPERS PARA LEER VARIABLES DE ENTORNO
# ============================================================
def env(key, default=None, cast=str):
    """Lee una variable de entorno y la convierte al tipo indicado."""
    value = os.environ.get(key, default)
    if value is None:
        return None
    if cast == bool:
        return str(value).lower() in ('true', '1', 'yes', 'on')
    if cast == int:
        return int(value)
    if cast == list:
        return [x.strip() for x in str(value).split(',') if x.strip()]
    return value


# ============================================================
# SEGURIDAD
# ============================================================
SECRET_KEY = env(
    'SECRET_KEY',
    'django-insecure-iyz%l0@j&fv89an+%dnnlwm5i+r@$m#5-(b-lp7(l!&qk+ubt9'
)

DEBUG = env('DEBUG', 'True', bool)

ALLOWED_HOSTS = env(
    'ALLOWED_HOSTS',
    'localhost,127.0.0.1,10.0.10.196,10.0.10.181',
    list
)

CSRF_TRUSTED_ORIGINS = env(
    'CSRF_TRUSTED_ORIGINS',
    'http://localhost:8082,https://localhost:8082,'
    'http://127.0.0.1:8082,https://127.0.0.1:8082',
    list
)


# ============================================================
# APPS
# ============================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    'session_security',

    'apps.usuarios',
    'apps.core',
    'apps.productos',
    'apps.configuracion.apps.ConfiguracionConfig',
    'apps.ventas',
    'apps.alertas.apps.AlertasConfig',
]

AUTH_USER_MODEL = 'usuarios.Usuario'


# ============================================================
# MIDDLEWARE
# ============================================================
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'session_security.middleware.SessionSecurityMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ============================================================
# SESIÓN
# ============================================================
SESSION_SECURITY_WARN_AFTER = 60 * 60 * 3 - 300
SESSION_SECURITY_EXPIRE_AFTER = 60 * 60 * 3

SESSION_COOKIE_AGE = 60 * 60 * 3
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SESSION_SECURITY_INSECURE = env('SESSION_SECURITY_INSECURE', 'True', bool)


# ============================================================
# URLS / TEMPLATES
# ============================================================
ROOT_URLCONF = 'sistema_ventas.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',

                'apps.configuracion.context_processors.modulos_activos',
                'apps.configuracion.context_processors.configuracion_global',
                'apps.ventas.context_processors.remitos_pendientes_global',
            ],
        },
    },
]

WSGI_APPLICATION = 'sistema_ventas.wsgi.application'


# ============================================================
# BASE DE DATOS
# ============================================================
DB_ENGINE = env('DB_ENGINE', 'django.db.backends.sqlite3')

if DB_ENGINE == 'django.db.backends.sqlite3':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': DB_ENGINE,
            'NAME': env('DB_NAME', 'sistema_ventas'),
            'USER': env('DB_USER', 'pos_user'),
            'PASSWORD': env('DB_PASSWORD', ''),
            'HOST': env('DB_HOST', '10.0.10.220'),
            'PORT': env('DB_PORT', '5432'),
            'OPTIONS': {
                'connect_timeout': 10,
            },
            'CONN_MAX_AGE': 600,
        }
    }


# ============================================================
# AUTENTICACIÓN
# ============================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ============================================================
# INTERNACIONALIZACIÓN
# ============================================================
LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True


# ============================================================
# ARCHIVOS ESTÁTICOS Y MEDIA
# ============================================================
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ============================================================
# OTROS
# ============================================================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = 'usuarios:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'usuarios:login'


# ============================================================
# LOGGING
# ============================================================
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}


# ============================================================
# SEGURIDAD EN PRODUCCIÓN
# ============================================================
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_BROWSER_XSS_FILTER = True
    X_FRAME_OPTIONS = 'DENY'

    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False