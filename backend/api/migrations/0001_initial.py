from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='Person',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=200)),
                ('employee_id', models.CharField(blank=True, max_length=100, null=True, unique=True)),
                ('embeddings_paths', models.JSONField(default=list)),
                ('images_folder', models.CharField(blank=True, max_length=500)),
                ('is_active', models.BooleanField(default=True)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={'ordering': ['name']},
        ),
        migrations.CreateModel(
            name='AttendanceLog',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('temp_name', models.CharField(blank=True, max_length=200, null=True)),
                ('entry_time', models.DateTimeField(blank=True, null=True)),
                ('exit_time', models.DateTimeField(blank=True, null=True)),
                ('recognition_confidence', models.FloatField(default=0.0)),
                ('track_id', models.IntegerField(default=-1)),
                ('snapshots', models.JSONField(default=list)),
                ('direction', models.CharField(
                    choices=[('entry', 'Entry'), ('exit', 'Exit'), ('unknown', 'Unknown')],
                    default='unknown', max_length=20)),
                ('frames_seen', models.IntegerField(default=0)),
                ('notes', models.TextField(blank=True)),
                ('meta', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('person', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='attendance_logs', to='api.person')),
            ],
            options={'ordering': ['-entry_time']},
        ),
        migrations.CreateModel(
            name='CVSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('key', models.CharField(max_length=100, unique=True)),
                ('value', models.JSONField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
    ]
