"""
Regression tests for residual v2.1 benchmark mismatches.

Covers confirmed deterministic defects:
  1. 000048 t4: the ``hod`` keyword pattern matched "hod" inside "thodi"
     (no word boundary) making a career-confusion turn flaky.
  2. 000046 t2: a "hostel security + CSE placement" follow-up inside a
     safety conversation hit an exact hostel/placement tie; the committed
     safety topic must survive weak/tied multi-subtopic follow-ups.
  3. 000048 t0-t3: ``career_confusion`` must be answerable generally so an
     empty profile does not block ``provide_career_guidance``.

Plus statefulness coverage:
  4. ``TestSessionIsolation``: cross-turn signal persistence is scoped per
     session, so a shared pipeline (all benchmark conversations through one
     engine) must reproduce fresh-pipe output exactly — 000046 t2 is the
     probe that used to flip to a leaked ``reassure`` action.
  5. ``TestHashSeedDeterminism``: subprocess test asserting intent/action/
     decision output is identical across multiple ``PYTHONHASHSEED`` values.
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


def _run_conv_on(pipe: PipelineOrchestrator, conv: dict) -> list[dict]:
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


def _run_pipeline_turns(conv: dict) -> list[dict]:
    return _run_conv_on(PipelineOrchestrator(), conv)


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


class TestSessionIsolation:
    """Cross-turn signal persistence must be scoped to the session, not the
    engine instance. 000046 t2 is the probe: on a shared pipe (all benchmark
    conversations through one pipeline) it must behave exactly as on a fresh
    pipe, i.e. action `provide_program_info`, not leaked `reassure`."""

    @staticmethod
    def _shared_pipe() -> PipelineOrchestrator:
        pipe = PipelineOrchestrator()
        for path in sorted(BENCH_DIR.glob("*/BENCH_V21_*.json")):
            if path.name == "BENCH_V21_000046.json":
                continue
            _run_conv_on(pipe, json.loads(path.read_text(encoding="utf-8")))
        return pipe

    def test_shared_pipe_matches_fresh_pipe(self):
        conv = _load_conv("admission", "000046")
        baseline = _run_pipeline_turns(conv)
        pipe = self._shared_pipe()
        assert _run_conv_on(pipe, conv) == baseline

    def test_shared_pipe_t2_action_stays_gold(self):
        pipe = self._shared_pipe()
        log = _run_conv_on(pipe, _load_conv("admission", "000046"))
        assert log[2]["intent"] == "safety"
        assert log[2]["action"] == "provide_program_info"

    def test_shared_pipe_t1_signals_match_fresh(self):
        conv = _load_conv("admission", "000046")
        fresh = _run_pipeline_turns(conv)
        pipe = self._shared_pipe()
        shared = _run_conv_on(pipe, conv)
        for i, (a, b) in enumerate(zip(fresh, shared, strict=True)):
            assert a == b, f"turn {i} diverged: fresh={a} shared={b}"


class TestHashSeedDeterminism:
    """Intent/action/decision must be identical across PYTHONHASHSEED values."""

    CHILD = r"""
import json, sys
sys.path.insert(0, {root!r})
from src.pipeline import PipelineOrchestrator
from src.conversation.state import ConversationState

# Order deliberately runs contaminating conversations BEFORE 000046 on the
# shared pipe, so a leaked cross-session state would show up in 000046's turns.
paths = [
    ({career!r}, "000048"),
    ({cutoff!r}, "000014"),
    ({admission!r}, "000046"),
]

def run_all(pipe):
    out = []
    for path, cid in paths:
        conv = json.load(open(path, encoding="utf-8"))
        state = ConversationState(session_id=cid)
        for turn in conv["turns"]:
            result = pipe.run(turn["student"], state)
            out.append([
                result.understanding.intent.primary if result.understanding else None,
                result.decision.action if result.decision else None,
                result.reasoning.current_problem if result.reasoning else None,
            ])
    return out

fresh = run_all(PipelineOrchestrator())
shared = run_all(PipelineOrchestrator())
assert shared == fresh, "shared-pipe output diverges from fresh-pipe output"
json.dump(shared, sys.stdout)
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


class Test000008BudgetSwitchesToFee:
    """000008 t2: revealing a 2L budget must switch scholarship -> fee even
    though the previous-turn scholarship context boost still applies."""

    def test_t2_budget_switches_to_fee(self):
        conv = _load_conv("fees", "000008")
        log = _run_pipeline_turns(conv)
        assert log[2]["intent"] == "fee"
        assert log[2]["action"] == "provide_fee_info"


class Test000009RankNotYetSwitchesToAdmission:
    """000009 t1: 'rank abhi nahi aaya' introduces a pending-rank admission
    question; the previous fee intent must not persist."""

    def test_t1_switches_to_admission(self):
        conv = _load_conv("fees", "000009")
        log = _run_pipeline_turns(conv)
        assert log[1]["intent"] == "admission"
        assert log[1]["action"] == "collect_profile"


class Test000012AnxietyReassurance:
    """000012 t2: 'Can't he get CSE anywhere? Even in round 3?' must route to
    reassure, and the anxiety must decay so t3 ('What about other branches?')
    is NOT re-routed to reassure."""

    def test_t2_reassures(self):
        conv = _load_conv("admission", "000012")
        log = _run_pipeline_turns(conv)
        assert log[2]["intent"] == "admission"
        assert log[2]["action"] == "reassure"

    def test_t3_stays_recommend_branches(self):
        conv = _load_conv("admission", "000012")
        log = _run_pipeline_turns(conv)
        assert log[3]["action"] == "recommend_branches"


class Test000014ChancesBengaliCutoff:
    """000014 t0: 'ki chances ache' (Bengali 'what are the chances') must be a
    cutoff intent, not fall through to admission."""

    def test_t0_is_cutoff(self):
        conv = _load_conv("admission", "000014")
        log = _run_pipeline_turns(conv)
        assert log[0]["intent"] == "cutoff"
        assert log[0]["action"] == "provide_cutoff_info"


class Test000016DepartmentContinuity:
    """000016: 'What about ECE specifically?' must stay department (bare 'call'
    inside 'specifically' must not match contact), and the future-applicant
    admission question must not be blocked by profile collection."""

    def test_t1_what_about_ece_is_department(self):
        conv = _load_conv("admission", "000016")
        log = _run_pipeline_turns(conv)
        assert log[1]["intent"] == "department"
        assert log[1]["action"] == "provide_program_info"

    def test_t2_future_applicant_gets_guidance(self):
        conv = _load_conv("admission", "000016")
        log = _run_pipeline_turns(conv)
        assert log[2]["action"] == "provide_admission_guidance"


class Test000017DocumentsQuestion:
    """000017: the documents question must stay a document intent (the
    admission keyword must not outrank the explicit document question), and
    the future applicant ('not appeared yet') must not be sent to
    collect_profile by the incompleteness guard."""

    def test_t0_documents_question_is_document(self):
        conv = _load_conv("admission", "000017")
        log = _run_pipeline_turns(conv)
        assert log[0]["intent"] == "document"
        assert log[0]["action"] == "provide_program_info"

    def test_t2_future_applicant_gets_guidance(self):
        conv = _load_conv("admission", "000017")
        log = _run_pipeline_turns(conv)
        assert log[2]["action"] == "provide_admission_guidance"


class Test000049GrievanceReassurance:
    """000049 t0: 'This is absolutely unacceptable. The mess ... is a mess'
    must be a grievance routed to reassure (hostel 'mess' keyword must not
    hijack it, and strong emotion must de-escalate first)."""

    def test_t0_is_grievance(self):
        conv = _load_conv("grievance", "000049")
        log = _run_pipeline_turns(conv)
        assert log[0]["intent"] == "grievance"
        assert log[0]["action"] == "reassure"
        assert log[0]["problem"] == "needs_reassurance"
