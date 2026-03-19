"""
api/apps.py — AttendAI v4 (Cloud Architecture)
No local CV engine. Attendance is logged via /api/cv/log-attendance/ from browser.
WebSocket broadcast still works — consumers.py unchanged.
"""
import logging
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name               = 'api'
    verbose_name       = 'AttendAI API'

    def ready(self):
        """
        No engine auto-start in cloud mode.
        The CV engine runs on HuggingFace Spaces, not here.
        """
        pass


# ─── Stub functions kept for backward compat with any existing views ──────────

def get_engine():
    return None


def start_engine():
    return None


def stop_engine():
    pass
