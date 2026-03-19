"""
api/cv_views.py — Cloud CV Integration Endpoints
==================================================
These endpoints serve the HuggingFace CV service and the browser:

  GET  /api/cv/embeddings/         → CV service fetches enrolled embeddings
  POST /api/cv/save-embeddings/    → CV service saves extracted embeddings
  POST /api/cv/log-attendance/     → Browser logs confirmed attendance
  POST /api/cv/reload/             → Tell CV service to refresh its cache
  GET  /api/cv/status/             → Check CV service health
"""
import logging
from datetime import date

import httpx
from django.conf import settings
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Person, FaceEmbedding, AttendanceLog

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Embedding export (called by HF Space CV service)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])   # CV service doesn't have user JWT
def export_embeddings(request):
    """
    Return all enrolled face embeddings.
    Called by HF Space on startup and every 30s.
    Response: {persons: [{person_id, name, embeddings: [[128 floats], ...]}]}
    """
    persons = Person.objects.filter(is_active=True).prefetch_related('face_embeddings')
    result  = []

    for person in persons:
        emb_list = [
            list(fe.embedding)
            for fe in person.face_embeddings.all()
        ]
        if not emb_list:
            continue
        result.append({
            "person_id":  str(person.id),
            "name":       person.name,
            "employee_id": person.employee_id,
            "embeddings": emb_list,
        })

    return Response({
        "persons": result,
        "count":   len(result),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Save embeddings (called by HF Space after enrollment)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def save_embeddings(request):
    """
    Save face embeddings extracted by the CV service.
    Body: {person_id, name, embeddings: [[128 floats], ...]}
    """
    person_id  = request.data.get('person_id', '').strip()
    name       = request.data.get('name', '').strip()
    embeddings = request.data.get('embeddings', [])

    if not person_id or not name:
        return Response({'error': 'person_id and name required'}, status=400)
    if not embeddings:
        return Response({'error': 'No embeddings provided'}, status=400)

    try:
        person = Person.objects.get(id=person_id)
    except Person.DoesNotExist:
        return Response({'error': 'Person not found'}, status=404)

    # Clear existing embeddings and re-save (idempotent)
    FaceEmbedding.objects.filter(person=person).delete()

    saved = 0
    for i, emb in enumerate(embeddings):
        if not isinstance(emb, list) or len(emb) != 128:
            continue
        FaceEmbedding.objects.create(
            person=person,
            embedding=emb,
            shot_index=i,
        )
        saved += 1

    person.embeddings_paths = [f"db:{person_id}:{i}" for i in range(saved)]
    person.save(update_fields=['embeddings_paths', 'updated_at'])

    logger.info("Saved %d embeddings for %s", saved, name)
    return Response({
        'saved':   saved,
        'message': f'Saved {saved} embeddings for {name}',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Attendance logging (called by browser after N confirmed frames)
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['POST'])
def log_attendance(request):
    """
    Log an attendance event.
    Called by browser when it confirms a person (N consecutive detections).
    Body: {person_id, person_name, action, confidence, track_id}
    """
    person_id   = request.data.get('person_id')
    person_name = request.data.get('person_name', 'Unknown')
    action      = request.data.get('action', 'entry')
    confidence  = float(request.data.get('confidence', 0.0))
    track_id    = int(request.data.get('track_id', -1))

    person = None
    if person_id:
        try:
            person = Person.objects.get(id=person_id)
        except Person.DoesNotExist:
            pass

    if action == 'exit':
        # Find open entry and close it
        log_filter = {'exit_time__isnull': True}
        if person:
            log_filter['person'] = person
        else:
            log_filter['track_id'] = track_id

        log = AttendanceLog.objects.filter(**log_filter).order_by('-entry_time').first()
        if log:
            log.exit_time = timezone.now()
            log.save(update_fields=['exit_time', 'updated_at'])
            logger.info("EXIT logged: %s", person_name)
        else:
            AttendanceLog.objects.create(
                person=person,
                temp_name=person_name if not person else None,
                exit_time=timezone.now(),
                recognition_confidence=confidence,
                track_id=track_id,
                direction='exit',
                frames_seen=1,
            )
    else:
        # Log entry
        log = AttendanceLog.objects.create(
            person=person,
            temp_name=person_name if not person else None,
            entry_time=timezone.now(),
            recognition_confidence=confidence,
            track_id=track_id,
            direction='entry',
            frames_seen=1,
        )
        logger.info("ENTRY logged: %s (conf=%.2f)", person_name, confidence)

    # Broadcast via WebSocket so all browsers get real-time toast
    try:
        from api.consumers import CVFeedConsumer
        CVFeedConsumer.broadcast_attendance({
            'person_id':   person_id,
            'person_name': person_name,
            'action':      action,
            'confidence':  confidence,
            'track_id':    track_id,
        })
    except Exception as e:
        logger.debug("WebSocket broadcast error: %s", e)

    return Response({'status': 'logged', 'action': action, 'person': person_name})


# ─────────────────────────────────────────────────────────────────────────────
# CV Service status
# ─────────────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def cv_service_status(request):
    """Check if the HuggingFace CV service is reachable."""
    cv_url = getattr(settings, 'CV_SERVICE_URL', '')
    if not cv_url:
        return Response({
            'available': False,
            'message':   'CV_SERVICE_URL not configured',
            'setup':     'Set CV_SERVICE_URL in your Railway environment variables',
        })
    try:
        import requests
        resp = requests.get(f"{cv_url}/health", timeout=5)
        data = resp.json()
        return Response({
            'available':      True,
            'url':            cv_url,
            'persons_loaded': data.get('persons_loaded', 0),
            'cache_age_s':    data.get('cache_age_s', 0),
        })
    except Exception as e:
        return Response({
            'available': False,
            'url':       cv_url,
            'error':     str(e),
        })


# ─────────────────────────────────────────────────────────────────────────────
# Trigger CV service cache reload (called after person enrolled/deleted)
# ─────────────────────────────────────────────────────────────────────────────

def notify_cv_service_reload(backend_url: str = None):
    """
    Async-safe: notify the HF Space to reload its embedding cache.
    Called after enrollment or person deletion.
    """
    cv_url = getattr(settings, 'CV_SERVICE_URL', '')
    if not cv_url or not backend_url:
        return
    try:
        import requests
        backend = backend_url or f"{getattr(settings, 'BACKEND_URL', 'http://localhost:8000')}"
        requests.post(
            f"{cv_url}/reload",
            json={"backend_url": backend},
            timeout=3,
        )
    except Exception:
        pass  # Non-fatal — CV service will reload on its 30s TTL
