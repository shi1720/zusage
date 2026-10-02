"""Optional natural interviewer speech. Never accepts arbitrary synthesis text."""

from __future__ import annotations

import base64
import hashlib
import threading
import time
from collections import OrderedDict, deque

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..config import Settings
from ..db import Interview, User
from ..engine.guard import redact
from .deps import current_user, get_session

router = APIRouter(prefix="/api/interviews", tags=["speech"])
LOCALES = {"en": "en-US", "de": "de-DE", "fr": "fr-FR", "it": "it-IT", "gsw": "de-DE"}


class SpeechIn(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    rate: float = Field(default=0.95, ge=0.8, le=1.1)


class SpeechService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.lock = threading.Lock()
        self.slots = threading.BoundedSemaphore(2)
        self.cache: OrderedDict[str, tuple[float, bytes]] = OrderedDict()
        self.requests: OrderedDict[str, deque[float]] = OrderedDict()
        self.credentials = None

    def synthesize(self, text: str, language: str, rate: float) -> bytes:
        import google.auth
        from google.auth.transport.requests import Request as AuthRequest

        with self.lock:
            if self.credentials is None:
                self.credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
            if not self.credentials.valid:
                self.credentials.refresh(AuthRequest())
            token = self.credentials.token
        locale = LOCALES[language]
        with httpx.Client(timeout=18) as client:
            response = client.post("https://eu-texttospeech.googleapis.com/v1/text:synthesize", json={
                "input": {"text": text},
                "voice": {"languageCode": locale, "name": f"{locale}-Chirp3-HD-Aoede"},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": rate},
            }, headers={"Authorization": f"Bearer {token}",
                        "x-goog-user-project": self.settings.tts_project})
            response.raise_for_status()
            audio = base64.b64decode(response.json()["audioContent"], validate=True)
            if not audio or len(audio) > 2_000_000:
                raise ValueError("Invalid speech response")
            return audio

    def audio(self, user_id: str, interview_id: str, text: str, language: str, rate: float) -> bytes:
        now = time.monotonic()
        key = hashlib.sha256(f"{interview_id}:{language}:{rate}:{text}".encode()).hexdigest()
        with self.lock:
            bucket = self.requests.setdefault(user_id, deque())
            while bucket and bucket[0] <= now - 60:
                bucket.popleft()
            if len(bucket) >= 20:
                raise HTTPException(429, "Voice limit reached. Try again shortly.")
            bucket.append(now)
            self.requests.move_to_end(user_id)
            while len(self.requests) > 1000:
                self.requests.popitem(last=False)
            cached = self.cache.get(key)
            if cached and cached[0] > now:
                self.cache.move_to_end(key)
                return cached[1]
        if not self.slots.acquire(blocking=False):
            raise HTTPException(503, "Natural voice is busy. Device voice remains available.")
        try:
            audio = self.synthesize(text, language, rate)
            with self.lock:
                self.cache[key] = (now + 600, audio)
                self.cache.move_to_end(key)
                while len(self.cache) > 32:
                    self.cache.popitem(last=False)
            return audio
        except HTTPException:
            raise
        except Exception:
            # Provider errors can contain request text or credentials; never log them.
            raise HTTPException(503, "Natural voice is unavailable. Device voice remains available.") from None
        finally:
            self.slots.release()


@router.post("/{interview_id}/speech")
def interviewer_speech(interview_id: str, body: SpeechIn, request: Request,
                       user: User = Depends(current_user), session: Session = Depends(get_session)):
    iv = session.get(Interview, interview_id)
    if not iv or iv.user_id != user.id:
        raise HTTPException(404, "Interview not found")
    state = iv.state or {}
    if state.get("purged") or state.get("safety_pause"):
        raise HTTPException(409, "Speech is paused for this interview")
    allowed = {state.get("interviewer_message", "")}
    if state.get("turns"):
        allowed.add(state["turns"][-1]["question"]["text"])
    if body.text not in allowed:
        raise HTTPException(400, "Only the current interviewer message can be spoken")
    service = request.app.state.speech
    if not service.settings.tts_enabled:
        raise HTTPException(503, "Natural voice is not enabled on this deployment")
    audio = service.audio(user.id, iv.id, redact(body.text), iv.language, body.rate)
    return Response(audio, media_type="audio/mpeg", headers={"X-Zusage-Voice": "Chirp3-HD-Aoede"})
