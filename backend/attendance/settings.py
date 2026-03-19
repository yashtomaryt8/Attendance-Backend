"""
attendance/settings.py — AttendAI v4 (Cloud Architecture)
- No local CV engine config (runs on HuggingFace Spaces)
- Groq replaces Ollama (free, 800 tok/sec, no local model needed)
- Supabase-compatible (can swap SQLite for PostgreSQL on Railway)
"""
import os
from pathlib import Path
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY   = os.environ.get('SECRET_KEY', 'dev-secret-key-CHANGE-IN-PRODUCTION')
DEBUG        = os.environ.get('DEBUG', 'True') == 'True'
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'api',
]

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

ROOT_URLCONF     = 'attendance.urls'
ASGI_APPLICATION = 'attendance.asgi.application'

TEMPLATES = [{
    'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [], 'APP_DIRS': True,
    'OPTIONS': {
        'context_processors': [
            'django.template.context_processors.debug',
            'django.template.context_processors.request',
            'django.contrib.auth.context_processors.auth',
            'django.contrib.messages.context_processors.messages',
        ],
    },
}]

# ── Channels ───────────────────────────────────────────────────────
CHANNEL_LAYERS = {
    'default': {'BACKEND': 'channels.layers.InMemoryChannelLayer'}
}

# ── Database ────────────────────────────────────────────────────────
# Railway provides DATABASE_URL for PostgreSQL (free tier)
# Falls back to SQLite for local dev
DATABASE_URL = os.environ.get('DATABASE_URL', '')

if DATABASE_URL and DATABASE_URL.startswith('postgres'):
    import dj_database_url
    DATABASES = {'default': dj_database_url.parse(DATABASE_URL, conn_max_age=600)}
else:
    DATABASES = {
        'default': {
            'ENGINE':  'django.db.backends.sqlite3',
            'NAME':    BASE_DIR / 'db.sqlite3',
            'OPTIONS': {'timeout': 30},
        }
    }

LANGUAGE_CODE = 'en-us'
TIME_ZONE     = os.environ.get('TIME_ZONE', 'Asia/Kolkata')
USE_I18N      = True
USE_TZ        = True

STATIC_URL  = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL   = '/media/'
MEDIA_ROOT  = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ── CORS ───────────────────────────────────────────────────────────
CORS_ALLOW_ALL_ORIGINS = True
CORS_ALLOW_CREDENTIALS = True

# ── REST ───────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES':   ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': [
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ],
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':    timedelta(days=1),
    'REFRESH_TOKEN_LIFETIME':   timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':    True,
    'BLACKLIST_AFTER_ROTATION': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

# ── Paths ──────────────────────────────────────────────────────────
EMBEDDINGS_ROOT = BASE_DIR / 'data' / 'embeddings'   # kept for compat
EMBEDDINGS_CSV  = EMBEDDINGS_ROOT / 'embeddings_index.csv'
CHROMA_PATH     = str(BASE_DIR / 'data' / 'chromadb')
SNAPSHOTS_DIR   = BASE_DIR / 'media' / 'snapshots'

for _d in [EMBEDDINGS_ROOT, BASE_DIR / 'data', SNAPSHOTS_DIR]:
    _d.mkdir(parents=True, exist_ok=True)

os.environ.setdefault('CHROMA_PATH', CHROMA_PATH)

# ── CV Service (HuggingFace Spaces) ────────────────────────────────
# Set this to your HF Space URL after deployment
# e.g. https://yourusername-attendai-cv.hf.space
CV_SERVICE_URL = os.environ.get('CV_SERVICE_URL', '')
BACKEND_URL    = os.environ.get('BACKEND_URL', 'http://localhost:8000')

# ── LLM — Groq (FREE, no credit card, 800 tok/sec) ─────────────────
# Sign up: https://console.groq.com  → API Keys → Create key
# No rate limits for basic usage. llama-3.1-8b-instant is completely free.
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_MODEL   = os.environ.get('GROQ_MODEL', 'llama-3.1-8b-instant')

# Kept for backward compat (Ollama fallback if Groq key not set)
OLLAMA_URL   = os.environ.get('OLLAMA_URL',   'http://localhost:11434')
OLLAMA_MODEL = os.environ.get('OLLAMA_MODEL', 'phi3:mini')

# ── CV Config (used by engine_status endpoint stub) ────────────────
CV_CONFIG = {
    'mode': 'cloud',
    'cv_service_url': CV_SERVICE_URL,
    'CONFIRMATION_FRAMES': 8,
    'MISS_FRAMES_EXIT': 15,
    'ATTENDANCE_COOLDOWN_S': 30,
    'SEND_FRAME_INTERVAL_MS': 300,
}
