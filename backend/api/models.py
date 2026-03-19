"""
api/models.py — AttendAI v4 (Cloud Architecture)
Added: FaceEmbedding model stores embeddings in DB instead of .pkl files.
This makes them persistent on Railway and fetchable by the HF Space CV service.
"""
import uuid
from django.db import models


class Person(models.Model):
    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name         = models.CharField(max_length=200)
    employee_id  = models.CharField(max_length=100, unique=True, null=True, blank=True)
    embeddings_paths = models.JSONField(default=list)   # kept for compat
    images_folder    = models.CharField(max_length=500, blank=True)
    is_active    = models.BooleanField(default=True)
    notes        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.employee_id or 'No ID'})"

    @property
    def embedding_count(self):
        return self.face_embeddings.count()

    @property
    def image_count(self):
        import os
        folder = self.images_folder
        if folder and os.path.exists(folder):
            return len([f for f in os.listdir(folder) if f.endswith(('.jpg', '.png'))])
        return 0


class FaceEmbedding(models.Model):
    """
    Stores a single face embedding (128-dim dlib vector) for a person.
    Multiple embeddings per person → better recognition accuracy.
    Stored in DB so Railway can persist them and HF Space can fetch them.
    """
    person     = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='face_embeddings')
    embedding  = models.JSONField()         # list of 128 floats
    shot_index = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['person', 'shot_index']
        unique_together = ['person', 'shot_index']

    def __str__(self):
        return f"{self.person.name} shot_{self.shot_index}"


class AttendanceLog(models.Model):
    DIRECTION_CHOICES = [
        ('entry',   'Entry'),
        ('exit',    'Exit'),
        ('unknown', 'Unknown'),
    ]

    person      = models.ForeignKey(
        Person, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='attendance_logs')
    temp_name   = models.CharField(max_length=200, null=True, blank=True)
    entry_time  = models.DateTimeField(null=True, blank=True)
    exit_time   = models.DateTimeField(null=True, blank=True)
    recognition_confidence = models.FloatField(default=0.0)
    track_id    = models.IntegerField(default=-1)
    snapshots   = models.JSONField(default=list)
    direction   = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default='unknown')
    frames_seen = models.IntegerField(default=0)
    notes       = models.TextField(blank=True)
    meta        = models.JSONField(default=dict)
    created_at  = models.DateTimeField(auto_now_add=True)
    updated_at  = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-entry_time']

    def __str__(self):
        name = self.person.name if self.person else (self.temp_name or 'Unknown')
        return f"{name} @ {self.entry_time}"

    @property
    def duration_minutes(self):
        if self.entry_time and self.exit_time:
            return round((self.exit_time - self.entry_time).total_seconds() / 60, 1)
        return None

    @property
    def display_name(self):
        return self.person.name if self.person else (self.temp_name or 'Unknown')


class CVSettings(models.Model):
    key        = models.CharField(max_length=100, unique=True)
    value      = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.key} = {self.value}"
