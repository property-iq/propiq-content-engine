from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Upstream services
    data_api_base: str = "https://propiq-data-api-429012647952.me-central1.run.app"
    charts_api_base: str = "https://propiq-charts-api-429012647952.me-central1.run.app"
    charts_img_base: str = "https://propiq-charts-img-429012647952.me-central1.run.app"

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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
