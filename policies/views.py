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
    """GET /api/policy/analytics/ — current social indicators."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        return Response(
            {
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

        impact = PolicySimulatorService.simulate_policy_impact(policy_type, magnitude)
        return Response(
            {"policy_type": policy_type, "magnitude": magnitude, "impact": impact}
        )


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
        return Response({"applied": policy_type, "impact": impact})


class ResetDemoDataView(APIView):
    """POST /api/policy/demo-data/reset/ — reseed the analytical store."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        _require_hr(request)
        DemoDataService.reset_and_populate()
        return Response({"detail": "Demo data reset."}, status=status.HTTP_201_CREATED)
