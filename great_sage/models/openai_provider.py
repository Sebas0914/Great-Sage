import json
import logging
from typing import Iterator, List

import requests

from great_sage.models.base import Message, ModelProvider, ModelProviderError

log = logging.getLogger(__name__)

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"


class OpenAIProvider(ModelProvider):
    def __init__(
        self,
        api_key: str,
        model: str = "",
        timeout: int = 90,
        base_url: str = OPENAI_API_URL,
        provider_name: str = "OpenAI",
    ):
        if not api_key:
            raise ModelProviderError(
                "No %s API key is set." % provider_name
            )

        self.api_key = api_key
        self.model = model or DEFAULT_MODEL
        self.timeout = timeout
        self.base_url = base_url
        self.provider_name = provider_name

    @staticmethod
    def supports_tools() -> bool:
        return True

    def _headers(self):
        return {
            "Authorization": "Bearer " + self.api_key,
            "Content-Type": "application/json",
        }

    def _convert(self, messages: List[Message]):
        out = []

        for m in messages:
            role = m.get("role")
            content = m.get("content", "")
            images = m.get("images")

            if role == "tool":
                out.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id") or "call_1",
                    "content": str(content),
                })
                continue

            if images:
                parts = [{"type": "text", "text": content or ""}]

                for img in images:
                    parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/jpeg;base64," + img
                        },
                    })

                out.append({
                    "role": role or "user",
                    "content": parts,
                })
                continue

            entry = {
                "role": role or "user",
                "content": content,
            }

            if m.get("tool_calls"):
                entry["tool_calls"] = m["tool_calls"]

            out.append(entry)

        return out

    def _fail(self, exc, response=None):
        name = self.provider_name

        if response is not None:
            if response.status_code == 401:
                return ModelProviderError(
                    "%s rejected the API key. Check it in AI settings."
                    % name
                )

            if response.status_code == 429:
                return ModelProviderError(
                    "%s rate limit reached. Try again shortly."
                    % name
                )

            return ModelProviderError(
                "%s returned HTTP %s."
                % (name, response.status_code)
            )

        return ModelProviderError(
            "Could not reach %s: %s"
            % (name, type(exc).__name__)
        )

    def _post(self, body, stream=False):
        try:
            r = requests.post(
                self.base_url,
                headers=self._headers(),
                json=body,
                timeout=self.timeout,
                stream=stream,
            )
        except Exception as exc:
            raise self._fail(exc) from exc

        if r.status_code != 200:
            raise self._fail(None, r)

        return r

    def send_message(self, messages: List[Message]) -> str:
        r = self._post({
            "model": self.model,
            "messages": self._convert(messages),
        })

        try:
            return r.json()["choices"][0]["message"].get("content") or ""
        except Exception as exc:
            raise ModelProviderError(
                "%s returned an unexpected response format."
                % self.provider_name
            ) from exc

    def chat_raw(self, messages, tools=None):
        body = {
            "model": self.model,
            "messages": self._convert(messages),
        }

        if tools:
            body["tools"] = tools

        r = self._post(body)

        try:
            msg = r.json()["choices"][0]["message"]
        except Exception as exc:
            raise ModelProviderError(
                "%s returned an unexpected response format."
                % self.provider_name
            ) from exc

        out = {
            "role": "assistant",
            "content": msg.get("content") or "",
        }

        calls = msg.get("tool_calls") or []

        if calls:
            out["tool_calls"] = [
                {
                    "id": c.get("id"),
                    "function": {
                        "name": (c.get("function") or {}).get("name"),
                        "arguments": _parse_args(
                            (c.get("function") or {}).get("arguments")
                        ),
                    },
                }
                for c in calls
            ]

        return out

    def stream_response(self, messages: List[Message]) -> Iterator[str]:
        body = {
            "model": self.model,
            "messages": self._convert(messages),
            "stream": True,
        }

        if self.provider_name.lower() == "nvidia":
            body["max_tokens"] = 300
            body["reasoning_effort"] = "low"

        r = self._post(body, stream=True)

        for line in r.iter_lines():
            if not line or not line.startswith(b"data:"):
                continue

            payload = line[5:].strip()

            if payload in (b"", b"[DONE]"):
                continue

            try:
                delta = json.loads(payload)["choices"][0].get("delta") or {}
            except Exception:
                continue

            text = delta.get("content")

            if text:
                yield text

    def get_available_models(self) -> List[str]:
        return [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4.1-mini",
        ]


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw

    try:
        return json.loads(raw or "{}")
    except Exception:
        return {}

