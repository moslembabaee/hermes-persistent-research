from __future__ import annotations

from numbers import Real


DEFAULT_DIMENSIONS = (
    "factual_correctness",
    "citation_entailment",
    "provenance_completeness",
    "lineage_accuracy",
    "counterevidence_coverage",
    "calibration",
    "continuity",
    "reproducibility",
    "safety",
    "decision_usefulness",
)


def compare_runs(baseline: dict, pgra: dict) -> dict:
    baseline_metrics = baseline.get("metrics")
    pgra_metrics = pgra.get("metrics")
    if not isinstance(baseline_metrics, dict) or not isinstance(pgra_metrics, dict):
        raise ValueError("Both inputs require a metrics object")
    if set(baseline_metrics) != set(pgra_metrics):
        raise ValueError("Baseline and PGRA metric keys must match")
    if not baseline_metrics:
        raise ValueError("At least one metric is required")

    metrics = {}
    for name in sorted(baseline_metrics):
        baseline_value = baseline_metrics[name]
        pgra_value = pgra_metrics[name]
        if isinstance(baseline_value, bool) or not isinstance(baseline_value, Real):
            raise ValueError(f"Baseline metric {name} must be numeric")
        if isinstance(pgra_value, bool) or not isinstance(pgra_value, Real):
            raise ValueError(f"PGRA metric {name} must be numeric")
        metrics[name] = {
            "baseline": float(baseline_value),
            "pgra": float(pgra_value),
            "delta": float(pgra_value - baseline_value),
        }

    baseline_total = sum(item["baseline"] for item in metrics.values())
    pgra_total = sum(item["pgra"] for item in metrics.values())
    cost = {
        "baseline": baseline.get("cost", {}),
        "pgra": pgra.get("cost", {}),
    }
    return {
        "metrics": metrics,
        "summary": {
            "baseline_mean": baseline_total / len(metrics),
            "pgra_mean": pgra_total / len(metrics),
            "mean_delta": (pgra_total - baseline_total) / len(metrics),
            "pgra_wins": sum(1 for item in metrics.values() if item["delta"] > 0),
            "ties": sum(1 for item in metrics.values() if item["delta"] == 0),
            "pgra_losses": sum(1 for item in metrics.values() if item["delta"] < 0),
        },
        "cost": cost,
        "comparable": baseline.get("conditions") == pgra.get("conditions"),
        "condition_mismatch": None
        if baseline.get("conditions") == pgra.get("conditions")
        else {"baseline": baseline.get("conditions"), "pgra": pgra.get("conditions")},
    }
