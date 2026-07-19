from src.llm.interfaces import LLMResponse


class MockLLM:
    def __init__(self, response: str = "") -> None:
        self._response = response
        self.last_prompt: str = ""

    def generate(self, prompt: str, **kwargs) -> LLMResponse:
        self.last_prompt = prompt
        return LLMResponse(
            text=self._response or "This is a mock LLM response for testing purposes.",
            finish_reason="stop",
            usage={"prompt_tokens": len(prompt) // 4, "completion_tokens": 50},
        )
