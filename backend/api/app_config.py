from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        import os
        # Only auto-start in server context (not during migrations/shell)
        if os.environ.get('RUN_CV_ENGINE', 'true').lower() == 'true':
            # Delay import to avoid circular imports during startup
            import threading
            def _delayed_start():
                import time
                time.sleep(2)  # wait for Django to fully initialize
                try:
                    from api.apps import start_engine
                    start_engine()
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning(f"Auto-start CV engine failed: {e}")
            t = threading.Thread(target=_delayed_start, daemon=True)
            t.start()
