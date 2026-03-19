"""
Groq LLM analytics — drop-in for the existing analytics_query view.
Replaces both Ollama (local) and any paid cloud LLM.
Groq: free, no credit card, llama-3.1-8b-instant at 800 tok/sec.
"""
import json
import logging
from datetime import date

from django.conf import settings
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

logger = logging.getLogger(__name__)


def _groq_query(query: str, log_data: list, date_str: str) -> dict:
    """Query Groq API (free tier). Falls back to rule-based if key not set."""
    groq_key = getattr(settings, 'GROQ_API_KEY', '')
    model    = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')

    if not groq_key:
        return {
            'answer': _fallback_answer(query, log_data, date_str),
            'model':  'fallback',
            'source': 'fallback',
            'error':  'GROQ_API_KEY not set. Get your free key at console.groq.com',
        }

    system_prompt = (
        "You are AttendAI, an attendance analytics assistant. "
        "You receive JSON attendance data and answer questions concisely. "
        "Never invent data not present. Return markdown tables for tabular answers. "
        "Convert ISO timestamps to HH:MM format. Keep answers under 200 words."
    )
    user_msg = (
        f"Date: {date_str}\n"
        f"Query: {query}\n\n"
        f"Attendance data ({len(log_data)} records):\n"
        f"{json.dumps(log_data[:200], indent=2)}"
    )

    try:
        from groq import Groq
        client = Groq(api_key=groq_key)
        resp = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_msg},
            ],
            max_tokens=800,
            temperature=0.2,
        )
        answer = resp.choices[0].message.content.strip()
        return {'answer': answer, 'model': model, 'source': 'groq', 'error': None}
    except Exception as e:
        logger.warning("Groq error: %s", e)
        return {
            'answer': _fallback_answer(query, log_data, date_str),
            'model':  'fallback',
            'source': 'fallback',
            'error':  str(e),
        }


def _fallback_answer(query: str, data: list, date_str: str) -> str:
    q     = query.lower()
    total = len(data)
    known = sum(1 for r in data if r.get('employee_id'))
    still = sum(1 for r in data if not r.get('exit_time'))
    confs = [r['confidence'] for r in data if r.get('confidence')]
    avg   = round(sum(confs) / len(confs), 2) if confs else 0
    names = sorted({r['name'] for r in data if r.get('name') and r['name'] != 'Unknown'})

    if any(w in q for w in ('how many', 'count', 'total', 'number')):
        return (
            f"**{date_str}** | Total: {total} | Known: {known} | "
            f"Unknown: {total-known} | Still inside: {still} | Avg confidence: {avg:.0%}"
        )
    if any(w in q for w in ('who', 'name', 'list', 'people', 'present')):
        return "Present today: " + (", ".join(names) if names else "No known persons.")
    if 'confidence' in q or 'accuracy' in q:
        return f"Average recognition confidence: **{avg:.0%}** across {total} entries."
    return (
        f"_Groq unavailable — basic stats for {date_str}:_ "
        f"Total: **{total}** | Known: **{known}** | "
        f"Still inside: **{still}** | Avg confidence: **{avg:.0%}**"
    )


@api_view(['POST'])
def analytics_query(request):
    """Semantic attendance analytics powered by Groq (free LLM)."""
    from api.models import AttendanceLog
    from django.db.models import Avg

    query = request.data.get('query', '').strip()
    if not query:
        return Response({'error': 'query is required'}, status=400)

    date_param = request.data.get('date', date.today().isoformat())
    try:
        d = date.fromisoformat(date_param)
    except ValueError:
        d = date.today()

    logs = AttendanceLog.objects.filter(entry_time__date=d).select_related('person')[:500]
    log_data = [{
        'name':         log.display_name,
        'employee_id':  log.person.employee_id if log.person else None,
        'entry_time':   log.entry_time.isoformat() if log.entry_time else None,
        'exit_time':    log.exit_time.isoformat()  if log.exit_time  else None,
        'duration_min': log.duration_minutes,
        'confidence':   round(log.recognition_confidence, 3),
        'direction':    log.direction,
    } for log in logs]

    result = _groq_query(query, log_data, date_param)

    return Response({
        'query':     query,
        'answer':    result['answer'],
        'data_rows': len(log_data),
        'model':     result['model'],
        'source':    result['source'],
        'error':     result.get('error'),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def ollama_status(request):
    """Returns Groq status (replaces Ollama status check)."""
    groq_key = getattr(settings, 'GROQ_API_KEY', '')
    model    = getattr(settings, 'GROQ_MODEL', 'llama-3.1-8b-instant')
    return Response({
        'available':   bool(groq_key),
        'service':     'groq',
        'model':       model,
        'url':         'https://api.groq.com',
        'free':        True,
        'speed':       '800 tokens/sec',
        'setup':       'Get free key at https://console.groq.com',
        'key_set':     bool(groq_key),
    })
