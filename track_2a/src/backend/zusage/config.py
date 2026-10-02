"""Application configuration.

Every knob lives here, so the same container image runs in every context:

- **live**    : ``LLM_BASE_URL`` + ``LLM_API_KEY`` + ``LLM_NAME`` point at any
                OpenAI-compatible server hosting Apertus 1.5 (CSCS, vLLM,
                llama.cpp, Ollama, MLX, Public AI, Infomaniak...).
- **offline** : no LLM configured. A deterministic, rule-based coach stands in
                so the product, the tests and CI run with zero credentials.
                The UI shows a clear "offline demo" badge - nothing is faked
                silently.

The three ``LLM_*`` variables are the names mandated by the Hack Apertus
project template; ``ZUSAGE_*`` variables tune the product itself.
"""

from __future__ import annotations

import secrets
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> str:
    # repo layout: track_2a/src/backend/zusage/config.py -> track_2a/data
    here = Path(__file__).resolve()
    for candidate in (here.parents[3] / "data", Path("/app/data")):
        if (candidate / "questions.yaml").is_file():
            return str(candidate)
    return str(here.parents[3] / "data")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ZUSAGE_", env_file=".env", extra="ignore")

    # --- LLM (Hack Apertus template variables, no prefix) -----------------
    llm_name: str = Field(default="swiss-ai/Apertus-v1.5-8B", validation_alias=AliasChoices("LLM_NAME"))
    llm_base_url: str = Field(default="", validation_alias=AliasChoices("LLM_BASE_URL"))
    llm_api_key: str = Field(default="", validation_alias=AliasChoices("LLM_API_KEY"))
    llm_timeout_s: float = 18.0
    llm_max_retries: int = 0
    llm_temperature: float = 0.3
    llm_max_tokens: int = 900
    # Some servers reject `response_format`; we detect that once and stop sending it.
    llm_json_mode: bool = True
    # Force the offline coach even if an endpoint is configured (tests, CI).
    offline: bool = False

    # --- storage / runtime ----------------------------------------------
    database_url: str = "sqlite:///./zusage.db"
    data_dir: str = Field(default_factory=_default_data_dir)
    static_dir: str = ""
    secret_key: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    task_key: str = ""
    push_public_key: str = ""
    push_private_key: str = ""
    session_hours: int = 24 * 14
    cookie_secure: bool = False
    seed_demo: bool = True
    isolate_demo: bool = True

    # --- product knobs ---------------------------------------------------
    max_followups_per_interview: int = 3
    max_answer_chars: int = 1500
    transcript_retention_days: int = 180  # FADP data-minimisation default

    @field_validator("llm_name")
    @classmethod
    def aperture_only(cls, value: str) -> str:
        if "apertus" not in value.lower() or "8b" not in value.lower():
            raise ValueError("Zusage requires Apertus 1.5 8B")
        return value

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url) and not self.offline


@lru_cache
def get_settings() -> Settings:
    return Settings()
