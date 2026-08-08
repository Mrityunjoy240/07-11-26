"""
Regression tests for residual v2.1 benchmark mismatches.

Covers three confirmed deterministic defects:
  1. 000048 t4: the ``hod`` keyword pattern matched "hod" inside "thodi"
     (no word boundary) making a career-confusion turn flaky.
  2. 000046 t2: a "hostel security + CSE placement" follow-up inside a
     safety conversation hit an exact hostel/placement tie; the committed
     safety topic must survive weak/tied multi-subtopic follow-ups.
  3. 000048 t0-t3: ``career_confusion`` must be answerable generally so an
     empty profile does not block ``provide_career_guidance``.

Plus a subprocess test asserting intent/action/decision output is identical
across multiple ``PYTHONHASHSEED`` values.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.conversation.state import ConversationState
from src.pipeline import PipelineOrchestrator
from src.reasoning.engine import ANSWERABLE_GENERALLY

REPO_ROOT = Path(__file__).resolve().parents[1]
BENCH_DIR = REPO_ROOT / "data" / "benchmark" / "conversations"


def _load_conv(domain: str, conv_id: str) -> dict:
    path = BENCH_DIR / domain / f"BENCH_V21_{conv_id}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _run_pipeline_turns(conv: dict) -> list[dict]:
    pipe = PipelineOrchestrator()
    state = ConversationState(session_id=conv["id"])
    out: list[dict] = []
    for turn in conv["turns"]:
        result = pipe.run(turn["student"], state)
        out.append({
            "intent": result.understanding.intent.primary if result.understanding else None,
            "action": result.decision.action if result.decision else None,
            "problem": result.reasoning.current_problem if result.reasoning else None,
        })
    return out


class Test000046SafetyPersistence:
    """000046 t2: hostel/placement tie must not hijack a safety conversation."""

    def test_t2_safety_persists(self):
        conv = _load_conv("admission", "000046")
        log = _run_pipeline_turns(conv)
        assert log[2]["intent"] == "safety"
        assert log[2]["action"] == "provide_program_info"

    def test_all_turns_match_gold_intent(self):
        conv = _load_conv("admission", "000046")
        log = _run_pipeline_turns(conv)
        for i, (turn, entry) in enumerate(zip(conv["turns"], log, strict=True)):
            gold = turn["expected"]["understanding"]["intent"]
            assert entry["intent"] == gold, f"turn {i}: got {entry['intent']} want {gold}"


class Test000048CareerConfusion:
    """000048 t0-t4: career_confusion intent/action, incl. the thodi fix."""

    def test_t0_through_t4_match_gold(self):
        conv = _load_conv("career", "000048")
        log = _run_pipeline_turns(conv)
        # t5 is a frozen spec decision (career-vs-admission persistence).
        for i, (turn, entry) in enumerate(zip(conv["turns"][:5], log[:5], strict=True)):
            gold_intent = turn["expected"]["understanding"]["intent"]
            gold_action = turn["expected"]["decision"]["action"]
            assert entry["intent"] == gold_intent, f"turn {i}: got {entry['intent']} want {gold_intent}"
            assert entry["action"] == gold_action, f"turn {i}: got {entry['action']} want {gold_action}"

    def test_thodi_does_not_match_hod(self):
        conv = _load_conv("career", "000048")
        pipe = PipelineOrchestrator()
        state = ConversationState(session_id="thodi")
        for turn in conv["turns"][:4]:
            pipe.run(turn["student"], state)
        result = pipe.run(conv["turns"][4]["student"], state)
        assert result.understanding.intent.primary == "career_confusion"

    def test_career_confusion_answerable_generally(self):
        assert "career_confusion" in ANSWERABLE_GENERALLY


class Test000014CutoffSwitch:
    """000014 t1: a clear new "IT cutoff" question must switch away from the
    committed topic even when both are weak (tie-break vs persistence)."""

    def test_t1_switches_to_cutoff(self):
        conv = _load_conv("admission", "000014")
        log = _run_pipeline_turns(conv)
        assert log[1]["intent"] == "cutoff"
        assert log[1]["action"] == "provide_cutoff_info"


class TestHashSeedDeterminism:
    """Intent/action/decision must be identical across PYTHONHASHSEED values."""

    CHILD = r"""
import json, sys
sys.path.insert(0, {root!r})
from src.pipeline import PipelineOrchestrator
from src.conversation.state import ConversationState
convs = [
    ({admission!r}, "000046"),
    ({career!r}, "000048"),
    ({cutoff!r}, "000014"),
]
out = []
for path, cid in convs:
    conv = json.load(open(path, encoding="utf-8"))
    pipe = PipelineOrchestrator()
    state = ConversationState(session_id=cid)
    for turn in conv["turns"]:
        result = pipe.run(turn["student"], state)
        out.append([
            result.understanding.intent.primary if result.understanding else None,
            result.decision.action if result.decision else None,
            result.reasoning.current_problem if result.reasoning else None,
        ])
json.dump(out, sys.stdout)
"""

    @staticmethod
    def _run_seed(seed: str) -> list:
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        child = TestHashSeedDeterminism.CHILD.format(
            root=str(REPO_ROOT),
            admission=str(BENCH_DIR / "admission" / "BENCH_V21_000046.json").replace("\\", "/"),
            career=str(BENCH_DIR / "career" / "BENCH_V21_000048.json").replace("\\", "/"),
            cutoff=str(BENCH_DIR / "admission" / "BENCH_V21_000014.json").replace("\\", "/"),
        )
        proc = subprocess.run(
            [sys.executable, "-c", child],
            capture_output=True, text=True, check=True, env=env, cwd=str(REPO_ROOT),
        )
        return json.loads(proc.stdout)

    @pytest.mark.parametrize("seed", ["1", "2", "3", "4"])
    def test_output_identical_across_seeds(self, seed):
        baseline = self._run_seed("1")
        actual = self._run_seed(seed)
        assert actual == baseline, f"output differs under PYTHONHASHSEED={seed}"
