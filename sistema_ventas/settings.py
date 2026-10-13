import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Agrega la carpeta apps al path para evitar problemas con las importaciones cruzadas
sys.path.insert(0, str(BASE_DIR / 'apps'))

SECRET_KEY = 'django-insecure-iyz%l0@j&fv89an+%dnnlwm5i+r@$m#5-(b-lp7(l!&qk+ubt9'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1', '10.0.10.196', '*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_extensions',

    # 🔽 App de terceros: caducidad de sesión
    'session_security',

    # Apps alojadas en la subcarpeta apps/
    'apps.usuarios',
    'apps.core',
    'apps.productos',
    'apps.configuracion.apps.ConfiguracionConfig',
    'apps.ventas',
    'apps.alertas.apps.AlertasConfig',   # 🔽 NUEVA
]

AUTH_USER_MODEL = 'usuarios.Usuario'

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'session_security.middleware.SessionSecurityMiddleware',   # 🔽 NUEVO
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# 🔽 Sesión: 3 horas de inactividad
SESSION_SECURITY_WARN_AFTER = 60 * 60 * 3 - 300   # aviso a las 2h 55min
SESSION_SECURITY_EXPIRE_AFTER = 60 * 60 * 3       # expira a las 3h

# 🔽 Forzar expiración en el servidor
SESSION_COOKIE_AGE = 60 * 60 * 3
SESSION_SAVE_EVERY_REQUEST = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False

SESSION_SECURITY_INSECURE = True

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

# =========================================================
# BASE DE DATOS
# =========================================================
# Para volver a SQLite: cambiá USE_POSTGRES a False
USE_POSTGRES = False

if USE_POSTGRES:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': 'sistema_ventas',
            'USER': 'pos_user',
            'PASSWORD': 'neron123',
            'HOST': '10.0.10.220',
            'PORT': '5432',
            'OPTIONS': {
                'connect_timeout': 10,
            },
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Rutas de Autenticación
LOGIN_URL = 'usuarios:login'
LOGIN_REDIRECT_URL = 'core:dashboard'
LOGOUT_REDIRECT_URL = 'usuarios:login'