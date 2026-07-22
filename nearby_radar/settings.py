import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# ---- SECURITY: SECRET_KEY ----
# لا تستخدم قيمة افتراضية ضعيفة في الإنتاج؛ اطلب المفتاح صراحةً.
_DEFAULT_DEV_KEY = 'django-insecure-dev-only-key-do-not-use-in-production'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', _DEFAULT_DEV_KEY)
if not os.environ.get('DJANGO_SECRET_KEY') and not os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes'):
    raise RuntimeError('DJANGO_SECRET_KEY must be set in production.')

DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if h.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'api',
]

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
]

SITE_ID = 1
LOGIN_REDIRECT_URL = '/' # أين يذهب المستخدم بعد النجاح
LOGIN_URL = '/api/login-page/'
LOGOUT_REDIRECT_URL = '/api/login-page/'
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'nearby_radar.urls'

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
            ],
        },
    },
]

WSGI_APPLICATION = 'nearby_radar.wsgi.application'

# ---- DATABASE: SQLite افتراضياً، PostgreSQL عند ضبط DATABASE_URL ----
def _get_database():
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        try:
            import dj_database_url
            return dj_database_url.parse(db_url, conn_max_age=600)
        except ImportError:
            # تحليل بسيط لمسار postgres كاحتياط
            return {'ENGINE': 'django.db.backends.postgresql',
                    'NAME': db_url.rsplit('/', 1)[-1] or 'radar',
                    'USER': os.environ.get('POSTGRES_USER', 'postgres'),
                    'PASSWORD': os.environ.get('POSTGRES_PASSWORD', ''),
                    'HOST': os.environ.get('POSTGRES_HOST', 'localhost'),
                    'PORT': os.environ.get('POSTGRES_PORT', '5432')}
    return {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3'}

DATABASES = {'default': _get_database()}

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

LANGUAGE_CODE = 'en-us'

TIME_ZONE = os.environ.get('DJANGO_TIME_ZONE', 'UTC')

USE_I18N = True

USE_L10N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': '20/hour',
        'user': '1000/hour',
    },
}

# ---- SECURITY: CORS محدود بدل الجميع ----
CORS_ALLOW_ALL_ORIGINS = False
_allowed_origins = os.environ.get('DJANGO_CORS_ALLOWED_ORIGINS', '')
CORS_ALLOWED_ORIGINS = [o.strip() for o in _allowed_origins.split(',') if o.strip()]

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': 900,      # 15 دقيقة (بدل 24 ساعة)
    'REFRESH_TOKEN_LIFETIME': 7 * 24 * 3600,
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ---- SECURITY: إعدادات الإنتاج الآمنة ----
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ---- OTP لإعادة تعيين كلمة المرور ----
PASSWORD_RESET_OTP_EXPIRY_MINUTES = int(os.environ.get('OTP_EXPIRY_MINUTES', '10'))
PASSWORD_RESET_OTP_LENGTH = int(os.environ.get('OTP_LENGTH', '6'))
OTP_RESEND_COOLDOWN_SECONDS = int(os.environ.get('OTP_RESEND_SECONDS', '60'))

# ---- اكتشاف القريبين ----
NEARBY_RADIUS_KM = float(os.environ.get('NEARBY_RADIUS_KM', '2.5'))
ONLINE_THRESHOLD_MINUTES = int(os.environ.get('ONLINE_THRESHOLD_MINUTES', '5'))

# ---- Logging ----
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'api': {'handlers': ['console'], 'level': os.environ.get('LOG_LEVEL', 'INFO')},
        'django.security': {'handlers': ['console'], 'level': 'WARNING'},
    },
}
