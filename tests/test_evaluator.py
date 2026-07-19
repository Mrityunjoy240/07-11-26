"""Tests for the benchmark evaluation CLI."""

from pathlib import Path

from scripts.evaluate import (
    check_contains,
    check_field,
    check_must_not,
    evaluate_conversation,
    load_conversation,
    mock_pipeline_result,
)


def _fixture_path(name: str) -> Path:
    return Path("data/benchmark/v0.1") / f"{name}.json"


def test_load_conversation():
    conv = load_conversation(_fixture_path("ADM_LOWRANK_001"))
    assert conv["id"] == "ADM_LOWRANK_001"
    assert len(conv["turns"]) == 4
    assert conv["difficulty"] == 3
    assert conv["expected_end_state"] == "success"


def test_load_nonexistent_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_conversation("NONEXISTENT_001")


def test_check_field_passes():
    actual = {"a": {"b": 42}}
    r = check_field("a.b", 42, actual)
    assert r.passed


def test_check_field_fails():
    actual = {"a": {"b": 42}}
    r = check_field("a.b", 99, actual)
    assert not r.passed
    assert r.expected == 99
    assert r.actual == 42


def test_check_field_missing_key():
    actual = {"a": {"c": 42}}
    r = check_field("a.b", 42, actual)
    assert not r.passed


def test_check_contains_all_found():
    results = check_contains("text", ["hello", "world"], {"text": "hello world"})
    assert all(r.passed for r in results)
    assert len(results) == 2


def test_check_contains_partial():
    results = check_contains("text", ["hello", "missing"], {"text": "hello world"})
    assert results[0].passed
    assert not results[1].passed


def test_must_not_detects_violation():
    violations = check_must_not("CSE is a great branch for you", ["cse"])
    assert "cse" in violations


def test_must_not_passes():
    violations = check_must_not("ME and CE are good options", ["recommend_CSE"])
    assert len(violations) == 0


def test_mock_pipeline_result():
    conv = load_conversation(_fixture_path("ADM_LOWRANK_001"))
    results = mock_pipeline_result(conv)
    assert len(results) == 4
    assert results[0]["understanding"]["facts"]["rank"] == 48000
    assert results[0]["decision"]["action"] == "collect_profile"


def test_evaluate_conversation_with_mock():
    conv = load_conversation(_fixture_path("ADM_LOWRANK_001"))
    mock_results = mock_pipeline_result(conv)
    result = evaluate_conversation(conv, mock_results)
    assert result.conv_id == "ADM_LOWRANK_001"
    assert len(result.turn_results) == 4
    assert result.total_checks > 0
    # Understanding and decision checks should all pass with mock data
    for tr in result.turn_results:
        u = tr.stages.get("understanding")
        if u:
            assert u.score >= 0.5, f"Understanding score too low: {u.score}"


def test_evaluate_all_v0_1():
    """Verify every conversation in v0.1 loads and evaluates without error."""
    directory = Path("data/benchmark/v0.1")
    conv_files = sorted(directory.glob("*.json"))
    assert len(conv_files) >= 5, f"Expected at least 5 conversations, found {len(conv_files)}"
    for f in conv_files:
        conv = load_conversation(f)
        mock_results = mock_pipeline_result(conv)
        result = evaluate_conversation(conv, mock_results)
        assert result.total_checks > 0, f"{conv['id']}: no checks run"
