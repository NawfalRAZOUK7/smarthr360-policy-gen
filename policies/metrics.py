"""Prometheus metrics for policy-gen, on the shared idempotent factory."""

from __future__ import annotations

from smarthr360_integration.observability import get_counter

POLICY_SIMULATIONS = get_counter(
    "policy_simulations_total",
    "Policy impact simulations run, by policy type.",
    ["policy_type"],
)

POLICY_COMPARISONS = get_counter(
    "policy_comparisons_total",
    "A/B policy comparisons run.",
)


def record_simulation(policy_type: str) -> None:
    try:
        POLICY_SIMULATIONS.labels(policy_type=policy_type).inc()
    except Exception:  # pragma: no cover
        pass


def record_comparison() -> None:
    try:
        POLICY_COMPARISONS.inc()
    except Exception:  # pragma: no cover
        pass
