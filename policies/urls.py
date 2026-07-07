from django.urls import path

from .views import (
    OptimizePortfolioView,
    ComparePoliciesView,
    SimulationHistoryView,
    AnalyticsView,
    ApplyPolicyView,
    RecommendationsView,
    ResetDemoDataView,
    SimulateView,
)

urlpatterns = [
    path("analytics/", AnalyticsView.as_view(), name="policy-analytics"),
    path("simulate/", SimulateView.as_view(), name="policy-simulate"),
    path("simulations/", SimulationHistoryView.as_view(), name="policy-simulations"),
    path("optimize/", OptimizePortfolioView.as_view(), name="policy-optimize"),
    path("compare/", ComparePoliciesView.as_view(), name="policy-compare"),
    path("recommendations/", RecommendationsView.as_view(), name="policy-recommendations"),
    path("apply/", ApplyPolicyView.as_view(), name="policy-apply"),
    path("demo-data/reset/", ResetDemoDataView.as_view(), name="policy-demo-reset"),
]
