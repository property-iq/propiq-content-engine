import os
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Upstream services
    data_api_base: str = "https://propiq-data-api-429012647952.me-central1.run.app"
    charts_api_base: str = "https://propiq-charts-api-429012647952.me-central1.run.app"
    # charts-img is PARKED (ADR 0017 — static PNG rendering moved to the
    # consumer/NAR side). Empty default so the dormant charts client refuses
    # loudly instead of firing a silent HTTP call at a dead prod host. Set this
    # explicitly to re-enable — the park is config-reversible. See issue #17.
    charts_img_base: str = ""

    # LLM — Vertex AI primary, direct Anthropic fallback
    anthropic_api_key: str = ""  # Optional: enables direct API fallback
    anthropic_model: str = "claude-sonnet-4-6"
    vertex_project: str = "crowdproperty-440707"
    vertex_region: str = "us-east5"

    # GCP
    gcp_project: str = "crowdproperty-440707"

    # Paths
    output_dir: Path = Path("./output")
    templates_dir: Path = Path("./templates")

    # Timeouts (seconds)
    http_timeout: float = 30.0

    # Generation auth (see app/auth.py and issue #7).
    # On Cloud Run: mounted from Secret Manager (operator sibling).
    # Locally: leave empty to keep endpoints open for dev convenience.
    content_engine_api_key: str = ""

    @property
    def is_production(self) -> bool:
        """True when running on Cloud Run.

        ``K_SERVICE`` is set automatically by the Cloud Run runtime in every
        container and is unset locally — so this needs no deploy.yml change.
        Read at call time, not import time, so tests can monkeypatch the env.
        """
        return bool(os.environ.get("K_SERVICE"))

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
