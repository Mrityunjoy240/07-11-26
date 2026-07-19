#!/usr/bin/env python3
"""Unified benchmark validator for conversation quality, coverage, and balance.

Usage:
    python scripts/benchmark_validate.py --version v2.0 --schema     # validate v2.0 with v2 schema
    python scripts/benchmark_validate.py --version v1.1 --schema     # validate v1.1 with v1 schema
    python scripts/benchmark_validate.py --all-versions              # validate each version separately
    python scripts/benchmark_validate.py --version v2.0 --all        # all checks on v2.0
    python scripts/benchmark_validate.py --version v2.0 --regression --run  # run pipeline
"""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ── Constants ────────────────────────────────────────────────────────────────

BENCHMARK_DIR = Path("data/benchmark")
CONVERSATIONS_DIR = BENCHMARK_DIR / "conversations"
VERSIONS_DIR = BENCHMARK_DIR / "versions"
SCHEMA_DIR = BENCHMARK_DIR / "schema"
EVAL_DIR = BENCHMARK_DIR / "evaluation"

VALID_DOMAINS = {
    "admission", "fees", "hostel", "placement", "scholarship",
    "management", "sports", "nri", "lateral", "transfer",
    "distance", "counseling", "grievance", "mixed", "multilingual",
}

VALID_FEATURES = {
    "correction", "topic_switch", "missing_info", "adversarial",
    "parent_mode", "emotion", "language_switch", "noisy_input",
}

VALID_LANGUAGES = {
    "en", "hi", "bn", "te", "ta", "mr", "gu", "kn", "ml", "pa", "ur", "other",
}

VALID_INTENTS = {
    "admission", "fee", "placement", "hostel", "scholarship",
    "grievance", "counseling", "nri_admission", "management_quota",
    "sports_quota", "lateral_entry", "transfer", "distance_education",
    "career_confusion", "general", "unknown",
}

VALID_DECISION_ACTIONS = {
    "collect_profile", "encourage_and_collect_profile", "recommend_branches",
    "provide_admission_info", "provide_fee_info", "provide_placement_info",
    "provide_hostel_info", "provide_scholarship_info", "provide_career_guidance",
    "provide_counseling_schedule", "escalate_to_human", "explain_management_quota_policy",
    "provide_grievance_process", "provide_transfer_info", "provide_nri_admission_info",
    "provide_branch_guidance", "provide_sports_info", "provide_distance_ed_info",
    "provide_lateral_entry_info", "provide_sports_quota_info", "clarify",
}

VALID_PLANNER_ACTIONS = {
    "recommend", "ask", "inform", "reassure", "encourage",
    "listen", "clarify", "summarize", "escalate",
}

VALID_STAGES = {"discovery", "exploration", "comparison", "decision", "post_admission"}

VALID_CURRENT_PROBLEMS = {
    "needs_admission_guidance", "needs_profile_completion",
    "needs_fee_information", "needs_placement_data",
    "needs_hostel_info", "expressing_anxiety",
    "comparing_options", "has_management_query",
    "has_transfer_query", "has_grievance", "general_inquiry",
}

# Domain-to-directory mapping
DOMAIN_DIR_MAP = {
    "admission": "admission", "fees": "fees", "hostel": "hostel",
    "placement": "placement", "scholarship": "scholarship",
    "management": "management", "sports": "sports", "nri": "nri",
    "lateral": "lateral", "transfer": "transfer", "distance": "distance",
    "counseling": "counseling", "grievance": "grievance",
    "mixed": "mixed", "multilingual": "multilingual",
}

FILLER_WORDS = {
    "like", "know", "more", "next", "any", "question", "help",
    "think", "just", "also", "very", "really", "well", "okay",
    "yes", "no", "right", "um", "uh", "hmm", "actually",
}


# ── Utility ──────────────────────────────────────────────────────────────────

# Map manifest schema field to schema file
SCHEMA_MAP = {
    "v1": SCHEMA_DIR / "conversation_v0.1.schema.json",
    "v2": SCHEMA_DIR / "conversation_v2.schema.json",
}

# Map legacy conversation IDs to their file locations
LEGACY_ID_TO_PATH: dict[str, Path] = {}


def _build_legacy_index():
    """Index legacy conversations (v0.1/v0.2 directories) by ID."""
    if LEGACY_ID_TO_PATH:
        return
    for version_dir in sorted(BENCHMARK_DIR.iterdir()):
        if not version_dir.is_dir():
            continue
        if not re.match(r"^v\d+\.\d+$", version_dir.name):
            continue
        for f in sorted(version_dir.glob("*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cid = data.get("id", "")
                if cid:
                    LEGACY_ID_TO_PATH[cid] = f
            except (json.JSONDecodeError, KeyError):
                pass


def _find_conversation_file(conv_id: str) -> Path | None:
    """Find a conversation file by ID. Checks conversations/ dir, then legacy v*/ dirs."""
    # New structure: conversations/<domain>/<id>.json
    if CONVERSATIONS_DIR.exists():
        for domain_dir in CONVERSATIONS_DIR.iterdir():
            if domain_dir.is_dir():
                f = domain_dir / f"{conv_id}.json"
                if f.exists():
                    return f
    # Legacy structure: v0.1/<id>.json, v0.2/<id>.json
    _build_legacy_index()
    return LEGACY_ID_TO_PATH.get(conv_id)


def load_version(version: str) -> tuple[dict, list[dict], list[str]]:
    """Load a version manifest and its conversations.

    Returns: (manifest, conversations, errors)
    """
    manifest_path = VERSIONS_DIR / f"{version}.json"
    if not manifest_path.exists():
        return {}, [], [f"Manifest not found: {manifest_path}"]

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    conv_ids = manifest.get("conversations", [])
    schema_key = manifest.get("schema", "v2")

    convs = []
    errors = []
    for cid in conv_ids:
        f = _find_conversation_file(cid)
        if f is None:
            errors.append(f"  {cid}: file not found (referenced in {version})")
            continue
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            data["_path"] = str(f)
            data["_manifest"] = version
            convs.append(data)
        except json.JSONDecodeError as e:
            errors.append(f"  {cid}: invalid JSON in {f}: {e}")

    return manifest, convs, errors


def load_all_versions() -> list[tuple[dict, list[dict], list[str]]]:
    """Load all version manifests and their conversations."""
    results = []
    for manifest_file in sorted(VERSIONS_DIR.glob("*.json")):
        version = manifest_file.stem
        manifest, convs, errors = load_version(version)
        if manifest:
            results.append((manifest, convs, errors))
    return results


def checksum(data: Any) -> str:
    """SHA-256 of JSON-serialized data (sorted keys, no whitespace)."""
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def difficulty_label(level: int) -> str:
    """Derive human-readable label from difficulty number."""
    labels = {
        1: "faq", 2: "single_turn", 3: "profile_building",
        4: "multi_turn", 5: "memory_contradiction",
        6: "emotion_recommendation", 7: "everything",
    }
    return labels.get(level, "unknown")


# ── SchemaValidator ──────────────────────────────────────────────────────────

class SchemaValidator:
    """Validates conversations against JSON schema."""

    def __init__(self, schema_path: Path | None = None):
        self.schema_path = schema_path
        self._validator = None
        self._schema_key = None

    def set_schema(self, schema_key: str):
        """Set schema from manifest's schema field (e.g. 'v1', 'v2')."""
        path = SCHEMA_MAP.get(schema_key)
        if path and path.exists():
            self.schema_path = path
            self._validator = None  # reset cached validator
            self._schema_key = schema_key
        else:
            raise ValueError(f"Unknown schema key '{schema_key}', no file in SCHEMA_MAP")

    def _get_validator(self):
        if self._validator is None:
            import jsonschema
            if self.schema_path is None:
                self.schema_path = SCHEMA_MAP.get("v2", SCHEMA_DIR / "conversation_v2.schema.json")
            schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
            self._validator = jsonschema.Draft202012Validator(schema)
        return self._validator

    def validate(self, conv: dict) -> list[str]:
        errors = []
        validator = self._get_validator()
        for error in sorted(validator.iter_errors(conv), key=lambda e: list(e.absolute_path)):
            path = ".".join(str(p) for p in error.absolute_path)
            errors.append(f"  {path or '(root)'}: {error.message}")
        return errors


# ── MetadataValidator ────────────────────────────────────────────────────────

class MetadataValidator:
    """Validates metadata fields, features, languages, domain consistency."""

    def validate(self, conv: dict) -> list[str]:
        errors = []
        meta = conv.get("metadata", conv)  # v2 has top-level metadata fields

        # Domain check
        domain = conv.get("domain", "")
        if domain not in VALID_DOMAINS:
            errors.append(f"  domain: '{domain}' not in valid set")
        domain_dir = conv.get("_domain_dir", "")
        expected_dir = DOMAIN_DIR_MAP.get(domain, "")
        if domain_dir and expected_dir and domain_dir != expected_dir:
            errors.append(f"  domain='{domain}' but file is in '{domain_dir}/' (expected '{expected_dir}/')")

        # Features check
        for feat in conv.get("features", []):
            if feat not in VALID_FEATURES:
                errors.append(f"  features: '{feat}' not in valid set")

        # Languages check
        langs = conv.get("languages", [])
        if not langs:
            errors.append("  languages: empty array")
        for lang in langs:
            if lang not in VALID_LANGUAGES:
                errors.append(f"  languages: '{lang}' not in valid ISO code")
        primary = conv.get("primary_language", "")
        if primary and primary not in VALID_LANGUAGES:
            errors.append(f"  primary_language: '{primary}' not in valid ISO code")
        if primary and langs and primary not in langs:
            errors.append(f"  primary_language='{primary}' but not in languages={langs}")

        # Difficulty check
        diff = conv.get("difficulty", 0)
        if not isinstance(diff, int) or not (1 <= diff <= 7):
            errors.append(f"  difficulty: {diff} not in range 1-7")

        # Speaker profile check
        sp = conv.get("speaker_profile", "")
        if sp and sp not in ("student", "parent", "mixed"):
            errors.append(f"  speaker_profile: '{sp}' invalid")

        # ID format check
        conv_id = conv.get("id", "")
        if not re.match(r"^BENCH_\d{6}$", conv_id):
            errors.append(f"  id: '{conv_id}' doesn't match BENCH_NNNNNN pattern")

        # Annotation status check (if present)
        ann = conv.get("annotation", {})
        if ann:
            if ann.get("status") and ann["status"] not in ("draft", "reviewed", "frozen"):
                errors.append(f"  annotation.status: '{ann['status']}' invalid")

        return errors


# ── CoverageValidator ────────────────────────────────────────────────────────

class CoverageValidator:
    """Detects duplicated scenarios and reports unseen domain x feature combinations."""

    def __init__(self):
        self.unseen_report: dict[str, int] = {}
        self.duplicate_groups: list[list[str]] = []

    def validate(self, convs: list[dict]) -> list[str]:
        issues = []
        issues.extend(self._check_duplicates(convs))
        issues.extend(self._report_unseen(convs))
        return issues

    def _scenario_key(self, conv: dict) -> str:
        """Create a semantic scenario key from domain + features + ground_truth pattern."""
        gt = conv.get("ground_truth", {})
        domain = conv.get("domain", "")
        features = sorted(conv.get("features", []))
        rank = gt.get("rank")
        pcm = gt.get("pcm_percentage")
        cat = gt.get("category", "")
        interest = gt.get("interest", "")
        # Quantize rank to nearest 5000, PCM to nearest 10
        rank_bucket = f"rank_{(rank // 5000) * 5000}" if rank else "rank_none"
        pcm_bucket = f"pcm_{(int(pcm) // 10) * 10}" if pcm else "pcm_none"
        return f"{domain}|{','.join(features)}|{rank_bucket}|{pcm_bucket}|{cat}|{interest}"

    def _check_duplicates(self, convs: list[dict]) -> list[str]:
        issues = []
        by_scenario: dict[str, list[str]] = defaultdict(list)
        for conv in convs:
            key = self._scenario_key(conv)
            by_scenario[key].append(conv.get("id", "?"))
        for key, ids in by_scenario.items():
            if len(ids) > 1:
                issues.append(f"  DUPLICATE SCENARIO ({len(ids)}x): {key}")
                for cid in ids:
                    issues.append(f"    - {cid}")
        return issues

    def _report_unseen(self, convs: list[dict]) -> list[str]:
        """Report domain x feature combinations with zero examples."""
        seen: dict[str, set[str]] = defaultdict(set)
        for conv in convs:
            domain = conv.get("domain", "")
            for feat in conv.get("features", ["(none)"]):
                seen[domain].add(feat)

        all_features = sorted(VALID_FEATURES | {"(none)"})
        missing = []
        for domain in sorted(VALID_DOMAINS):
            for feat in all_features:
                if feat not in seen.get(domain, set()):
                    missing.append(f"  {domain} + {feat}: 0")
        return missing


# ── BalanceValidator ─────────────────────────────────────────────────────────

class BalanceValidator:
    """Prints distribution tables and warns on skew."""

    def validate(self, convs: list[dict]) -> list[str]:
        issues = []
        issues.extend(self._count_distribution("domain", [c.get("domain", "?") for c in convs]))
        issues.extend(self._count_distribution("difficulty", [str(c.get("difficulty", "?")) for c in convs]))
        issues.extend(self._count_distribution("primary_language", [c.get("primary_language", "?") for c in convs]))
        issues.extend(self._count_distribution("speaker_profile", [c.get("speaker_profile", "?") for c in convs]))

        # Feature counts (flatten)
        all_features = []
        for c in convs:
            feats = c.get("features", [])
            all_features.extend(feats if feats else ["(none)"])
        issues.extend(self._count_distribution("features", all_features))

        # Intent counts (flatten from turns)
        all_intents = []
        for c in convs:
            for t in c.get("turns", []):
                intent = t.get("expected", {}).get("understanding", {}).get("intent", "?")
                all_intents.append(intent)
        issues.extend(self._count_distribution("intent (per-turn)", all_intents))

        # Decision action counts
        all_actions = []
        for c in convs:
            for t in c.get("turns", []):
                action = t.get("expected", {}).get("decision", {}).get("action", "?")
                all_actions.append(action)
        issues.extend(self._count_distribution("decision action (per-turn)", all_actions))

        # Turn count stats
        turn_counts = [len(c.get("turns", [])) for c in convs]
        if turn_counts:
            avg = sum(turn_counts) / len(turn_counts)
            issues.append(f"\n  Turn count: avg={avg:.1f}, min={min(turn_counts)}, max={max(turn_counts)}")
            single = sum(1 for t in turn_counts if t == 1)
            multi = sum(1 for t in turn_counts if t >= 2)
            issues.append(f"  Single-turn: {single} ({100*single/len(convs):.0f}%), Multi-turn: {multi} ({100*multi/len(convs):.0f}%)")

        return issues

    def _count_distribution(self, label: str, values: list[str]) -> list[str]:
        counts = Counter(values)
        total = len(values) or 1
        lines = [f"\n  {label} distribution ({total} total):"]
        for val, count in counts.most_common():
            bar = "█" * (count * 30 // max(counts.values(), default=1))
            pct = 100 * count / total
            lines.append(f"    {val:25s} {count:4d} ({pct:5.1f}%) {bar}")
        return lines


# ── QualityValidator ─────────────────────────────────────────────────────────

class QualityValidator:
    """Checks annotation quality beyond schema compliance."""

    def validate(self, convs: list[dict]) -> list[str]:
        issues = []
        issues.extend(self._check_filler_content_contains(convs))
        issues.extend(self._check_duplicate_planner_responses(convs))
        issues.extend(self._check_duplicate_content_contains(convs))
        issues.extend(self._check_contradictory_annotations(convs))
        issues.extend(self._check_impossible_branches(convs))
        issues.extend(self._check_duplicate_must_not(convs))
        issues.extend(self._check_repeated_openings_endings(convs))
        issues.extend(self._check_intent_action_consistency(convs))
        return issues

    def _check_filler_content_contains(self, convs: list[dict]) -> list[str]:
        issues = []
        for conv in convs:
            for i, turn in enumerate(conv.get("turns", [])):
                planner = turn.get("expected", {}).get("planner", {})
                for j, pt in enumerate(planner.get("turns", [])):
                    for kw in pt.get("content_contains", []):
                        if kw.lower() in FILLER_WORDS:
                            issues.append(
                                f"  {conv.get('id')} turn {i} planner[{j}]: "
                                f"filler word '{kw}' in content_contains"
                            )
        return issues

    def _check_duplicate_planner_responses(self, convs: list[dict]) -> list[str]:
        issues = []
        for conv in convs:
            seen_actions = []
            for i, turn in enumerate(conv.get("turns", [])):
                planner = turn.get("expected", {}).get("planner", {})
                actions = tuple(pt.get("action", "") for pt in planner.get("turns", []))
                if actions in seen_actions and actions:
                    issues.append(
                        f"  {conv.get('id')} turn {i}: duplicate planner response pattern"
                    )
                seen_actions.append(actions)
        return issues

    def _check_duplicate_content_contains(self, convs: list[dict]) -> list[str]:
        issues = []
        for conv in convs:
            for i, turn in enumerate(conv.get("turns", [])):
                planner = turn.get("expected", {}).get("planner", {})
                all_kws = []
                for pt in planner.get("turns", []):
                    all_kws.extend(pt.get("content_contains", []))
                dupes = [kw for kw, c in Counter(all_kws).items() if c > 1]
                if dupes:
                    issues.append(
                        f"  {conv.get('id')} turn {i}: duplicate content_contains: {dupes}"
                    )
        return issues

    def _check_contradictory_annotations(self, convs: list[dict]) -> list[str]:
        """Check for contradictions across turns within a conversation."""
        issues = []
        for conv in convs:
            facts_so_far: dict[str, Any] = {}
            for i, turn in enumerate(conv.get("turns", [])):
                facts = turn.get("expected", {}).get("understanding", {}).get("facts", {})
                for key, val in facts.items():
                    if val is not None and val != "" and val != 0:
                        prev = facts_so_far.get(key)
                        if prev is not None and prev != val:
                            # Check if this is a correction (allowed)
                            features = conv.get("features", [])
                            if "correction" not in features:
                                issues.append(
                                    f"  {conv.get('id')} turn {i}: "
                                    f"{key} changed {prev} -> {val} without 'correction' feature"
                                )
                        facts_so_far[key] = val
        return issues

    def _check_impossible_branches(self, convs: list[dict]) -> list[str]:
        """Check brain eligible_branches contain only known branch names."""
        KNOWN_BRANCHES = {
            "CSE", "AIML", "IT", "ECE", "EE", "ME", "CE", "CH", "BT",
            "AE", "IE", "SE", "PE", "TE", "MN", "MIN", "PI",
            "CSBS", "AI", "DS", "IoT", "Cyber Security",
        }
        issues = []
        for conv in convs:
            for i, turn in enumerate(conv.get("turns", [])):
                brain = turn.get("expected", {}).get("brain", {})
                for branch in brain.get("eligible_branches", []):
                    if branch.upper() not in {b.upper() for b in KNOWN_BRANCHES}:
                        issues.append(
                            f"  {conv.get('id')} turn {i}: "
                            f"unknown branch '{branch}' in eligible_branches"
                        )
        return issues

    def _check_duplicate_must_not(self, convs: list[dict]) -> list[str]:
        issues = []
        for conv in convs:
            for i, turn in enumerate(conv.get("turns", [])):
                must_nots = turn.get("must_not", [])
                dupes = [m for m, c in Counter(must_nots).items() if c > 1]
                if dupes:
                    issues.append(
                        f"  {conv.get('id')} turn {i}: duplicate must_not: {dupes}"
                    )
        return issues

    def _check_repeated_openings_endings(self, convs: list[dict]) -> list[str]:
        issues = []
        openings = []
        endings = []
        for conv in convs:
            turns = conv.get("turns", [])
            if turns:
                openings.append(turns[0].get("student", ""))
                endings.append(turns[-1].get("student", ""))
        # Check for near-identical openings
        for i, o1 in enumerate(openings):
            for j, o2 in enumerate(openings):
                if i >= j:
                    continue
                if self._text_similarity(o1, o2) > 0.7:
                    issues.append(
                        f"  Similar opening: conv[{i}] and conv[{j}] ({self._text_similarity(o1, o2):.0%})"
                    )
        # Check for near-identical endings
        for i, e1 in enumerate(endings):
            for j, e2 in enumerate(endings):
                if i >= j:
                    continue
                if self._text_similarity(e1, e2) > 0.7:
                    issues.append(
                        f"  Similar ending: conv[{i}] and conv[{j}] ({self._text_similarity(e1, e2):.0%})"
                    )
        return issues

    def _check_intent_action_consistency(self, convs: list[dict]) -> list[str]:
        """Check that decision action is plausible for the intent."""
        issues = []
        INTENT_ACTION_MAP = {
            "admission": {"recommend_branches", "collect_profile", "provide_admission_info",
                          "encourage_and_collect_profile", "provide_branch_guidance"},
            "fee": {"provide_fee_info", "collect_profile"},
            "hostel": {"provide_hostel_info", "collect_profile"},
            "placement": {"provide_placement_info", "collect_profile"},
            "scholarship": {"provide_scholarship_info", "collect_profile"},
            "grievance": {"provide_grievance_process", "escalate_to_human"},
            "counseling": {"provide_counseling_schedule", "collect_profile"},
        }
        for conv in convs:
            for i, turn in enumerate(conv.get("turns", [])):
                intent = turn.get("expected", {}).get("understanding", {}).get("intent", "")
                action = turn.get("expected", {}).get("decision", {}).get("action", "")
                allowed = INTENT_ACTION_MAP.get(intent)
                if allowed and action and action not in allowed:
                    issues.append(
                        f"  {conv.get('id')} turn {i}: intent={intent} but action={action} "
                        f"(expected one of {allowed})"
                    )
        return issues

    def _text_similarity(self, a: str, b: str) -> float:
        """Simple word-overlap Jaccard similarity."""
        if not a or not b:
            return 0.0
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        return len(words_a & words_b) / len(words_a | words_b)


# ── RegressionValidator ──────────────────────────────────────────────────────

class RegressionValidator:
    """Runs pipeline on conversations and compares gold vs actual output."""

    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def validate(self, convs: list[dict]) -> list[str]:
        if self.dry_run:
            return ["  [skipped] --regression requires pipeline (use --regression --run)"]
        try:
            from src.pipeline import PipelineOrchestrator
            from src.conversation.state import ConversationState
        except ImportError:
            return ["  [skipped] Cannot import pipeline"]

        issues = []
        pipe = PipelineOrchestrator()
        for conv in convs:
            conv_id = conv.get("id", "?")
            state = ConversationState(session_id=conv_id)
            turns = conv.get("turns", [])
            for i, turn in enumerate(turns):
                text = turn.get("student", "")
                result = pipe.run(text, state)
                if not result.understanding:
                    issues.append(f"  {conv_id} turn {i}: no understanding output")
                    continue
                # Check intent
                expected_intent = turn.get("expected", {}).get("understanding", {}).get("intent", "")
                actual_intent = result.understanding.intent.primary
                if expected_intent and actual_intent != expected_intent:
                    issues.append(
                        f"  {conv_id} turn {i}: intent {actual_intent} != gold {expected_intent}"
                    )
                # Check decision action
                expected_action = turn.get("expected", {}).get("decision", {}).get("action", "")
                actual_action = result.decision.action if result.decision else ""
                if expected_action and actual_action != expected_action:
                    issues.append(
                        f"  {conv_id} turn {i}: action {actual_action} != gold {expected_action}"
                    )
        return issues


# ── CompatibilityValidator ───────────────────────────────────────────────────

class CompatibilityValidator:
    """Cross-version integrity checks across all manifests."""

    def validate(self, all_results: list[tuple[dict, list[dict], list[str]]]) -> list[str]:
        issues = []

        # Collect all conversation IDs across versions
        all_ids: dict[str, list[str]] = defaultdict(list)
        all_convs: dict[str, dict] = {}
        for manifest, convs, _ in all_results:
            version = manifest.get("version", "?")
            for conv in convs:
                cid = conv.get("id", "")
                all_ids[cid].append(version)
                all_convs[cid] = conv

        # Check: no duplicate IDs across versions
        for cid, versions in all_ids.items():
            if len(versions) > 1:
                issues.append(f"  DUPLICATE ID '{cid}' in versions: {', '.join(versions)}")

        # Check: every conversation belongs to exactly one version
        # (already covered above — duplicates are the violation)

        # Check: every manifest references existing files
        for manifest, convs, load_errors in all_results:
            version = manifest.get("version", "?")
            for err in load_errors:
                issues.append(f"  [{version}] {err}")

        # Check: manifest checksums are valid
        for manifest, convs, _ in all_results:
            version = manifest.get("version", "?")
            stored_checksum = manifest.get("checksum")
            if stored_checksum:
                conv_ids = sorted(c.get("id", "") for c in convs)
                computed = checksum(conv_ids)
                if computed != stored_checksum:
                    issues.append(
                        f"  [{version}] Checksum mismatch: stored={stored_checksum} computed={computed}"
                    )

        # Check: schema_version matches manifest schema
        for manifest, convs, _ in all_results:
            version = manifest.get("version", "?")
            manifest_schema = manifest.get("schema", "")
            for conv in convs:
                cid = conv.get("id", "?")
                conv_schema = conv.get("schema_version", "")
                if manifest_schema and conv_schema and conv_schema != manifest_schema:
                    issues.append(
                        f"  [{version}] {cid}: schema_version='{conv_schema}' != manifest schema='{manifest_schema}'"
                    )

        # Check: no orphan conversations (files in conversations/ not in any manifest)
        all_manifest_ids = set()
        for manifest, _, _ in all_results:
            for cid in manifest.get("conversations", []):
                all_manifest_ids.add(cid)

        if CONVERSATIONS_DIR.exists():
            for domain_dir in CONVERSATIONS_DIR.iterdir():
                if not domain_dir.is_dir():
                    continue
                for f in domain_dir.glob("*.json"):
                    try:
                        data = json.loads(f.read_text(encoding="utf-8"))
                        cid = data.get("id", "")
                        if cid and cid not in all_manifest_ids:
                            issues.append(f"  ORPHAN: {cid} in {f} not in any manifest")
                    except (json.JSONDecodeError, KeyError):
                        pass

        # Check: referenced schema files exist
        for manifest, _, _ in all_results:
            version = manifest.get("version", "?")
            schema_key = manifest.get("schema", "")
            schema_path = SCHEMA_MAP.get(schema_key)
            if schema_path and not schema_path.exists():
                issues.append(f"  [{version}] Schema file not found: {schema_path}")

        return issues


# ── CLI ──────────────────────────────────────────────────────────────────────

def _validate_version(version: str, manifest: dict, convs: list[dict],
                       args) -> int:
    """Run all requested checks on a single version. Returns issue count."""
    schema_key = manifest.get("schema", "v2")
    total_issues = 0

    print(f"\n{'=' * 60}")
    print(f"  VERSION: {version}  (schema: {schema_key}, conversations: {len(convs)})")
    print(f"{'=' * 60}\n")

    run_all = args.all

    if run_all or args.schema:
        print("─" * 60)
        print("SCHEMA VALIDATION")
        print("─" * 60)
        validator = SchemaValidator()
        try:
            validator.set_schema(schema_key)
        except ValueError as e:
            print(f"  SKIP: {e}")
        else:
            issues = []
            for conv in convs:
                errs = validator.validate(conv)
                if errs:
                    print(f"\n  {conv.get('id', '?')}:")
                    for e in errs:
                        print(f"    {e}")
                    issues.extend(errs)
            if not issues:
                print("  All conversations pass schema validation.")
            total_issues += len(issues)
        print()

    if run_all or args.metadata:
        print("─" * 60)
        print("METADATA VALIDATION")
        print("─" * 60)
        validator = MetadataValidator()
        issues = []
        for conv in convs:
            errs = validator.validate(conv)
            if errs:
                print(f"\n  {conv.get('id', '?')}:")
                for e in errs:
                    print(f"    {e}")
                issues.extend(errs)
        if not issues:
            print("  All metadata valid.")
        total_issues += len(issues)
        print()

    if run_all or args.coverage:
        print("─" * 60)
        print("COVERAGE ANALYSIS")
        print("─" * 60)
        validator = CoverageValidator()
        issues = validator.validate(convs)
        for issue in issues:
            print(issue)
        if not issues:
            print("  No duplicates found.")
        total_issues += len([i for i in issues if "DUPLICATE" in i])
        print()

    if run_all or args.balance:
        print("─" * 60)
        print("BALANCE REPORT")
        print("─" * 60)
        validator = BalanceValidator()
        issues = validator.validate(convs)
        for issue in issues:
            print(issue)
        print()

    if run_all or args.quality:
        print("─" * 60)
        print("QUALITY CHECKS")
        print("─" * 60)
        validator = QualityValidator()
        issues = validator.validate(convs)
        for issue in issues:
            print(issue)
        if not issues:
            print("  All quality checks pass.")
        total_issues += len(issues)
        print()

    if run_all or args.regression:
        print("─" * 60)
        print("REGRESSION CHECK")
        print("─" * 60)
        validator = RegressionValidator(dry_run=not args.run)
        issues = validator.validate(convs)
        for issue in issues:
            print(issue)
        total_issues += len(issues)
        print()

    return total_issues


def main():
    parser = argparse.ArgumentParser(
        description="Unified benchmark validator (version-aware)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", type=str, help="Validate a specific version (e.g. v2.0, v1.1)")
    parser.add_argument("--all-versions", action="store_true", help="Validate each version separately + compatibility")
    parser.add_argument("--schema", action="store_true", help="Validate schema compliance")
    parser.add_argument("--metadata", action="store_true", help="Validate metadata fields")
    parser.add_argument("--coverage", action="store_true", help="Detect duplicates + unseen combos")
    parser.add_argument("--balance", action="store_true", help="Print distribution tables")
    parser.add_argument("--quality", action="store_true", help="Annotation quality checks")
    parser.add_argument("--regression", action="store_true", help="Run pipeline + compare")
    parser.add_argument("--run", action="store_true", help="Actually run pipeline (with --regression)")
    parser.add_argument("--all", action="store_true", help="Run all checks")
    args = parser.parse_args()

    if not any([args.version, args.all_versions, args.schema, args.metadata,
                args.coverage, args.balance, args.quality, args.regression, args.all]):
        parser.print_help()
        return

    total_issues = 0

    if args.all_versions:
        # Validate each version separately, then run compatibility checks
        all_results = load_all_versions()
        if not all_results:
            print("No version manifests found in", VERSIONS_DIR)
            return

        for manifest, convs, load_errors in all_results:
            version = manifest.get("version", "?")
            total_issues += _validate_version(version, manifest, convs, args)

        # Compatibility checks across all versions
        print("=" * 60)
        print("COMPATIBILITY CHECKS (cross-version)")
        print("=" * 60)
        compat = CompatibilityValidator()
        issues = compat.validate(all_results)
        for issue in issues:
            print(issue)
        if not issues:
            print("  All compatibility checks pass.")
        total_issues += len(issues)
        print()

    elif args.version:
        # Validate a single version
        manifest, convs, load_errors = load_version(args.version)
        if not manifest:
            print(f"Version {args.version} not found.")
            return
        for err in load_errors:
            print(err)
        total_issues += _validate_version(args.version, manifest, convs, args)

    else:
        parser.print_help()
        return

    print("=" * 60)
    print(f"TOTAL ISSUES: {total_issues}")
    print("=" * 60)
    sys.exit(1 if total_issues > 0 else 0)


if __name__ == "__main__":
    main()
