"""
LLM client for DESNWORLD - OpenAI-compatible Chat Completions wrapper.

Adapted from MiroFish (https://github.com/666ghj/MiroFish),
backend/app/utils/llm_client.py - Copyright (c) MiroFish authors and
contributors, AGPL-3.0. Modified for DESNWORLD: module path, English
documentation, structured DESNWORLD error types, and provider error mapping
(rate limits, timeouts) so the pipeline can surface actionable failures.

Key behaviours preserved from upstream:
- Cleans reasoning wrappers and Markdown JSON fences from model output.
- Accepts a single complete JSON object even when trailing prose follows,
  never repairs or invents truncated JSON, and rejects multiple JSON values.
- Negotiates `response_format` support once (provider rejection downgrades to
  prompt-only JSON guidance) and retries unusable content a bounded number of
  times without consuming a content attempt for capability negotiation.
"""

import json
import logging
import re
from typing import Optional, Dict, Any, List
from openai import OpenAI

from .config import Config
from .errors import (
    MalformedResponseError,
    MissingCredentialsError,
    ProviderError,
    ProviderTimeoutError,
    RateLimitError,
)
from .openai_chat_compat import create_chat_completion, extract_chat_completion_text


logger = logging.getLogger("desnworld.llm")


# Backwards-compatible alias (upstream name).
LLMResponseError = MalformedResponseError


def _map_provider_error(error: Exception) -> Exception:
    """Map OpenAI SDK transport errors to structured DESNWORLD errors."""

    try:
        import openai as _openai
    except ImportError:  # pragma: no cover - openai is a declared dependency
        return error

    if isinstance(error, _openai.RateLimitError):
        return RateLimitError(
            "The AI provider rate-limited the request after retries were "
            "exhausted. Wait and try again, or reduce request frequency.",
            hint="Rate limits come from the configured LLM_BASE_URL provider.",
        )
    if isinstance(error, _openai.APITimeoutError):
        return ProviderTimeoutError(
            "The AI provider request timed out. Try again, or raise "
            "LLM_TIMEOUT_SECONDS.",
        )
    if isinstance(error, _openai.APIConnectionError):
        return ProviderError(
            "Could not reach the AI provider. Check LLM_BASE_URL connectivity.",
        )
    if isinstance(error, _openai.AuthenticationError):
        return MissingCredentialsError(
            "The AI provider rejected the configured credentials. Check "
            "LLM_API_KEY.",
        )
    if isinstance(error, _openai.APIStatusError):
        return ProviderError(
            f"The AI provider returned HTTP {error.status_code}.",
        )
    return error


def _is_response_format_unsupported(error: Exception) -> bool:
    """Detect an explicit provider rejection of JSON response_format."""

    if getattr(error, "status_code", None) not in {400, 422}:
        return False

    body = getattr(error, "body", None)
    if not isinstance(body, dict):
        return False

    details = body.get("error", body)
    if not isinstance(details, dict):
        return False

    param = str(details.get("param") or "").strip().lower()
    if param == "response_format" or param.startswith("response_format."):
        return True

    message = str(details.get("message") or "").lower()
    if "response_format" not in message:
        return False

    code = str(details.get("code") or "").lower()
    unsupported_codes = {
        "unsupported_parameter",
        "unsupported_value",
        "unknown_parameter",
        "invalid_parameter",
    }
    unsupported_phrases = (
        "not support",
        "unsupported",
        "unknown parameter",
        "unrecognized parameter",
    )
    return code in unsupported_codes or any(
        phrase in message for phrase in unsupported_phrases
    )


def _clean_chat_text(content: str) -> str:
    """Remove common reasoning wrappers and an outer Markdown JSON fence."""

    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
    cleaned = cleaned.lstrip("\ufeff")
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    return cleaned.strip()


def _contains_additional_json_container(content: str) -> bool:
    """Return True when trailing text embeds another JSON object or array."""

    decoder = json.JSONDecoder()
    for match in re.finditer(r"[\[{]", content):
        try:
            value, _ = decoder.raw_decode(content[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, (dict, list)):
            return True
    return False


class LLMClient:
    """LLM客户端"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model = model or Config.LLM_MODEL_NAME
        
        if not self.api_key:
            raise MissingCredentialsError(
                "LLM_API_KEY is not configured. Set it in .env (local runs) or "
                "as a GitHub Actions secret (workflow runs)."
            )
        
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def _create_completion(
        self,
        *,
        messages: List[Dict[str, str]],
        temperature: Optional[float],
        max_tokens: Optional[int],
        response_format: Optional[Dict[str, Any]],
    ) -> Any:
        """Send one raw Chat Completions request through the compatibility layer."""

        try:
            return create_chat_completion(
                self.client,
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception as error:
            mapped = _map_provider_error(error)
            if isinstance(mapped, RateLimitError) and not isinstance(
                error, RateLimitError
            ):
                # Let the caller's retry policy see a retryable error type.
                mapped.__cause__ = error
            raise mapped from error
    
    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        response_format: Optional[Dict] = None
    ) -> str:
        """
        发送聊天请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            response_format: 响应格式（如JSON模式）
            
        Returns:
            模型响应文本
        """
        response = self._create_completion(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        content = extract_chat_completion_text(response)
        return _clean_chat_text(content)
    
    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: Optional[int] = 4096,
        max_attempts: int = 1,
    ) -> Dict[str, Any]:
        """
        发送聊天请求并返回JSON
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数
            max_attempts: 内容生成尝试次数（不含一次明确的JSON模式能力降级）
            
        Returns:
            解析后的JSON对象
        """
        if max_attempts < 1:
            raise ValueError("max_attempts must be at least 1")

        response_format: Optional[Dict[str, str]] = {"type": "json_object"}
        request_max_tokens = max_tokens
        last_error: Optional[LLMResponseError] = None

        for attempt in range(1, max_attempts + 1):
            # JSON-mode capability negotiation is separate from content
            # regeneration. An explicit response_format rejection may add one
            # request, but it must not consume a content attempt.
            while True:
                try:
                    response = self._create_completion(
                        messages=messages,
                        temperature=temperature,
                        max_tokens=request_max_tokens,
                        response_format=response_format,
                    )
                except Exception as error:
                    if (
                        response_format is not None
                        and _is_response_format_unsupported(error)
                    ):
                        logger.warning(
                            "LLM provider explicitly rejected response_format; "
                            "retrying once with prompt-only JSON guidance"
                        )
                        response_format = None
                        continue
                    raise
                break

            try:
                return self._parse_json_response(response)
            except LLMResponseError as error:
                last_error = error
                if attempt >= max_attempts:
                    raise

                # A caller-supplied cap is the common cause of a partial JSON
                # object. Omit it for the one bounded retry so the provider can
                # use its model-specific output limit.
                had_token_cap = request_max_tokens is not None
                request_max_tokens = None
                logger.warning(
                    "LLM returned unusable JSON (finish_reason=%s); "
                    "retrying content generation%s",
                    error.finish_reason or "unknown",
                    " without an output token cap" if had_token_cap else "",
                )

        if last_error is not None:  # pragma: no cover - defensive loop guard
            raise last_error
        raise LLMResponseError("LLM did not produce a JSON response")

    @staticmethod
    def _parse_json_response(response: Any) -> Dict[str, Any]:
        choices = getattr(response, "choices", None) or []
        if not choices:
            raise LLMResponseError("LLM returned no choices")

        choice = choices[0]
        finish_reason = getattr(choice, "finish_reason", None)
        if finish_reason == "length":
            raise LLMResponseError(
                "LLM JSON output was truncated at the token limit",
                finish_reason=finish_reason,
            )
        if finish_reason not in {None, "stop"}:
            raise LLMResponseError(
                f"LLM JSON generation stopped unexpectedly ({finish_reason})",
                finish_reason=finish_reason,
            )

        content = _clean_chat_text(extract_chat_completion_text(response))
        if not content:
            raise LLMResponseError(
                "LLM returned empty JSON content",
                finish_reason=finish_reason,
            )

        try:
            value = json.loads(content)
        except json.JSONDecodeError as strict_error:
            # Some compatible providers append a short explanation after an
            # otherwise complete JSON object. Accept only an object decoded
            # from the beginning; never repair or invent truncated JSON.
            try:
                value, end = json.JSONDecoder().raw_decode(content)
            except json.JSONDecodeError:
                raise LLMResponseError(
                    "LLM returned invalid JSON "
                    f"(line {strict_error.lineno}, column {strict_error.colno})",
                    finish_reason=finish_reason,
                ) from strict_error

            trailing = content[end:].strip()
            if trailing:
                if _contains_additional_json_container(trailing):
                    raise LLMResponseError(
                        "LLM returned multiple JSON values",
                        finish_reason=finish_reason,
                    )
                logger.warning("Ignoring text after a complete LLM JSON object")

        if not isinstance(value, dict):
            raise LLMResponseError(
                "LLM JSON response must be a top-level JSON object",
                finish_reason=finish_reason,
            )

        return value


def parse_json_response(response: Any) -> Dict[str, Any]:
    """Parse a chat completion response into a JSON object.

    Public wrapper around the upstream static parser so tests and callers can
    validate model output handling directly.
    """
    return LLMClient._parse_json_response(response)
