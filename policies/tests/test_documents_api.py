"""Tests for the PDF document-generation endpoints (Phase 2).

Reuses the RS256 ``bearer`` harness and demo-data seeding from
``test_policy_api`` so contracts/policies are generated from real employee rows.
"""

from django.test import TestCase, override_settings

from smarthr360_jwt_auth import conf

from ..models import Employe
from ..services.policy import DemoDataService
from .test_policy_api import PUBLIC_PEM, bearer


class DocumentApiTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._s = override_settings(
            SMARTHR_JWT_AUTH={"PUBLIC_KEY": PUBLIC_PEM, "ISSUER": "smarthr360"}
        )
        cls._s.enable()
        conf.clear_cache()

    @classmethod
    def tearDownClass(cls):
        cls._s.disable()
        conf.clear_cache()
        super().tearDownClass()

    def setUp(self):
        DemoDataService.reset_and_populate()

    def test_employee_list_is_hr_gated(self):
        # HR sees the list.
        resp = self.client.get("/api/policy/employees/", **bearer(role="HR"))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertGreater(resp.json()["count"], 0)
        # A plain employee is forbidden.
        self.assertEqual(
            self.client.get("/api/policy/employees/", **bearer(role="EMPLOYEE")).status_code,
            403,
        )
        # Anonymous is unauthorized.
        self.assertEqual(self.client.get("/api/policy/employees/").status_code, 401)

    def test_contract_pdf_is_generated(self):
        emp = Employe.objects.first()
        resp = self.client.get(f"/api/policy/employees/{emp.id}/contract/", **bearer(role="HR"))
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp["Content-Type"], "application/pdf")
        self.assertIn("attachment", resp["Content-Disposition"])
        body = b"".join(resp.streaming_content) if resp.streaming else resp.content
        self.assertTrue(body.startswith(b"%PDF-"))
        self.assertGreater(len(body), 800)

    def test_contract_pdf_unknown_employee_404(self):
        import uuid

        resp = self.client.get(f"/api/policy/employees/{uuid.uuid4()}/contract/", **bearer(role="HR"))
        self.assertEqual(resp.status_code, 404)

    def test_policy_templates_and_document_pdf(self):
        tmpls = self.client.get("/api/policy/documents/templates/", **bearer(role="HR"))
        self.assertEqual(tmpls.status_code, 200, tmpls.content)
        types = {t["policy_type"] for t in tmpls.json()["templates"]}
        self.assertIn("remote_work", types)

        pdf = self.client.get(
            "/api/policy/documents/policy/?policy_type=remote_work", **bearer(role="HR")
        )
        self.assertEqual(pdf.status_code, 200, pdf.content)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        self.assertTrue(pdf.content.startswith(b"%PDF-"))

    def test_policy_document_requires_type(self):
        resp = self.client.get("/api/policy/documents/policy/", **bearer(role="HR"))
        self.assertEqual(resp.status_code, 400)
