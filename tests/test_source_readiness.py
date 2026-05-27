from pathlib import Path

from shiyi import (
    DEFAULT_STRUCTURED_FIXTURE_MAX_BYTES,
    StructuredApiReadinessEvidence,
    check_fixture_size,
)

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


def test_structured_api_readiness_requires_all_objective_evidence() -> None:
    evidence = StructuredApiReadinessEvidence(
        stable_official_endpoint=True,
        canonical_urls=True,
        traceability_refs=("docs/SOURCE_STRATEGY.md",),
    )

    assert evidence.status == "blocked"
    assert evidence.source_ready is False
    assert set(evidence.blockers) == {
        "stable_item_ids",
        "reliable_published_timestamps",
        "complete_payloads",
        "bounded_fixtures",
        "repeatable_extraction_tests",
    }


def test_structured_api_readiness_passes_with_complete_fixture_backed_evidence() -> None:
    evidence = StructuredApiReadinessEvidence(
        stable_official_endpoint=True,
        stable_item_ids=True,
        reliable_published_timestamps=True,
        canonical_urls=True,
        complete_payloads=True,
        bounded_fixtures=True,
        repeatable_extraction_tests=True,
        traceability_refs=(
            "tests/adapters/test_adapter_internal_item_contract.py",
            "tests/integration/test_boundary_e2e_export_golden.py",
        ),
    )

    assert evidence.blockers == ()
    assert evidence.status == "ready"
    assert evidence.source_ready is True


def test_structured_api_fixture_size_boundary_covers_current_ready_payloads() -> None:
    checks = [
        check_fixture_size(FIXTURE_ROOT / "bytedance-seed-blog" / "raw" / "index.html"),
        check_fixture_size(
            FIXTURE_ROOT / "bytedance-seed-blog" / "raw" / "seed3d-2-0-released.html"
        ),
    ]

    assert all(check.ok for check in checks)
    assert all(check.max_bytes == DEFAULT_STRUCTURED_FIXTURE_MAX_BYTES for check in checks)


def test_us04_ai_coding_ready_fixture_size_boundary_is_bounded() -> None:
    checks = [
        check_fixture_size(FIXTURE_ROOT / "cursor-changelog" / "raw" / "changelog.html"),
        check_fixture_size(FIXTURE_ROOT / "github-copilot-changelog" / "raw" / "feed.json"),
    ]

    assert all(check.ok for check in checks)
    assert all(check.max_bytes == DEFAULT_STRUCTURED_FIXTURE_MAX_BYTES for check in checks)


def test_fixture_size_check_marks_oversized_payloads(tmp_path: Path) -> None:
    oversized = tmp_path / "oversized.json"
    payload_size = 4
    max_bytes = 3
    oversized.write_bytes(b"x" * payload_size)

    check = check_fixture_size(oversized, max_bytes=max_bytes)

    assert check.ok is False
    assert check.size_bytes == payload_size
    assert check.max_bytes == max_bytes
