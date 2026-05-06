"""Thin HTTP client for HybrIE v0.1.28.

STT runs locally (HybrIE native Whisper). LLM defaults to local. VLM is cloud-only
— `x-hybrie-cloud-provider: hybrie` resolves to Nebius
(https://api.studio.nebius.ai/v1) per hybrie-server/src/inference_api.rs:61.

v0.1.28 STT additions surfaced here:
  - word-level timestamps (pure-Rust DTW) via ``word_timestamps=True``
  - prompt conditioning (``prompt=...``) to bias decoding toward proper nouns
  - segment confidence (``avg_logprob``, ``no_speech_prob``, ``compression_ratio``)
    flow through verbose_json automatically — no API change required here.

The agent should reach for its own vision first when it has multimodal capability;
this client's vision() is the fallback path for text-only runtimes.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any, Iterable

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8001"
DEFAULT_API_KEY = "hybrie"
DEFAULT_STT_MODEL = "openai/whisper-large-v3-turbo"
DEFAULT_LLM_MODEL = "Qwen/Qwen3.5-9B-Instruct"
DEFAULT_VLM_MODEL_FALLBACK = "Qwen/Qwen2.5-VL-72B-Instruct"


class HybrieError(RuntimeError):
    """HybrIE rejected the request or is not running."""


class HybrieClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: float = 600.0,
    ) -> None:
        self.base_url = (base_url or os.environ.get("HYBRIE_API_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.api_key = api_key or os.environ.get("HYBRIE_API_KEY") or DEFAULT_API_KEY
        self._http = httpx.Client(timeout=timeout)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "HybrieClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    # ---- low-level ------------------------------------------------------

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if extra:
            headers.update(extra)
        return headers

    def _raise(self, response: httpx.Response, action: str) -> None:
        body = response.text[:500] if response.text else ""
        raise HybrieError(
            f"HybrIE {action} failed: HTTP {response.status_code} {response.reason_phrase} — {body}"
        )

    # ---- diagnostics ----------------------------------------------------

    def health(self) -> dict[str, Any]:
        try:
            r = self._http.get(f"{self.base_url}/v1/health", headers=self._headers())
        except httpx.ConnectError as e:
            raise HybrieError(
                f"Cannot reach HybrIE at {self.base_url}. Is the server running? "
                "See install.md → 'Start HybrIE'. ({e})"
            ) from e
        if not r.is_success:
            self._raise(r, "health")
        return r.json()

    def list_models(self) -> list[dict[str, Any]]:
        r = self._http.get(f"{self.base_url}/v1/models", headers=self._headers())
        if not r.is_success:
            self._raise(r, "list_models")
        payload = r.json()
        return payload.get("data", payload) if isinstance(payload, dict) else payload

    # ---- STT (local Whisper) -------------------------------------------

    def transcribe(
        self,
        audio_path: Path,
        *,
        model: str | None = None,
        language: str | None = None,
        response_format: str = "verbose_json",
        temperature: float | None = None,
        prompt: str | None = None,
        word_timestamps: bool = False,
    ) -> dict[str, Any]:
        """Multipart POST /v1/audio/transcriptions.

        Always requests ``timestamp_granularities[]=segment``. When
        ``word_timestamps=True`` (HybrIE v0.1.28+), additionally requests
        ``timestamp_granularities[]=word`` so the response carries a populated
        ``words: [{word, start, end}]`` array via DTW alignment.

        ``prompt`` (v0.1.28+) biases Whisper decoding toward the supplied
        free-text — useful for proper nouns, project names, jargon.
        """
        audio_path = Path(audio_path)
        if not audio_path.is_file():
            raise FileNotFoundError(audio_path)

        mime = mimetypes.guess_type(audio_path.name)[0] or "application/octet-stream"
        files = [("file", (audio_path.name, audio_path.read_bytes(), mime))]
        data: list[tuple[str, str]] = [
            ("model", model or DEFAULT_STT_MODEL),
            ("response_format", response_format),
            ("timestamp_granularities[]", "segment"),
        ]
        if word_timestamps:
            data.append(("timestamp_granularities[]", "word"))
        if language:
            data.append(("language", language))
        if temperature is not None:
            data.append(("temperature", str(temperature)))
        if prompt:
            data.append(("prompt", prompt))

        r = self._http.post(
            f"{self.base_url}/v1/audio/transcriptions",
            headers=self._headers(),
            files=files,
            data=data,
        )
        if not r.is_success:
            self._raise(r, "transcribe")
        return r.json()

    # ---- LLM chat -------------------------------------------------------

    def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        model: str | None = None,
        response_format: dict[str, str] | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        execution_mode: str = "local",
        cloud_provider: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": model or DEFAULT_LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if max_tokens is not None:
            body["max_tokens"] = max_tokens

        extra = {"x-hybrie-execution-mode": execution_mode}
        if cloud_provider:
            extra["x-hybrie-cloud-provider"] = cloud_provider

        r = self._http.post(
            f"{self.base_url}/v1/chat/completions",
            headers=self._headers({**extra, "Content-Type": "application/json"}),
            content=json.dumps(body),
        )
        if not r.is_success:
            self._raise(r, "chat")
        return r.json()

    @staticmethod
    def chat_text(response: dict[str, Any]) -> str:
        choices = response.get("choices") or []
        if not choices:
            return ""
        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return content or ""

    # ---- VLM (cloud-only fallback) -------------------------------------

    def vision(
        self,
        prompt: str,
        image_paths: Iterable[Path],
        *,
        model: str | None = None,
        cloud_provider: str = "hybrie",
        detail: str = "high",
    ) -> str:
        """Send images + prompt to a multimodal model via HybrIE cloud routing.

        Use only when the host agent has no native vision. Default cloud_provider
        ``hybrie`` routes via Nebius. Pass ``openai`` / ``anthropic`` / ``gemini``
        if you have those keys configured on the HybrIE server.
        """
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for path in image_paths:
            path = Path(path)
            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            data = base64.b64encode(path.read_bytes()).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{mime};base64,{data}", "detail": detail},
                }
            )
        response = self.chat(
            messages=[{"role": "user", "content": content}],
            model=model or DEFAULT_VLM_MODEL_FALLBACK,
            execution_mode="cloud",
            cloud_provider=cloud_provider,
        )
        return self.chat_text(response)


# ---- module-level convenience ---------------------------------------

_default_client: HybrieClient | None = None


def get_client() -> HybrieClient:
    global _default_client
    if _default_client is None:
        _default_client = HybrieClient()
    return _default_client
