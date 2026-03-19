from rest_framework import serializers
from .models import Person, AttendanceLog, CVSettings


class PersonSerializer(serializers.ModelSerializer):
    embedding_count = serializers.ReadOnlyField()
    image_count = serializers.ReadOnlyField()

    class Meta:
        model = Person
        fields = [
            'id', 'name', 'employee_id', 'embeddings_paths',
            'images_folder', 'is_active', 'notes',
            'embedding_count', 'image_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'embeddings_paths', 'images_folder', 'created_at', 'updated_at']


class AttendanceLogSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    duration_minutes = serializers.ReadOnlyField()
    person_name = serializers.SerializerMethodField()

    class Meta:
        model = AttendanceLog
        fields = [
            'id', 'person', 'person_name', 'temp_name', 'display_name',
            'entry_time', 'exit_time', 'duration_minutes',
            'recognition_confidence', 'track_id', 'snapshots',
            'direction', 'frames_seen', 'notes', 'meta',
            'created_at', 'updated_at'
        ]

    def get_person_name(self, obj):
        return obj.person.name if obj.person else None


class CVSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = CVSettings
        fields = ['key', 'value', 'updated_at']
