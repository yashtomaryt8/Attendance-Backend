"""
api/views.py — AttendAI v4 (Cloud Architecture)
All views updated to work without a local CV engine.
Engine status returns cloud service info.
Enrollment creates person record; CV service handles embeddings.
Analytics uses Groq (free) or Ollama fallback.
"""
import os
import csv
import json
import logging
import uuid
from io import StringIO
from datetime import date

from django.conf import settings
from django.db.models import Avg
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes, permission_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import Person, AttendanceLog, CVSettings
from .serializers import PersonSerializer, AttendanceLogSerializer

# Analytics powered by Groq (free) — imported from dedicated module
from .analytics_views import analytics_query, ollama_status  # noqa: F401

logger = logging.getLogger(__name__)


# ─── Dashboard ────────────────────────────────────────────────────────────────
@api_view(['GET'])
def dashboard_stats(request):
    today = date.today()
    qs = AttendanceLog.objects.filter(entry_time__date=today).select_related('person')
    total    = qs.count()
    known    = qs.filter(person__isnull=False).count()
    unknown  = qs.filter(person__isnull=True).count()
    exited   = qs.filter(exit_time__isnull=False).count()
    avg_conf = float(qs.aggregate(avg=Avg('recognition_confidence'))['avg'] or 0)

    recent = qs.order_by('-entry_time')[:10]
    recent_data = [{
        'id':         log.id,
        'name':       log.display_name,
        'entry_time': log.entry_time.isoformat() if log.entry_time else None,
        'exit_time':  log.exit_time.isoformat()  if log.exit_time  else None,
        'confidence': round(log.recognition_confidence, 3),
        'direction':  log.direction,
        'snapshot':   log.snapshots[0] if log.snapshots else None,
    } for log in recent]

    # Cloud mode: engine info comes from CV service
    cv_url = getattr(settings, 'CV_SERVICE_URL', '')
    engine_info = {
        'running':           bool(cv_url),
        'fps':               0,
        'active_tracks':     0,
        'embedding_persons': Person.objects.filter(is_active=True).count(),
        'mode':              'cloud',
        'cv_service_url':    cv_url,
    }

    return Response({
        'date':            today.isoformat(),
        'total_entries':   total,
        'known_persons':   known,
        'unknown_persons': unknown,
        'still_inside':    total - exited,
        'exited':          exited,
        'avg_confidence':  round(avg_conf, 3),
        'total_enrolled':  Person.objects.filter(is_active=True).count(),
        'engine':          engine_info,
        'recent_activity': recent_data,
    })


# ─── People ───────────────────────────────────────────────────────────────────
@api_view(['GET', 'POST'])
def people_list(request):
    if request.method == 'GET':
        people = Person.objects.filter(is_active=True).order_by('name')
        return Response(PersonSerializer(people, many=True).data)
    serializer = PersonSerializer(data=request.data)
    if serializer.is_valid():
        person = serializer.save()
        return Response(PersonSerializer(person).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def enroll_person(request):
    """
    Create person record. In cloud mode, embeddings are sent separately
    by the browser → HF Space → /api/cv/save-embeddings/.
    This endpoint just creates the DB record and returns the person_id.
    """
    name        = request.data.get('name', '').strip()
    employee_id = request.data.get('employee_id', '').strip() or None
    if not name:
        return Response({'error': 'name is required'}, status=400)

    person_uuid   = str(uuid.uuid4())
    images_folder = os.path.join(str(settings.MEDIA_ROOT), 'enrollments', person_uuid)
    os.makedirs(images_folder, exist_ok=True)

    person = Person.objects.create(
        id=person_uuid,
        name=name,
        employee_id=employee_id,
        images_folder=images_folder,
        embeddings_paths=[],
    )

    logger.info("Person created: %s (%s)", name, person_uuid)
    return Response({
        'person':  PersonSerializer(person).data,
        'message': f"Person '{name}' created. Now enroll face via the camera.",
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
def person_detail(request, person_id):
    try:
        person = Person.objects.get(id=person_id)
    except Person.DoesNotExist:
        return Response({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        return Response(PersonSerializer(person).data)

    elif request.method == 'PUT':
        ser = PersonSerializer(person, data=request.data, partial=True)
        if ser.is_valid():
            ser.save()
            return Response(ser.data)
        return Response(ser.errors, status=400)

    elif request.method == 'DELETE':
        import shutil
        pid_str = str(person.id)
        # Delete enrollment images
        try:
            if person.images_folder and os.path.isdir(person.images_folder):
                shutil.rmtree(person.images_folder, ignore_errors=True)
        except Exception:
            pass
        # Delete DB embeddings
        from .models import FaceEmbedding
        FaceEmbedding.objects.filter(person=person).delete()
        person.delete()

        # Notify CV service to reload cache
        from .cv_views import notify_cv_service_reload
        backend_url = getattr(settings, 'BACKEND_URL', request.build_absolute_uri('/')[:-1])
        notify_cv_service_reload(backend_url)

        return Response(status=204)


# ─── Attendance ───────────────────────────────────────────────────────────────
@api_view(['GET'])
def attendance_list(request):
    qs = AttendanceLog.objects.select_related('person').order_by('-entry_time')
    if d := request.GET.get('date'):
        try:
            qs = qs.filter(entry_time__date=date.fromisoformat(d))
        except ValueError:
            return Response({'error': 'Invalid date'}, status=400)
    if pid := request.GET.get('person_id'):
        qs = qs.filter(person_id=pid)
    limit = int(request.GET.get('limit', 200))
    qs = qs[:limit]

    if request.GET.get('format') == 'csv':
        buf = StringIO()
        w = csv.writer(buf)
        w.writerow(['id', 'name', 'employee_id', 'entry_time', 'exit_time',
                    'duration_minutes', 'confidence', 'track_id', 'direction'])
        for log in qs:
            w.writerow([
                log.id, log.display_name,
                log.person.employee_id if log.person else '',
                log.entry_time.isoformat() if log.entry_time else '',
                log.exit_time.isoformat()  if log.exit_time  else '',
                log.duration_minutes or '',
                round(log.recognition_confidence, 4),
                log.track_id, log.direction,
            ])
        resp = HttpResponse(buf.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = 'attachment; filename="attendance.csv"'
        return resp

    return Response(AttendanceLogSerializer(qs, many=True).data)


@api_view(['GET'])
def attendance_summary(request):
    d_str = request.GET.get('date', date.today().isoformat())
    try:
        d = date.fromisoformat(d_str)
    except ValueError:
        return Response({'error': 'Invalid date'}, status=400)
    qs     = AttendanceLog.objects.filter(entry_time__date=d)
    total  = qs.count()
    known  = qs.filter(person__isnull=False).count()
    exited = qs.filter(exit_time__isnull=False).count()
    avg    = float(qs.aggregate(avg=Avg('recognition_confidence'))['avg'] or 0)
    return Response({
        'date': d_str, 'total_entries': total,
        'known_persons': known, 'unknown_persons': total - known,
        'still_inside': total - exited, 'avg_confidence': round(avg, 3),
    })


# ─── Engine (cloud stub) ──────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([AllowAny])
def engine_status(request):
    """Returns cloud CV service status instead of local engine status."""
    from .cv_views import cv_service_status
    return cv_service_status(request)


@api_view(['POST'])
def engine_control(request):
    """No-op in cloud mode — camera controlled by browser."""
    action = request.data.get('action', '')
    if action in ('start', 'stop', 'reload_embeddings', 'set_mode'):
        return Response({'status': action, 'mode': 'cloud',
                         'message': 'Cloud mode: camera controlled by browser'})
    return Response({'error': f'Unknown action: {action}'}, status=400)


@api_view(['GET', 'POST'])
def cv_settings(request):
    if request.method == 'GET':
        return Response(getattr(settings, 'CV_CONFIG', {}))
    updated = []
    for key, val in request.data.items():
        CVSettings.objects.update_or_create(key=key, defaults={'value': val})
        updated.append(key)
    return Response({'updated': updated})


# ─── Reset ────────────────────────────────────────────────────────────────────
@api_view(['POST'])
def reset_all_data(request):
    import shutil
    from .models import FaceEmbedding
    try:
        AttendanceLog.objects.all().delete()
        FaceEmbedding.objects.all().delete()
        Person.objects.all().delete()
        for d in [
            os.path.join(str(settings.MEDIA_ROOT), sub)
            for sub in ('enrollments', 'snapshots')
        ]:
            if os.path.isdir(d):
                shutil.rmtree(d, ignore_errors=True)
            os.makedirs(d, exist_ok=True)
        # Notify CV service to clear its cache
        from .cv_views import notify_cv_service_reload
        notify_cv_service_reload(getattr(settings, 'BACKEND_URL', ''))
        return Response({'status': 'ok', 'message': 'All data reset.'})
    except Exception as e:
        logger.exception('reset_all_data failed')
        return Response({'error': str(e)}, status=500)
