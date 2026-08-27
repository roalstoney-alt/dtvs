from __future__ import annotations


def fixture_cost_summary() -> dict[str, str]:
    return {
        "status": "SKIPPED_WITH_REASON",
        "reason": "fixture execution has no measured GPU energy, transfer, storage, manual review, or model runtime cost",
        "centralized_comparison": "CENTRALIZED_COMPARISON_NOT_AVAILABLE",
    }

