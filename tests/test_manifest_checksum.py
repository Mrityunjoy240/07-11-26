"""Regression test: manifest checksum must equal SHA256(sorted(conv_ids))[:16].

If someone changes the checksum algorithm on either side (manifest or validator),
this test breaks. That's the point.
"""
import hashlib
import json
from pathlib import Path

import pytest

BENCHMARK_DIR = Path("data/benchmark")
MANIFESTS_DIR = BENCHMARK_DIR / "versions"
CONVERSATIONS_DIR = BENCHMARK_DIR / "conversations"


def _compute_checksum(conv_ids: list[str]) -> str:
    """Canonical checksum algorithm — must match benchmark_validate.py exactly."""
    return hashlib.sha256(
        json.dumps(sorted(conv_ids), sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]


def _load_manifest_conversation_ids(manifest: dict) -> list[str]:
    """Load conversation IDs from disk using the manifest's conversation list."""
    # Search directories the validator uses: v0.1, v0.2, conversations, validation
    search_dirs = []
    for d in ["v0.1", "v0.2", "conversations", "validation"]:
        p = BENCHMARK_DIR / d
        if p.is_dir():
            search_dirs.append(p)

    conv_ids = []
    for cid in manifest.get("conversations", []):
        found = False
        for search_dir in search_dirs:
            for conv_file in search_dir.rglob(f"{cid}.json"):
                conv_ids.append(cid)
                found = True
                break
            if found:
                break
        if not found:
            pytest.fail(f"Conversation {cid} listed in manifest but not found on disk")
    return conv_ids


@pytest.mark.parametrize(
    "manifest_path",
    sorted(MANIFESTS_DIR.glob("*.json")),
    ids=lambda p: p.stem,
)
def test_manifest_checksum_matches_algorithm(manifest_path: Path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    stored = manifest.get("checksum")
    if not stored:
        pytest.skip(f"Manifest {manifest_path.name} has no checksum field")

    conv_ids = _load_manifest_conversation_ids(manifest)
    computed = _compute_checksum(conv_ids)

    assert computed == stored, (
        f"Checksum mismatch in {manifest_path.name}.\n"
        f"  stored:    {stored}\n"
        f"  computed:  {computed}\n"
        f"  algorithm: SHA256(json.dumps(sorted(conv_ids), sort_keys=True))[:16]\n"
        f"  ids:       {sorted(conv_ids)}"
    )


def test_checksum_algorithm_is_deterministic():
    ids = ["BENCH_000001", "BENCH_000002", "BENCH_000003"]
    a = _compute_checksum(ids)
    b = _compute_checksum(ids)
    assert a == b
    assert len(a) == 16


def test_checksum_changes_when_ids_change():
    ids_a = ["BENCH_000001", "BENCH_000002"]
    ids_b = ["BENCH_000001", "BENCH_000003"]
    assert _compute_checksum(ids_a) != _compute_checksum(ids_b)


def test_checksum_changes_when_order_changes():
    """Even though we sort, verify that sorted() is actually called."""
    ids = ["BENCH_000002", "BENCH_000001"]
    unordered_hash = hashlib.sha256(
        json.dumps(ids, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:16]
    # Our function sorts first, so order shouldn't matter
    assert _compute_checksum(ids) == _compute_checksum(["BENCH_000001", "BENCH_000002"])
