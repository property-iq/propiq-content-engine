"""Async Claude wrapper with Vertex AI -> direct API fallback.

Strategy: Try Vertex AI first (consolidated GCP billing). If it fails with
rate limit (429) or not found (404), fall back to the direct Anthropic API
when ANTHROPIC_API_KEY is set.

Mirrors the pattern from propiq-reports-api/app/clients/anthropic_client.py.
"""

import json
import logging
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Async Claude wrapper with Vertex AI -> direct API fallback."""

    def __init__(self) -> None:
        self._vertex_client = None
        self._direct_client = None
        self._initialized = False

    def _init_clients(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        import anthropic

        # Primary: Vertex AI (GCP ADC, no key needed)
        try:
            self._vertex_client = anthropic.AsyncAnthropicVertex(
                project_id=settings.vertex_project,
                region=settings.vertex_region,
            )
            logger.info(
                "Vertex AI client ready (project=%s, region=%s)",
                settings.vertex_project,
                settings.vertex_region,
            )
        except Exception as e:
            logger.warning("Failed to initialize Vertex AI client: %s", e)

        # Fallback: Direct Anthropic API (requires key)
        if settings.anthropic_api_key:
            self._direct_client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
            logger.info("Direct Anthropic API client ready (fallback)")

        if not self._vertex_client and not self._direct_client:
            logger.error("No Anthropic client available — LLM generation will fail")

    async def _call_llm(self, system_prompt: str, user_message: str, max_tokens: int = 1024) -> str:
        """Call Claude via Vertex AI with direct API fallback. Returns raw text."""
        import anthropic

        self._init_clients()

        if not self._vertex_client and not self._direct_client:
            raise RuntimeError("No Anthropic client available")

        clients = []
        if self._vertex_client:
            clients.append((self._vertex_client, "vertex"))
        if self._direct_client:
            clients.append((self._direct_client, "direct"))

        last_error = None
        for client, label in clients:
            try:
                response = await client.messages.create(
                    model=settings.anthropic_model,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_message}],
                )
                content = response.content[0].text if response.content else ""
                logger.debug("LLM response via %s (%d tokens)", label, response.usage.output_tokens)
                return content

            except (anthropic.RateLimitError, anthropic.NotFoundError) as e:
                last_error = e
                if self._direct_client and label == "vertex":
                    logger.warning(
                        "Vertex AI %s, falling back to direct API: %s",
                        type(e).__name__,
                        str(e)[:100],
                    )
                    continue
                raise

            except Exception as e:
                last_error = e
                if self._direct_client and label == "vertex":
                    logger.warning(
                        "Vertex AI error, falling back to direct API: %s",
                        str(e)[:100],
                    )
                    continue
                raise

        raise last_error or RuntimeError("All LLM clients failed")


_client: Optional[AnthropicClient] = None


def get_client() -> AnthropicClient:
    global _client
    if _client is None:
        _client = AnthropicClient()
    return _client


async def generate_copy(prompt_template: str, context_data: dict) -> dict:
    """Generate title + body copy using Claude.

    Args:
        prompt_template: The LLM prompt from config.yaml
        context_data: Dict with metrics, headlines, entity info

    Returns:
        {"title": "...", "body": "...", "caption_ig": "...", "caption_x": "..."}
    """
    user_message = f"""Generate content for this data:

{json.dumps(context_data, indent=2, default=str)}

Respond with valid JSON only, no markdown:
{{
    "title": "Bold headline, max 60 chars",
    "body": "3-4 sentences explaining the data trend",
    "caption_ig": "Instagram caption with hashtags (max 2200 chars)",
    "caption_x": "X/Twitter post (max 280 chars)"
}}"""

    client = get_client()
    text = await client._call_llm(
        system_prompt=prompt_template,
        user_message=user_message,
    )

    text = text.strip()
    # Handle potential markdown wrapping
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    return json.loads(text)
