"""A/B head-to-head policy comparison.

Distinct from ``optimize`` (which picks the best *portfolio* under a budget):
this compares an explicit set of policy options side by side and ranks them by
value, so HR can defend "why this policy over that one".

Pure ranking core — it receives a ``simulate_fn(policy_type, magnitude) ->
impact_dict`` so it unit-tests without Groq or a database. ``impact_dict`` keys:
``turnover_change`` (negative = good), ``performance_change``, ``cost_estimate``.
"""

from __future__ import annotations

from typing import Callable, Sequence

# How much a 1-point turnover reduction vs a 1-point performance gain is worth,
# expressed in comparable "value points" (tunable business weights).
W_TURNOVER = 1.0
W_PERFORMANCE = 0.8


def _benefit(impact: dict) -> float:
    # turnover_change is negative when the policy *reduces* turnover -> good.
    turnover_gain = -float(impact.get("turnover_change", 0.0))
    perf_gain = float(impact.get("performance_change", 0.0))
    return W_TURNOVER * turnover_gain + W_PERFORMANCE * perf_gain


def compare_policies(
    specs: Sequence[dict],
    simulate_fn: Callable[[str, float], dict],
) -> dict:
    """Compare policies. ``specs`` items: {"policy_type", "magnitude"}.

    Returns {"ranking": [...], "recommended": <policy_type>,
             "most_cost_efficient": <policy_type>}.
    """
    rows = []
    for spec in specs:
        ptype = spec["policy_type"]
        magnitude = float(spec.get("magnitude", 1))
        impact = simulate_fn(ptype, magnitude)
        benefit = _benefit(impact)
        cost = float(impact.get("cost_estimate", 0.0))
        # Value per 1,000 currency; zero-cost policies get pure benefit (inf-safe).
        efficiency = benefit if cost <= 0 else benefit / (cost / 1000.0)
        rows.append(
            {
                "policy_type": ptype,
                "magnitude": magnitude,
                "turnover_change": impact.get("turnover_change"),
                "performance_change": impact.get("performance_change"),
                "cost_estimate": cost,
                "benefit_score": round(benefit, 3),
                "cost_efficiency": round(efficiency, 3),
                "zero_cost": cost <= 0,
            }
        )

    by_benefit = sorted(rows, key=lambda r: r["benefit_score"], reverse=True)
    for i, row in enumerate(by_benefit, start=1):
        row["rank"] = i
    most_efficient = max(rows, key=lambda r: r["cost_efficiency"]) if rows else None

    return {
        "compared": len(by_benefit),
        "recommended": by_benefit[0]["policy_type"] if by_benefit else None,
        "most_cost_efficient": most_efficient["policy_type"] if most_efficient else None,
        "ranking": by_benefit,
    }
