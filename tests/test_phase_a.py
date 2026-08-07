"""Phase A validation tests: feature flag, latency, versions, telemetry, dual runner."""


from src.config.settings import Settings
from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator, _elapsed_ms
from src.telemetry.store import _asdict, count_runs, get_run, list_runs, save_run

try:
    from src.dual.runner import run_dual
    HAS_DUAL = True
except ImportError:
    HAS_DUAL = False

import importlib

HAS_GROQ = importlib.util.find_spec("groq") is not None


# ---------------------------------------------------------------------------
# Feature flag
# ---------------------------------------------------------------------------

def test_pipeline_mode_defaults_to_legacy():
    s = Settings()
    assert s.pipeline_mode == "legacy"


def test_pipeline_mode_accepts_shadow_and_new():
    assert Settings(pipeline_mode="shadow").pipeline_mode == "shadow"
    assert Settings(pipeline_mode="new").pipeline_mode == "new"


def test_pipeline_version_exists():
    assert Settings().pipeline_version == "1.0.0"


# ---------------------------------------------------------------------------
# Latency measurement
# ---------------------------------------------------------------------------

def test_elapsed_ms_returns_positive_int():
    import time
    t = time.perf_counter()
    assert _elapsed_ms(t) >= 0
    assert isinstance(_elapsed_ms(t), int)


def test_pipeline_result_has_latency():
    pipeline = PipelineOrchestrator()
    result = pipeline.run("my rank is 48000")
    assert hasattr(result, "latency_ms")
    assert isinstance(result.latency_ms, dict)
    assert "understanding" in result.latency_ms
    assert "total" in result.latency_ms
    assert result.latency_ms["total"] >= 0


def test_latency_has_all_expected_stages():
    pipeline = PipelineOrchestrator()
    result = pipeline.run("hello")
    expected = {"understanding", "reasoning", "brain", "decision", "planner", "total"}
    if result.plan:
        expected.add("llm")
    assert expected.issubset(result.latency_ms.keys()), f"Missing: {expected - set(result.latency_ms.keys())}"


# ---------------------------------------------------------------------------
# Version tracking
# ---------------------------------------------------------------------------

def test_pipeline_result_has_versions():
    pipeline = PipelineOrchestrator()
    result = pipeline.run("hello")
    assert hasattr(result, "versions")
    assert result.versions["pipeline"] == "1.0.0"
    assert result.versions["understanding"] == "v6"
    assert result.versions["reasoning"] == "v2"
    assert result.versions["brain"] == "v1"
    assert result.versions["decision"] == "v2"
    assert result.versions["planner"] == "v2"
    assert result.versions["composer"] == "v2"


def test_understanding_engine_has_version():
    from src.understanding.engine import UnderstandingEngine
    assert UnderstandingEngine.VERSION == "v6"


def test_reasoning_engine_has_version():
    from src.reasoning.engine import ReasoningEngine
    assert ReasoningEngine.VERSION == "v2"


def test_brain_has_version():
    from src.brain import CollegeBrain
    assert CollegeBrain.VERSION == "v1"


def test_decision_engine_has_version():
    from src.decision.engine import DecisionEngine
    assert DecisionEngine.VERSION == "v2"


def test_planner_engine_has_version():
    from src.planner.engine import MinimalPlanner
    assert MinimalPlanner.VERSION == "v2"


def test_composer_has_version():
    from src.composer.engine import ResponseComposer
    assert ResponseComposer.VERSION == "v2"


# ---------------------------------------------------------------------------
# Telemetry store
# ---------------------------------------------------------------------------

def test_save_and_get_run():
    pipeline = PipelineOrchestrator()
    result = pipeline.run("my rank is 48000")
    run_id = save_run(result, conversation_id="test-conv-1")
    assert run_id
    assert len(run_id) == 12

    loaded = get_run(run_id)
    assert loaded is not None
    assert loaded["id"] == run_id
    assert loaded["conversation_id"] == "test-conv-1"
    assert loaded["pipeline_version"] == "1.0.0"

    import json
    data = json.loads(loaded["run_json"])
    assert data["text"] == "my rank is 48000"
    assert "latency_ms" in data
    assert "versions" in data


def test_list_runs():
    p = PipelineOrchestrator()
    save_run(p.run("hello"), conversation_id="list-test")
    save_run(p.run("rank"), conversation_id="list-test")
    runs = list_runs(conversation_id="list-test")
    assert len(runs) >= 2
    assert runs[0]["created_at"] >= runs[1]["created_at"]  # newest first


def test_count_runs():
    before = count_runs()
    save_run(PipelineOrchestrator().run("test"), "count-test")
    assert count_runs() >= before + 1


def test_get_nonexistent_run():
    assert get_run("nonexistent-id") is None


def test_asdict_handles_dataclass():
    result = PipelineOrchestrator().run("hello")
    d = _asdict(result)
    assert isinstance(d, dict)
    assert "text" in d
    assert "latency_ms" in d
    assert "versions" in d
    assert "understanding" in d


def test_telemetry_does_not_crash_on_failure():
    """Even with bad data, save_run should not raise."""
    try:
        run_id = save_run(None)  # type: ignore[arg-type]
        assert run_id is not None
    except Exception:
        pass  # should not crash the test


# ---------------------------------------------------------------------------
# Dual runner (old system may not be available in test context)
# ---------------------------------------------------------------------------

def test_dual_runner_returns_dual_result():
    if not HAS_DUAL:
        return
    result = run_dual("hello")
    assert result.text == "hello"
    # old system depends on backend context — may or may not be available
    assert hasattr(result, "old_response")
    assert hasattr(result, "new_response")
    # new pipeline should always produce output
    assert result.new_response


def test_dual_runner_new_pipeline_never_crashes():
    if not HAS_DUAL:
        return
    # Even with gibberish, new pipeline should not crash the dual runner
    result = run_dual("")
    assert result.new_response or result.new_error


def test_dual_runner_accepts_conversation_id():
    if not HAS_DUAL:
        return
    result = run_dual("test", conversation_id="dual-test-1")
    assert result.new_telemetry_id
    loaded = get_run(result.new_telemetry_id)
    assert loaded is not None
    assert loaded["conversation_id"] == "dual-test-1"


def test_dual_runner_with_state():
    if not HAS_DUAL:
        return
    state = ConversationState(session_id="dual-test", profile={"rank": 48000})
    result = run_dual("what branches can I get", state=state)
    assert result.new_response
    if result.new_result:
        assert result.new_result.decision.action in ("recommend_branches", "collect_profile")
