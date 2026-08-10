import re
import sys

import pytest

sys.path.insert(0, ".")

from src.conversation.state import ConversationState
from src.engines.interfaces import DecisionOutput
from src.knowledge.cache import RetrievalCache
from src.knowledge.chunking import split_into_chunks, tokenize
from src.knowledge.embeddings import LocalNgramEmbedder
from src.knowledge.ingest import load_documents
from src.knowledge.kb import KnowledgeBase
from src.knowledge.models import KnowledgeDocument
from src.pipeline import PipelineOrchestrator
from src.planner.engine import MinimalPlanner

DOC = """DR. B.C. ROY ENGINEERING COLLEGE
College Timings: Monday to Friday from 10:00 AM to 5:30 PM. Closed on weekends.
Address: Jemua Road, Fuljhore, Durgapur - 713206, West Bengal.
Fee Structure: The annual tuition fee for ECE is Rs 1,03,000 per year.
Hostel: Boys hostel has single and double sharing rooms with mess and wifi.
Contact: The college office can be reached at 0343-2501353."""


@pytest.fixture
def doc_dir(tmp_path):
    (tmp_path / "college.txt").write_text(DOC, encoding="utf-8")
    return tmp_path


@pytest.fixture
def kb(doc_dir):
    return KnowledgeBase(root_dir=doc_dir / "kb")


# ------------------------------------------------------------------ #
# Ingest / extraction
# ------------------------------------------------------------------ #


def test_ingest_txt(kb, doc_dir):
    added = kb.ingest_paths([doc_dir])
    assert added == 1
    assert kb.document_count == 1
    assert kb.chunk_count >= 1
    assert kb.fingerprint


def test_reingest_same_file_is_noop(kb, doc_dir):
    assert kb.ingest_paths([doc_dir]) == 1
    fp1 = kb.fingerprint
    assert kb.ingest_paths([doc_dir]) == 0
    assert kb.fingerprint == fp1


def test_ingest_updated_file_replaces(kb, doc_dir):
    path = doc_dir / "college.txt"
    kb.ingest_paths([path])
    fp1 = kb.fingerprint
    path.write_text(DOC + "\nNew Library hours: 9 AM to 8 PM.", encoding="utf-8")
    added = kb.ingest_paths([path])
    assert added == 1
    assert kb.fingerprint != fp1
    assert kb.document_count == 1  # edited in place -> replaced, no stale copy
    answer = kb.answer("What are the library hours?")
    assert answer is not None and "9 AM" in answer.text


def test_unsupported_extension(kb, tmp_path):
    bad = tmp_path / "notes.doc"
    bad.write_bytes(b"\x00\x01")
    with pytest.raises(ValueError):
        load_documents(bad)


# ------------------------------------------------------------------ #
# Tokenization / chunking
# ------------------------------------------------------------------ #


def test_tokenize_is_deterministic():
    assert tokenize("Hello, World!") == tokenize("hello world")


def test_chunks_are_sentence_aligned():
    doc = KnowledgeDocument(doc_id="d1", title="t", source="s", text="AAA one. BBB two. CCC three. " * 50)
    chunks = split_into_chunks(doc, max_tokens=30, overlap_tokens=6)
    assert len(chunks) >= 2
    for chunk in chunks:
        assert chunk.text
        # sentence-aligned: starts with an uppercase alpha token or a number
        assert re.match(r"^[A-Za-z0-9]", chunk.text)


# ------------------------------------------------------------------ #
# Embeddings
# ------------------------------------------------------------------ #


def test_embedder_deterministic():
    emb = LocalNgramEmbedder()
    a = emb.embed(["hello world"])
    b = emb.embed(["hello world"])
    assert a == b
    assert len(a[0]) == emb.dim
    assert a[0] != emb.embed(["completely different sentence here"])[0]


def test_embedder_similar_queries_are_close():
    emb = LocalNgramEmbedder()
    v1 = emb.embed(["What is the ECE fee?"])[0]
    v2 = emb.embed(["fee for ECE"])[0]
    v3 = emb.embed(["hostel rules"])[0]
    from src.knowledge.embeddings import cosine

    assert cosine(v1, v2) > cosine(v1, v3)


# ------------------------------------------------------------------ #
# Retrieval / answer
# ------------------------------------------------------------------ #


def test_retrieval_grounded_answer(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    answer = kb.answer("What is the ECE fee?")
    assert answer is not None
    assert "1,03,000" in answer.text
    assert answer.sources == ["college"]
    assert answer.confidence > 0.3


def test_answer_returns_none_without_kb():
    kb = KnowledgeBase(root_dir="data/knowledge", auto_load=False)
    assert kb.answer("anything") is None


def test_answer_ungrounded_query_returns_none(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    # no shared meaningful term -> no grounded answer, caller falls back
    assert kb.answer("What is the weather like in Kolkata?") is None


def test_retrieval_topk(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    result = kb.retrieve("college timings", top_k=2)
    assert len(result.hits) <= 2
    assert result.kb_version == kb.fingerprint


# ------------------------------------------------------------------ #
# Cache
# ------------------------------------------------------------------ #


def test_retrieval_cache_hits(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    first = kb.retrieve("What is the ECE fee?")
    assert first.cached is False
    second = kb.retrieve("What is the ECE fee?")
    assert second.cached is True
    assert second.hits[0].chunk.chunk_id == first.hits[0].chunk.chunk_id


def test_cache_invalidates_on_update(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    kb.retrieve("What is the ECE fee?")
    assert len(kb.cache) == 1
    path = doc_dir / "college.txt"
    path.write_text(DOC + "\nNew Hostel fee: Rs 70,000 per year.", encoding="utf-8")
    kb.ingest_paths([path])
    assert len(kb.cache) == 0
    fresh = kb.retrieve("What is the hostel fee?")
    assert "70,000" in fresh.hits[0].chunk.text or "70,000" in fresh.hits[0].chunk.text


def test_cache_maxsize():
    cache = RetrievalCache(maxsize=2)
    for i in range(5):
        cache.put(f"q{i}", "fp", i)
    assert len(cache) == 2


# ------------------------------------------------------------------ #
# Persistence (JSON parcel)
# ------------------------------------------------------------------ #


def test_persistence_round_trip(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    manifest = kb.index_dir / "manifest.json"
    chunks = kb.index_dir / "chunks.jsonl"
    assert manifest.exists()
    assert chunks.exists()

    reloaded = KnowledgeBase(root_dir=kb.root)
    assert reloaded.document_count == kb.document_count
    assert reloaded.chunk_count == kb.chunk_count
    assert reloaded.fingerprint == kb.fingerprint
    a1 = kb.answer("What is the ECE fee?")
    a2 = reloaded.answer("What is the ECE fee?")
    assert a1 is not None and a2 is not None
    assert a1.text == a2.text


def test_clear(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    kb.clear()
    assert kb.document_count == 0
    assert kb.chunk_count == 0
    assert kb.answer("What is the ECE fee?") is None


# ------------------------------------------------------------------ #
# Brain integration (no-KB path identical; KB path grounded)
# ------------------------------------------------------------------ #


def _fee_decision(query):
    return DecisionOutput(
        action="provide_fee_info",
        confidence=0.9,
        metadata={"student_text": query},
    )


def test_planner_no_kb_keeps_hardcoded_content():
    plan = MinimalPlanner().process(_fee_decision("What is the ECE fee?"))
    from src.planner.engine import _CONTENT_MAP

    assert plan.turns[0].content == _CONTENT_MAP["provide_fee_info_inform"]


def test_planner_with_kb_uses_grounded_answer(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    planner = MinimalPlanner(knowledge=kb)
    plan = planner.process(_fee_decision("What is the ECE fee?"))
    assert "1,03,000" in plan.turns[0].content


def test_planner_with_kb_ungrounded_falls_back(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    planner = MinimalPlanner(knowledge=kb)
    from src.planner.engine import _CONTENT_MAP

    plan = planner.process(_fee_decision("What is the weather in Kolkata?"))
    assert plan.turns[0].content == _CONTENT_MAP["provide_fee_info_inform"]


def test_pipeline_default_has_no_knowledge():
    pipeline = PipelineOrchestrator()
    assert pipeline.knowledge is None


def test_pipeline_optin_kb_answers_from_documents(kb, doc_dir):
    kb.ingest_paths([doc_dir])
    pipeline = PipelineOrchestrator(knowledge=kb)
    result = pipeline.run(
        "What are the college timings?",
        state=ConversationState(session_id="t", profile={}),
    )
    assert result.decision.action == "provide_program_info"
    assert "10:00 AM" in result.plan.turns[0].content
    assert result.knowledge["sources"] == ["college"]
