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
from .views_documents import (
    EmployeeContractPDFView,
    EmployeeListView,
    PolicyDocumentPDFView,
    PolicyTemplatesView,
)
from .views_outcome import (
    AppliedPoliciesView,
    PolicyOutcomesSummaryView,
    RecordPolicyOutcomeView,
)

urlpatterns = [
    path("analytics/", AnalyticsView.as_view(), name="policy-analytics"),
    path("simulate/", SimulateView.as_view(), name="policy-simulate"),
    path("simulations/", SimulationHistoryView.as_view(), name="policy-simulations"),
    path("optimize/", OptimizePortfolioView.as_view(), name="policy-optimize"),
    path("compare/", ComparePoliciesView.as_view(), name="policy-compare"),
    path("recommendations/", RecommendationsView.as_view(), name="policy-recommendations"),
    path("apply/", ApplyPolicyView.as_view(), name="policy-apply"),
    path("applied/", AppliedPoliciesView.as_view(), name="policy-applied"),
    path("outcomes/summary/", PolicyOutcomesSummaryView.as_view(), name="policy-outcomes-summary"),
    path(
        "applied/<uuid:pk>/outcome/",
        RecordPolicyOutcomeView.as_view(),
        name="policy-applied-outcome",
    ),
    path("demo-data/reset/", ResetDemoDataView.as_view(), name="policy-demo-reset"),
    # Document generation (PDF)
    path("employees/", EmployeeListView.as_view(), name="policy-employees"),
    path("employees/<uuid:pk>/contract/", EmployeeContractPDFView.as_view(), name="policy-employee-contract"),
    path("documents/templates/", PolicyTemplatesView.as_view(), name="policy-doc-templates"),
    path("documents/policy/", PolicyDocumentPDFView.as_view(), name="policy-doc-generate"),
]
