"""Policy-Gen APIs (Module 4 — AI HR policy generator).

DRF conversion of the rescued dashboard views (Module-4-update branch):
the template UI is replaced by JSON APIs; the platform frontend renders
the decision dashboard.
"""

from rest_framework import status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from smarthr360_jwt_auth.access import has_hr_access

from .clients import CoreHRClient, ServiceError
from .metrics import record_comparison, record_simulation
from .services.comparison import compare_policies
from .services.policy import (
    DemoDataService,
    HRAnalyticsService,
    PolicySimulatorService,
)

POLICY_TYPES = [
    "salary_increase",
    "remote_work",
    "training_budget",
    "wellness_program",
    "flexible_hours",
    "mentorship",
]


def _require_hr(request):
    if not has_hr_access(request.user):
        raise PermissionDenied("HR or Admin role required.")


class AnalyticsView(APIView):
    """GET /api/policy/analytics/ — current social indicators.

    `?source=live` computes the indicators from LIVE core-hr data
    (token pass-through) instead of the local analytical store.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)

        if request.query_params.get("source") == "live":
            try:
                live = CoreHRClient(request.auth).get_live_stats()
            except ServiceError as exc:
                return Response(
                    {"detail": f"core-hr unavailable: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            return Response(
                {
                    "source": live["source"],
                    "turnover_rate": live["turnover"],
                    "avg_performance": live["performance"],
                    "headcount": live["headcount"],
                    "active": live["active"],
                    "reviews_counted": live["reviews_counted"],
                }
            )

        return Response(
            {
                "source": "local analytical store",
                "turnover_rate": round(HRAnalyticsService.get_turnover_rate(), 1),
                "avg_performance": round(
                    float(HRAnalyticsService.get_average_performance()), 2
                ),
                "retention_stats": HRAnalyticsService.get_retention_stats(),
            }
        )


class SimulateView(APIView):
    """POST /api/policy/simulate/ {policy_type, magnitude} — impact preview."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        policy_type = request.data.get("policy_type")
        if policy_type not in POLICY_TYPES:
            return Response(
                {"detail": f"policy_type must be one of {POLICY_TYPES}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            magnitude = float(request.data.get("magnitude", 0))
        except (TypeError, ValueError):
            return Response(
                {"detail": "magnitude must be a number (0-10)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not 0 <= magnitude <= 10:
            return Response(
                {"detail": "magnitude must be between 0 and 10."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # optional cross-service mode: evaluate against LIVE core-hr data
        current_stats, headcount, source = None, None, "local analytical store"
        if request.data.get("use_live"):
            try:
                live = CoreHRClient(request.auth).get_live_stats()
            except ServiceError as exc:
                return Response(
                    {"detail": f"core-hr unavailable: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            current_stats = {
                "turnover": live["turnover"],
                "performance": live["performance"],
            }
            headcount = live["headcount"]
            source = live["source"]

        impact = PolicySimulatorService.simulate_policy_impact(
            policy_type, magnitude,
            current_stats=current_stats, headcount=headcount,
        )
        record_simulation(policy_type)

        # persist for later comparison (uses the rescued SimulationRun)
        from .models import SimulationRun

        run = SimulationRun.objects.create(
            scenario={
                "policy_type": policy_type,
                "magnitude": magnitude,
                "data_source": source,
                "requested_by_user_id": request.user.id,
            },
            result=impact,
        )

        return Response(
            {
                "simulation_id": str(run.id),
                "policy_type": policy_type,
                "magnitude": magnitude,
                "impact": impact,
                "data_source": source,
            }
        )


class ComparePoliciesView(APIView):
    """POST /api/policy/compare/ {policies:[{policy_type,magnitude}], use_live?}

    Head-to-head A/B comparison: ranks the given policies by value (turnover
    reduction + performance gain), and flags the most cost-efficient. Distinct
    from /optimize/ (budget-constrained portfolio selection).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        specs = request.data.get("policies")
        if not isinstance(specs, list) or len(specs) < 2:
            return Response(
                {"detail": "policies must be a list of at least 2 entries."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        for spec in specs:
            if not isinstance(spec, dict) or spec.get("policy_type") not in POLICY_TYPES:
                return Response(
                    {"detail": f"each policy_type must be one of {POLICY_TYPES}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # optional cross-service mode: evaluate all options against LIVE core-hr
        current_stats, headcount, source = None, None, "local analytical store"
        if request.data.get("use_live"):
            try:
                live = CoreHRClient(request.auth).get_live_stats()
            except ServiceError as exc:
                return Response(
                    {"detail": f"core-hr unavailable: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            current_stats = {"turnover": live["turnover"], "performance": live["performance"]}
            headcount = live["headcount"]
            source = live["source"]

        def simulate_fn(policy_type, magnitude):
            return PolicySimulatorService.simulate_policy_impact(
                policy_type, magnitude,
                current_stats=current_stats, headcount=headcount,
            )

        result = compare_policies(specs, simulate_fn)
        record_comparison()
        result["data_source"] = source
        return Response(result)


class RecommendationsView(APIView):
    """GET /api/policy/recommendations/?budget=100000 — AI proposals."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        try:
            budget = int(request.query_params.get("budget", 100000))
        except (TypeError, ValueError):
            budget = 100000
        recs = PolicySimulatorService.generate_recommendations(budget_limit=budget)
        return Response({"budget": budget, "recommendations": recs})


class ApplyPolicyView(APIView):
    """POST /api/policy/apply/ — apply a simulated policy (demo semantics)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        policy_type = request.data.get("policy_type")
        if policy_type not in POLICY_TYPES:
            return Response(
                {"detail": f"policy_type must be one of {POLICY_TYPES}."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        magnitude = float(request.data.get("magnitude", 0))
        impact = PolicySimulatorService.apply_policy(policy_type, magnitude)

        # persist the applied policy so its real-world outcome can be tracked
        # later (loop-closer: simulated impact -> applied -> measured result).
        from .models import SimulationRun

        run = SimulationRun.objects.create(
            scenario={
                "policy_type": policy_type,
                "magnitude": magnitude,
                "applied": True,
                "applied_by_user_id": request.user.id,
                "source_simulation_id": request.data.get("simulation_id"),
            },
            result={"predicted": impact, "outcome": None},
        )

        return Response(
            {"applied": policy_type, "impact": impact, "applied_id": str(run.id)}
        )


class ResetDemoDataView(APIView):
    """POST /api/policy/demo-data/reset/ — reseed the analytical store."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        DemoDataService.reset_and_populate()
        return Response({"detail": "Demo data reset."}, status=status.HTTP_201_CREATED)


class SimulationHistoryView(APIView):
    """GET /api/policy/simulations/ — recent persisted simulations (HR).

    Lets HR compare scenarios side by side instead of re-running them.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        from .models import SimulationRun

        runs = SimulationRun.objects.order_by("-created_at")[:25]
        return Response(
            {
                "count": len(runs),
                "simulations": [
                    {
                        "id": str(run.id),
                        "created_at": run.created_at.isoformat(),
                        "scenario": run.scenario,
                        "result": run.result,
                    }
                    for run in runs
                ],
            }
        )


class OptimizePortfolioView(APIView):
    """POST /api/policy/optimize/ {budget, magnitude?, policies?, use_live?}

    Returns the best affordable mix of policies (greedy knapsack over
    the impact model) with per-policy selection reasons.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        try:
            budget = float(request.data.get("budget", 0))
        except (TypeError, ValueError):
            budget = -1
        if budget < 0:
            return Response(
                {"detail": "budget must be a non-negative number."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            magnitude = float(request.data.get("magnitude", 5))
        except (TypeError, ValueError):
            magnitude = 5
        if not 0 <= magnitude <= 10:
            return Response(
                {"detail": "magnitude must be between 0 and 10."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        candidates = request.data.get("policies") or None
        if candidates and not set(candidates).issubset(POLICY_TYPES):
            return Response(
                {"detail": f"policies must be a subset of {POLICY_TYPES}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        current_stats, headcount, source = None, None, "local analytical store"
        if request.data.get("use_live"):
            try:
                live = CoreHRClient(request.auth).get_live_stats()
            except ServiceError as exc:
                return Response(
                    {"detail": f"core-hr unavailable: {exc}"},
                    status=status.HTTP_502_BAD_GATEWAY,
                )
            current_stats = {"turnover": live["turnover"],
                             "performance": live["performance"]}
            headcount = live["headcount"]
            source = live["source"]

        from .optimizer import optimize_portfolio

        portfolio = optimize_portfolio(
            budget, magnitude, candidates,
            current_stats=current_stats, headcount=headcount,
        )
        portfolio["data_source"] = source
        return Response(portfolio)
