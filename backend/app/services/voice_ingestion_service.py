import io
import json
import logging

from sqlalchemy.orm import Session

from app.models.ingestion import StagedIngestion

logger = logging.getLogger(__name__)

# Lazy clients — created on first call so import doesn't fail without API keys.
_whisper = None
_claude  = None


def _get_whisper():
    global _whisper
    if _whisper is None:
        import openai
        _whisper = openai.OpenAI()
    return _whisper


def _get_claude():
    global _claude
    if _claude is None:
        import anthropic
        _claude = anthropic.Anthropic()
    return _claude

PARSE_PROMPT = (
    'Parse this spoken inventory count from a restaurant kitchen manager. '
    'Extract all items mentioned. Return ONLY valid JSON: '
    '{"items":[{"ingredient_name":"string","quantity":number,"unit":"string or null"}],'
    '"unclear_segments":["segments you could not parse"]}. '
    'Common units: lb, oz, case, each, liter, gallon, bag, dozen. '
    'If unit not stated, set null. No markdown.'
)


def transcribe(audio_bytes: bytes, fmt: str = 'webm') -> str:
    buf      = io.BytesIO(audio_bytes)
    buf.name = f'recording.{fmt}'
    return _get_whisper().audio.transcriptions.create(
        model='whisper-1', file=buf, language='en', response_format='text',
    )


def parse_transcript(transcript: str) -> dict:
    resp = _get_claude().messages.create(
        model='claude-sonnet-4-6',
        max_tokens=800,
        messages=[{'role': 'user', 'content': PARSE_PROMPT + '\n\nTRANSCRIPT: ' + transcript}],
    )
    raw = resp.content[0].text.strip()
    if raw.startswith('```'):
        raw = '\n'.join(raw.split('\n')[1:-1])
    return json.loads(raw)


def stage_voice_count(
    db: Session,
    restaurant_id: str,
    audio_bytes: bytes,
    fmt: str = 'webm',
) -> StagedIngestion:
    transcript = transcribe(audio_bytes, fmt)
    parsed     = parse_transcript(transcript)
    staged = StagedIngestion(
        restaurant_id     = restaurant_id,
        ingestion_type    = 'voice',
        import_type       = 'inventory_count',
        raw_input         = transcript,
        extracted_data    = parsed,
        confidence_scores = {'overall': 0.85},
    )
    db.add(staged)
    db.commit()
    db.refresh(staged)
    return staged
