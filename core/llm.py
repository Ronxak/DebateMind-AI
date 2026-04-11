"""LLM wrapper for Groq Chat Completions API."""

from __future__ import annotations

import os
import re
import time
from typing import Any, Dict

import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")


class LLMError(Exception):
    """Raised when an LLM call fails."""


def _candidate_models() -> list[str]:
    """Build ordered model candidates from environment variables."""
    models = [DEFAULT_MODEL.strip()]
    fallback_raw = os.getenv("GROQ_FALLBACK_MODELS", "")
    if fallback_raw:
        models.extend([item.strip() for item in fallback_raw.split(",") if item.strip()])
    # De-duplicate while preserving order.
    return list(dict.fromkeys(models))


def _extract_error_detail(response: requests.Response) -> tuple[str, str]:
    """Return raw detail and parsed message from Groq error payload."""
    raw_detail = ""
    parsed_message = ""
    try:
        raw_detail = response.text or ""
    except Exception:
        raw_detail = ""
    try:
        payload = response.json()
        parsed_message = str(payload.get("error", {}).get("message", "")).strip()
    except Exception:
        parsed_message = ""
    return raw_detail, parsed_message


def _extract_error_code(response: requests.Response) -> str:
    """Return error code from Groq payload when available."""
    try:
        payload = response.json()
        return str(payload.get("error", {}).get("code", "")).strip()
    except Exception:
        return ""


def _extract_retry_delay_seconds(message: str) -> int:
    """Parse retry-after hint from Groq message when present."""
    # Example: "Please try again in 16s"
    match = re.search(r"please\s+try\s+again\s+in\s+(\d+)", message or "", flags=re.IGNORECASE)
    if not match:
        return 0
    return max(0, int(match.group(1)))


def generate(prompt: str) -> str:
    """Generate text from a Groq-hosted chat model.

    Args:
        prompt: Prompt string for the model.

    Returns:
        Clean generated text from the model.

    Raises:
        ValueError: If prompt is empty.
        LLMError: If Groq is unavailable or returns invalid data.
    """
    if not prompt or not prompt.strip():
        raise ValueError("Prompt cannot be empty.")

    api_key = os.getenv("GROQ_API_KEY", "").strip()
    if not api_key:
        raise LLMError("Missing GROQ_API_KEY. Add it to your environment or .env file.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    model_candidates = _candidate_models()
    last_error: Exception | None = None
    last_rate_limit_message = ""

    for model_index, model_name in enumerate(model_candidates):
        response = None
        payload: Dict[str, Any] = {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": prompt.strip(),
                }
            ],
            "temperature": 0.7,
        }
        for attempt, timeout_seconds in enumerate((45, 60), start=1):
            try:
                response = requests.post(
                    GROQ_API_URL,
                    json=payload,
                    headers=headers,
                    timeout=timeout_seconds,
                )
                response.raise_for_status()
                break
            except requests.ConnectionError as exc:
                last_error = exc
                if attempt == 2:
                    raise LLMError(
                        "Could not connect to Groq API. Check your internet connection and try again."
                    ) from exc
                time.sleep(2)
            except requests.Timeout as exc:
                last_error = exc
                if attempt == 2:
                    raise LLMError("Groq request timed out. Please try again.") from exc
                time.sleep(2)
            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 401:
                    raise LLMError("Groq authentication failed. Check GROQ_API_KEY.") from exc
                if exc.response is not None and exc.response.status_code == 400:
                    detail, parsed_message = _extract_error_detail(exc.response)
                    error_code = _extract_error_code(exc.response)
                    if error_code == "model_decommissioned" and model_index < len(model_candidates) - 1:
                        # Skip retired models and try the next configured fallback.
                        break
                    if error_code == "model_decommissioned":
                        raise LLMError(
                            "Configured Groq model is decommissioned. "
                            "Update GROQ_MODEL or GROQ_FALLBACK_MODELS to a currently supported model."
                        ) from exc
                    raise LLMError(f"Groq request failed: {exc}. {detail or parsed_message}".strip()) from exc
                if exc.response is not None and exc.response.status_code == 429:
                    detail, parsed_message = _extract_error_detail(exc.response)
                    wait_match = re.search(r"Please try again in ([^.\n]+)", parsed_message, flags=re.IGNORECASE)
                    wait_hint = f" Retry in about {wait_match.group(1)}." if wait_match else ""
                    last_rate_limit_message = parsed_message or detail or str(exc)
                    has_fallback = model_index < len(model_candidates) - 1
                    retry_delay_seconds = _extract_retry_delay_seconds(last_rate_limit_message)
                    # Respect provider retry hints before giving up on the final model.
                    if not has_fallback and attempt < 2 and retry_delay_seconds > 0:
                        time.sleep(min(retry_delay_seconds + 1, 20))
                        continue
                    if has_fallback:
                        # Try the next model candidate when this one is rate-limited.
                        break
                    if last_rate_limit_message and len(model_candidates) > 1:
                        raise LLMError(
                            "Groq rate limit reached across all configured models."
                            f"{wait_hint} Consider reducing request frequency."
                        ) from exc
                    raise LLMError(
                        "Groq rate limit reached for current model."
                        f"{wait_hint} Set GROQ_FALLBACK_MODELS to try alternates automatically."
                    ) from exc
                detail, _ = _extract_error_detail(exc.response) if exc.response is not None else ("", "")
                raise LLMError(f"Groq request failed: {exc}. {detail}".strip()) from exc
            except requests.RequestException as exc:
                raise LLMError(f"Groq request failed: {exc}") from exc

        # When inner loop exits on 429 with fallback available, response is either None or 429.
        if response is None or response.status_code == 429:
            continue

        try:
            data = response.json()
        except ValueError as exc:
            raise LLMError("Groq returned a non-JSON response.") from exc

        text = data.get("choices", [{}])[0].get("message", {}).get("content")
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Groq returned an empty or invalid response.")
        return text.strip()

    if last_rate_limit_message:
        raise LLMError(f"Groq rate limit reached across all configured models. {last_rate_limit_message}")
    raise LLMError(f"Groq request failed: {last_error}")
