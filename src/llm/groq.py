import logging
import os

from src.llm.interfaces import LLMResponse

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


class GroqLLM:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = _DEFAULT_MODEL,
    ) -> None:
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model
        self._client = None

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        try:
            from groq import Groq
        except ImportError as err:
            raise ImportError("groq package not installed. Run: pip install groq") from err
        if not self.api_key:
            raise ValueError(
                "GROQ_API_KEY is not set. "
                "Pass api_key to GroqLLM() or set the GROQ_API_KEY environment variable."
            )
        self._client = Groq(api_key=self.api_key)

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self._ensure_client()
        model = kwargs.get("model", self.model)
        temperature = kwargs.get("temperature", 0.3)
        max_tokens = kwargs.get("max_tokens", 384)

        logger.info(
            "GroqLLM.generate model=%s temperature=%s max_tokens=%s prompt_len=%s",
            model, temperature, max_tokens, len(prompt),
        )

        completion = self._client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = (completion.choices[0].message.content or "").strip()
        finish_reason = completion.choices[0].finish_reason or "stop"
        usage: dict[str, int] = {}
        if completion.usage:
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens or 0,
                "completion_tokens": completion.usage.completion_tokens or 0,
                "total_tokens": completion.usage.total_tokens or 0,
            }

        logger.info(
            "GroqLLM response finish=%s usage=%s response_len=%s",
            finish_reason, usage, len(text),
        )
        return LLMResponse(text=text, finish_reason=finish_reason, usage=usage)
