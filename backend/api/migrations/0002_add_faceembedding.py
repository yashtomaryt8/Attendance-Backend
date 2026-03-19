from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='FaceEmbedding',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('embedding', models.JSONField()),
                ('shot_index', models.IntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('person', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='face_embeddings',
                    to='api.person',
                )),
            ],
            options={
                'ordering': ['person', 'shot_index'],
                'unique_together': {('person', 'shot_index')},
            },
        ),
    ]
