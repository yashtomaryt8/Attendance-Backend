from django.urls import path
from . import views, auth_views, cv_views

urlpatterns = [
    # ─── Auth ────────────────────────────────────────────────────
    path('auth/register/', auth_views.register, name='auth-register'),
    path('auth/login/',    auth_views.login,    name='auth-login'),
    path('auth/logout/',   auth_views.logout,   name='auth-logout'),
    path('auth/profile/',  auth_views.profile,  name='auth-profile'),

    # ─── People ──────────────────────────────────────────────────
    path('people/',                 views.people_list,   name='people-list'),
    path('people/enroll/',          views.enroll_person, name='enroll-person'),
    path('people/<str:person_id>/', views.person_detail, name='person-detail'),

    # ─── Attendance ──────────────────────────────────────────────
    path('attendance/summary/', views.attendance_summary, name='attendance-summary'),
    path('attendance/',         views.attendance_list,    name='attendance-list'),

    # ─── Dashboard ───────────────────────────────────────────────
    path('dashboard/', views.dashboard_stats, name='dashboard-stats'),

    # ─── Engine stub (returns cloud service info now) ─────────────
    path('engine/status/',   views.engine_status,  name='engine-status'),
    path('engine/control/',  views.engine_control, name='engine-control'),
    path('engine/settings/', views.cv_settings,    name='cv-settings'),

    # ─── Analytics (Groq LLM) ─────────────────────────────────────
    path('analytics/query/',  views.analytics_query, name='analytics-query'),
    path('analytics/ollama/', views.ollama_status,   name='ollama-status'),

    # ─── CV Cloud Endpoints (NEW) ─────────────────────────────────
    # Called by HuggingFace CV service
    path('cv/embeddings/',     cv_views.export_embeddings,  name='cv-embeddings'),
    path('cv/save-embeddings/', cv_views.save_embeddings,   name='cv-save-embeddings'),
    # Called by browser
    path('cv/log-attendance/', cv_views.log_attendance,     name='cv-log-attendance'),
    # Status check
    path('cv/status/',         cv_views.cv_service_status,  name='cv-status'),

    # ─── Data Management ──────────────────────────────────────────
    path('reset-all/', views.reset_all_data, name='reset-all-data'),
]
