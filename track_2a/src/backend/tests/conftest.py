"""Shared fixtures: an isolated app per test (in-memory SQLite, offline coach,
seeded demo class) and a scriptable fake brain for engine tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zusage.config import Settings
from zusage.engine.brain import BrainResult, OfflineBrain
from zusage.knowledge import load_knowledge
from zusage.llm.client import LLMError, Usage
from zusage.main import create_app

DATA = Path(__file__).resolve().parents[3] / "data"


@pytest.fixture(scope="session")
def kb():
    return load_knowledge(DATA)


@pytest.fixture
def settings(tmp_path):
    return Settings(
        offline=True,
        database_url=f"sqlite:///{tmp_path}/test.db",
        data_dir=str(DATA),
        secret_key="test-secret",
        seed_demo=True,
    )


@pytest.fixture
def client(settings):
    app = create_app(settings)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def student(client):
    assert client.post("/api/auth/demo/student").status_code == 200
    return client


class FakeBrain:
    """Returns scripted model outputs (or raises), counting calls like a real LLM."""

    name = "fake"
    model = "fake-apertus"

    def __init__(self, turn_outputs=None, fail=False, report=None, tailor=None):
        self.turn_outputs = list(turn_outputs or [])
        self.fail = fail
        self.report = report
        self.tailor_out = tailor
        self.calls = 0

    def _usage(self):
        self.calls += 1
        return Usage(calls=1, tokens_in=500, tokens_out=120, latency_ms=900)

    def assess_turn(self, kb, inp):
        if self.fail:
            raise LLMError("timeout", "simulated outage")
        data = self.turn_outputs.pop(0) if self.turn_outputs else OfflineBrain().assess_turn(kb, inp).data
        return BrainResult(data, self._usage(), self.model)

    def final_report(self, kb, **kw):
        if self.fail or self.report is None:
            raise LLMError("timeout", "simulated outage")
        return BrainResult(self.report, self._usage(), self.model)

    def tailor(self, kb, **kw):
        if self.tailor_out is None:
            raise LLMError("server", "no tailor")
        return BrainResult(self.tailor_out, self._usage(), self.model)


@pytest.fixture
def fake_brain():
    return FakeBrain
