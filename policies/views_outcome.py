"""Applied-policy outcome tracking (loop-closer for policy-gen).

Closes the policy loop: a simulated policy is *applied* (persisted by
``ApplyPolicyView``), then HR later records what actually happened to
turnover and cost. We compare the observed result against the predicted
impact so HR can see whether a policy delivered — and calibrate future
simulations.

No new model is needed: applied policies live in ``SimulationRun`` tagged
``scenario.applied = True``, and the outcome is stored inside ``result``.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from smarthr360_jwt_auth.access import has_hr_access

from .models import SimulationRun


def _require_hr(request):
    from rest_framework.exceptions import PermissionDenied

    if not has_hr_access(request.user):
        raise PermissionDenied("HR or Admin role required.")


def _to_float(value):
    if value is None or value == "":
        return None
    try:
        return round(float(value), 2)
    except (TypeError, ValueError):
        return None


def _variance(run):
    """Predicted vs. observed for one applied policy (or ``None``)."""
    result = run.result or {}
    predicted = result.get("predicted") or {}
    outcome = result.get("outcome")
    if not outcome:
        return None

    pred_turnover = predicted.get("turnover_change")
    pred_cost = predicted.get("cost_estimate")
    obs_turnover = outcome.get("observed_turnover_change")
    obs_cost = outcome.get("observed_cost")

    v = {}
    if pred_turnover is not None and obs_turnover is not None:
        v["turnover_variance"] = round(obs_turnover - pred_turnover, 2)
        # A policy "delivered" when the realized reduction meets/beats the
        # predicted reduction (both expressed as signed change; lower = better).
        v["delivered"] = obs_turnover <= pred_turnover
    if pred_cost is not None and obs_cost is not None:
        v["cost_variance"] = round(obs_cost - pred_cost, 2)
    return v or None


def _serialize(run):
    scenario = run.scenario or {}
    result = run.result or {}
    return {
        "applied_id": str(run.id),
        "policy_type": scenario.get("policy_type"),
        "magnitude": scenario.get("magnitude"),
        "applied_at": run.created_at.isoformat(),
        "source_simulation_id": scenario.get("source_simulation_id"),
        "predicted": result.get("predicted"),
        "outcome": result.get("outcome"),
        "variance": _variance(run),
    }


class AppliedPoliciesView(APIView):
    """GET /api/policy/applied/ — applied policies with predicted vs actual.

    HR sees every policy that was put into effect, its predicted impact, and
    (once recorded) the measured real-world outcome and variance.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        runs = [
            r
            for r in SimulationRun.objects.order_by("-created_at")[:100]
            if (r.scenario or {}).get("applied")
        ]
        tracked = [r for r in runs if (r.result or {}).get("outcome")]
        return Response(
            {
                "count": len(runs),
                "tracked_count": len(tracked),
                "applied": [_serialize(r) for r in runs[:50]],
            }
        )


class RecordPolicyOutcomeView(APIView):
    """POST /api/policy/applied/<uuid:pk>/outcome/ — record the real result.

    Body: ``{observed_turnover_change, observed_cost, note}``. Stores the
    outcome on the applied policy and returns the recomputed variance.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        _require_hr(request)
        try:
            run = SimulationRun.objects.get(pk=pk)
        except SimulationRun.DoesNotExist:
            return Response(
                {"detail": "Applied policy not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        if not (run.scenario or {}).get("applied"):
            return Response(
                {"detail": "This simulation was never applied."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        obs_turnover = _to_float(request.data.get("observed_turnover_change"))
        obs_cost = _to_float(request.data.get("observed_cost"))
        if obs_turnover is None and obs_cost is None:
            return Response(
                {"detail": "Provide observed_turnover_change and/or observed_cost."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = run.result or {}
        result["outcome"] = {
            "observed_turnover_change": obs_turnover,
            "observed_cost": obs_cost,
            "note": (request.data.get("note") or "").strip()[:500],
            "recorded_by_user_id": request.user.id,
        }
        run.result = result
        run.save(update_fields=["result"])

        return Response(_serialize(run), status=status.HTTP_200_OK)


class PolicyOutcomesSummaryView(APIView):
    """GET /api/policy/outcomes/summary/ — did applied policies deliver?

    Aggregates predicted-vs-actual across every applied policy, overall and by
    policy type, so HR can see which policy levers actually pay off and stop
    guessing from single simulations.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        applied = [
            r
            for r in SimulationRun.objects.order_by("-created_at")[:500]
            if (r.scenario or {}).get("applied")
        ]
        tracked = [r for r in applied if (r.result or {}).get("outcome")]

        def avg(xs):
            return round(sum(xs) / len(xs), 2) if xs else None

        by_type: dict = {}
        for r in applied:
            pt = (r.scenario or {}).get("policy_type") or "unknown"
            b = by_type.setdefault(
                pt,
                {"policy_type": pt, "applied": 0, "tracked": 0, "delivered": 0,
                 "_pred": [], "_obs": [], "_cost_var": []},
            )
            b["applied"] += 1
            v = _variance(r)
            if v is None:
                continue
            b["tracked"] += 1
            if v.get("delivered"):
                b["delivered"] += 1
            pred = (r.result or {}).get("predicted") or {}
            outcome = (r.result or {}).get("outcome") or {}
            if pred.get("turnover_change") is not None:
                b["_pred"].append(pred["turnover_change"])
            if outcome.get("observed_turnover_change") is not None:
                b["_obs"].append(outcome["observed_turnover_change"])
            if v.get("cost_variance") is not None:
                b["_cost_var"].append(v["cost_variance"])

        rows = [
            {
                "policy_type": b["policy_type"],
                "applied": b["applied"],
                "tracked": b["tracked"],
                "delivered": b["delivered"],
                "delivered_rate": round(b["delivered"] / b["tracked"], 2) if b["tracked"] else None,
                "avg_predicted_turnover": avg(b["_pred"]),
                "avg_observed_turnover": avg(b["_obs"]),
                "total_cost_variance": round(sum(b["_cost_var"]), 2) if b["_cost_var"] else None,
            }
            for b in by_type.values()
        ]
        rows.sort(key=lambda x: x["applied"], reverse=True)

        delivered_total = sum(1 for r in tracked if (_variance(r) or {}).get("delivered"))
        return Response(
            {
                "applied_count": len(applied),
                "tracked_count": len(tracked),
                "delivered_count": delivered_total,
                "delivered_rate": round(delivered_total / len(tracked), 2) if tracked else None,
                "by_policy_type": rows,
            }
        )
