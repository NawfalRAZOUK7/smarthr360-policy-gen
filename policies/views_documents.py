"""Document-generation APIs for policy-gen.

Turns the service's HR data into downloadable PDFs — employment contracts per
employee, and internal HR policy documents. All endpoints are HR-gated and
return ``application/pdf`` as an attachment so the frontend's authenticated
download helper streams them to the browser.
"""

from django.http import HttpResponse
from rest_framework import status
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from smarthr360_jwt_auth.access import has_hr_access

from .models import Contract, Employe, Salary
from .services.documents import POLICY_TEMPLATES, build_contract_pdf, build_policy_pdf


def _require_hr(request):
    if not has_hr_access(request.user):
        raise PermissionDenied("HR or Admin role required.")


def _pdf_response(pdf_bytes: bytes, filename: str) -> HttpResponse:
    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    resp["Content-Length"] = str(len(pdf_bytes))
    return resp


class EmployeeListView(APIView):
    """GET /api/policy/employees/ — employees available for document generation."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        qs = (
            Employe.objects.select_related("department", "job_title")
            .order_by("last_name", "first_name")[:200]
        )
        employees = [
            {
                "id": str(e.id),
                "name": f"{e.first_name} {e.last_name}".strip(),
                "employee_number": e.employee_number,
                "email": e.email,
                "department": getattr(e.department, "name", None),
                "job_title": getattr(e.job_title, "name", None),
                "status": e.status,
            }
            for e in qs
        ]
        return Response({"employees": employees, "count": len(employees)})


class EmployeeContractPDFView(APIView):
    """GET /api/policy/employees/<uuid>/contract/ — employment contract PDF."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        _require_hr(request)
        try:
            emp = Employe.objects.select_related("department", "job_title").get(pk=pk)
        except Employe.DoesNotExist:
            raise NotFound("Employee not found.")

        contract = Contract.objects.filter(employee=emp).order_by("-created_at").first()
        salary = Salary.objects.filter(employee=emp).order_by("-effective_from").first()
        pdf = build_contract_pdf(
            emp, contract=contract, salary=salary,
            department=emp.department, job_title=emp.job_title,
        )
        fname = f"contract_{emp.employee_number or str(emp.id)}.pdf"
        return _pdf_response(pdf, fname)


class PolicyTemplatesView(APIView):
    """GET /api/policy/documents/templates/ — available policy document types."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        templates = [{"policy_type": k, "title": v[0]} for k, v in POLICY_TEMPLATES.items()]
        return Response({"templates": templates})


class PolicyDocumentPDFView(APIView):
    """GET /api/policy/documents/policy/?policy_type=remote_work — policy PDF."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _require_hr(request)
        policy_type = request.query_params.get("policy_type")
        if not policy_type:
            return Response({"detail": "policy_type query param is required."}, status=status.HTTP_400_BAD_REQUEST)
        title = request.query_params.get("title") or None
        pdf = build_policy_pdf(policy_type, title=title)
        return _pdf_response(pdf, f"policy_{policy_type}.pdf")
