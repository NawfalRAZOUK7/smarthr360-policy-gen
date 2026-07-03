"""Policy portfolio optimizer: the best mix of HR policies under a budget.

Greedy knapsack over the simulator's impact model:
  benefit = |turnover reduction| * TURNOVER_WEIGHT
          + performance gain    * PERFORMANCE_WEIGHT

Zero-cost policies are always taken first (there is no reason not to);
paid policies are ranked by benefit-per-cost and added while the budget
allows. Deterministic with the static model; with Groq configured the
same procedure runs over the LLM-predicted impacts.
"""

from __future__ import annotations

from .services.policy import PolicySimulatorService
from .views import POLICY_TYPES

TURNOVER_WEIGHT = 10.0     # 1pt of turnover ≈ 10 benefit units
PERFORMANCE_WEIGHT = 20.0  # 1pt of avg performance ≈ 20 benefit units


def _benefit(impact: dict) -> float:
    return round(
        max(0.0, -impact["turnover_change"]) * TURNOVER_WEIGHT
        + max(0.0, impact["performance_change"]) * PERFORMANCE_WEIGHT,
        2,
    )


def optimize_portfolio(budget: float, magnitude: float = 5,
                       candidates: list[str] | None = None,
                       current_stats: dict | None = None,
                       headcount: int | None = None) -> dict:
    candidates = candidates or list(POLICY_TYPES)

    evaluated = []
    for policy_type in candidates:
        impact = PolicySimulatorService.simulate_policy_impact(
            policy_type, magnitude,
            current_stats=current_stats, headcount=headcount,
        )
        evaluated.append(
            {
                "policy_type": policy_type,
                "impact": impact,
                "cost": float(impact.get("cost_estimate", 0.0)),
                "benefit": _benefit(impact),
            }
        )

    free = [e for e in evaluated if e["cost"] <= 0]
    paid = sorted(
        (e for e in evaluated if e["cost"] > 0),
        key=lambda e: -(e["benefit"] / e["cost"]),
    )

    selected, rejected, remaining = [], [], float(budget)
    for entry in free:
        entry["reason"] = "zero cost — always beneficial"
        selected.append(entry)
    for entry in paid:
        if entry["benefit"] <= 0:
            entry["reason"] = "no modelled benefit"
            rejected.append(entry)
        elif entry["cost"] <= remaining:
            entry["reason"] = (
                f"best remaining benefit/cost "
                f"({entry['benefit']}/{entry['cost']:.0f})"
            )
            selected.append(entry)
            remaining -= entry["cost"]
        else:
            entry["reason"] = (
                f"over remaining budget ({entry['cost']:.0f} > "
                f"{remaining:.0f})"
            )
            rejected.append(entry)

    return {
        "budget": float(budget),
        "budget_used": round(float(budget) - remaining, 2),
        "budget_remaining": round(remaining, 2),
        "magnitude": magnitude,
        "expected_turnover_change": round(
            sum(e["impact"]["turnover_change"] for e in selected), 2
        ),
        "expected_performance_change": round(
            sum(e["impact"]["performance_change"] for e in selected), 2
        ),
        "selected": selected,
        "rejected": rejected,
        "weights": {
            "turnover_point": TURNOVER_WEIGHT,
            "performance_point": PERFORMANCE_WEIGHT,
        },
    }
