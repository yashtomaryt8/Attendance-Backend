from django.contrib import admin
from .models import Person, AttendanceLog, CVSettings


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ['name', 'employee_id', 'embedding_count', 'image_count', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['name', 'employee_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'embedding_count', 'image_count']


@admin.register(AttendanceLog)
class AttendanceLogAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'entry_time', 'exit_time', 'duration_minutes',
                    'recognition_confidence', 'direction', 'track_id']
    list_filter = ['direction', 'entry_time']
    search_fields = ['person__name', 'temp_name', 'track_id']
    readonly_fields = ['created_at', 'updated_at', 'duration_minutes', 'display_name']
    date_hierarchy = 'entry_time'


@admin.register(CVSettings)
class CVSettingsAdmin(admin.ModelAdmin):
    list_display = ['key', 'value', 'updated_at']
