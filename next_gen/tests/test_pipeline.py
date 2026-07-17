"""Quick test to verify the pipeline works."""

import asyncio
import sys
from pathlib import Path

# Add next_gen to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.models import ChannelMessage, Language
from src.core.pipeline import ConversationPipeline
from src.core.intent import IntentRouter
from src.core.postprocessors import PostProcessor
from src.handlers.fee import FeeHandler
from src.handlers.contact import ContactHandler
from src.handlers.department import DepartmentHandler, HODHandler, PlacementHandler, HostelHandler, ScholarshipHandler, ChatHandler
from src.session.memory import MemorySessionStore
from src.knowledge.loader import get_kb


async def test_structured_handlers():
    """Test that structured handlers return correct answers."""
    session_store = MemorySessionStore()
    intent_router = IntentRouter()
    handlers = [
        FeeHandler(), ContactHandler(), DepartmentHandler(),
        HODHandler(), PlacementHandler(), HostelHandler(),
        ScholarshipHandler(), ChatHandler(),
    ]
    post_processor = PostProcessor()

    # Create a minimal RAG engine (won't be used for structured queries)
    class MockRAG:
        async def retrieve(self, query, lang):
            return []
        async def generate(self, query, context, history, lang):
            from src.core.models import LLMResponse
            return LLMResponse(content="I don't know")

    pipeline = ConversationPipeline(
        session_store=session_store,
        intent_router=intent_router,
        structured_handlers=handlers,
        rag_engine=MockRAG(),
        post_processor=post_processor,
    )

    # Test cases
    test_cases = [
        ("What is the CSE fee?", "fee", "604700"),
        ("Who is the principal?", "principal", "Dr. Sanjay S. Pawar"),
        ("Contact number?", "contact", "0343-2501353"),
        ("CSE placement?", "placement", "93.6%"),
        ("Hostel available?", "hostel", "available"),
        ("Hello", "greeting", "BCREC"),
        ("Weather today?", "ood", "BCREC"),
    ]

    print("Testing structured handlers...")
    for query, expected_intent, expected_keyword in test_cases:
        message = ChannelMessage(
            text=query,
            session_id="test_session",
            channel="test",
        )
        result = await pipeline.process(message)
        print(f"  Query: {query}")
        print(f"    Intent: {result.intent.value} (expected: {expected_intent})")
        print(f"    Source: {result.source.value}")
        print(f"    Latency: {result.latency_ms}ms")
        print(f"    Answer: {result.response.text[:80]}...")
        if expected_keyword.lower() in result.response.text.lower():
            print(f"    ✓ Contains expected keyword")
        else:
            print(f"    ✗ Missing expected keyword: {expected_keyword}")
        print()

    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(test_structured_handlers())
