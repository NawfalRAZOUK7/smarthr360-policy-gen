"""Tests for applied-policy outcome tracking (loop-closer).

Reuses the RS256 identity harness (``PUBLIC_PEM`` / ``bearer``) from
``test_policy_api``.
"""

from django.test import TestCase, override_settings

from smarthr360_jwt_auth import conf

from ..models import SimulationRun
from .test_policy_api import PUBLIC_PEM, bearer


@override_settings(SMARTHR_JWT_AUTH={"PUBLIC_KEY": PUBLIC_PEM, "ISSUER": "smarthr360"})
class AppliedPolicyOutcomeTests(TestCase):
    def setUp(self):
        conf.clear_cache()

    def _apply(self):
        resp = self.client.post(
            "/api/policy/apply/",
            data={"policy_type": "salary_increase", "magnitude": 5},
            content_type="application/json",
            **bearer(role="HR"),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()

    def test_apply_persists_tracked_policy(self):
        body = self._apply()
        self.assertIn("applied_id", body)
        run = SimulationRun.objects.get(pk=body["applied_id"])
        self.assertTrue(run.scenario["applied"])
        self.assertIn("predicted", run.result)

        # It shows up in the applied list, untracked so far.
        listed = self.client.get("/api/policy/applied/", **bearer(role="HR")).json()
        self.assertEqual(listed["count"], 1)
        self.assertEqual(listed["tracked_count"], 0)
        self.assertIsNone(listed["applied"][0]["outcome"])

    def test_record_outcome_computes_variance(self):
        applied_id = self._apply()["applied_id"]
        predicted = SimulationRun.objects.get(pk=applied_id).result["predicted"]

        # Observe a turnover change that beats prediction by 1 point.
        observed = round(predicted["turnover_change"] - 1.0, 2)
        resp = self.client.post(
            f"/api/policy/applied/{applied_id}/outcome/",
            data={
                "observed_turnover_change": observed,
                "observed_cost": 12000,
                "note": "Q2 review",
            },
            content_type="application/json",
            **bearer(role="HR"),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body["outcome"]["observed_turnover_change"], observed)
        self.assertEqual(body["variance"]["turnover_variance"], -1.0)
        self.assertTrue(body["variance"]["delivered"])

        listed = self.client.get("/api/policy/applied/", **bearer(role="HR")).json()
        self.assertEqual(listed["tracked_count"], 1)

    def test_outcome_requires_a_metric(self):
        applied_id = self._apply()["applied_id"]
        resp = self.client.post(
            f"/api/policy/applied/{applied_id}/outcome/",
            data={"note": "nothing measured"},
            content_type="application/json",
            **bearer(role="HR"),
        )
        self.assertEqual(resp.status_code, 400, resp.content)

    def test_non_hr_forbidden(self):
        self.assertEqual(
            self.client.get("/api/policy/applied/", **bearer(role="EMPLOYEE")).status_code,
            403,
        )

    def test_applied_requires_auth(self):
        self.assertEqual(self.client.get("/api/policy/applied/").status_code, 401)

    def test_outcomes_summary_aggregates_by_type(self):
        # One applied policy with a delivering outcome + one untracked.
        applied_id = self._apply()["applied_id"]
        predicted = SimulationRun.objects.get(pk=applied_id).result["predicted"]
        observed = round(predicted["turnover_change"] - 1.0, 2)  # beats prediction
        self.client.post(
            f"/api/policy/applied/{applied_id}/outcome/",
            data={"observed_turnover_change": observed, "observed_cost": 12000},
            content_type="application/json",
            **bearer(role="HR"),
        )
        self._apply()  # second applied, untracked

        summary = self.client.get(
            "/api/policy/outcomes/summary/", **bearer(role="HR")
        ).json()
        self.assertEqual(summary["applied_count"], 2)
        self.assertEqual(summary["tracked_count"], 1)
        self.assertEqual(summary["delivered_count"], 1)
        self.assertEqual(summary["delivered_rate"], 1.0)
        row = next(
            r for r in summary["by_policy_type"] if r["policy_type"] == "salary_increase"
        )
        self.assertEqual(row["applied"], 2)
        self.assertEqual(row["tracked"], 1)
        self.assertEqual(row["delivered"], 1)

    def test_outcomes_summary_hr_only(self):
        self.assertEqual(
            self.client.get(
                "/api/policy/outcomes/summary/", **bearer(role="EMPLOYEE")
            ).status_code,
            403,
        )
