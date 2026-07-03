"""Module 4 tests: analytics, simulation fallback logic, authorization.

Groq is not configured in tests — the service must degrade to the
static prediction/recommendation logic.
"""

import time
from unittest import mock

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.test import TestCase, override_settings

from smarthr360_jwt_auth import conf

from ..models import Employe
from ..services.policy import DemoDataService, PolicySimulatorService

_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE_PEM = _key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
PUBLIC_PEM = (
    _key.public_key()
    .public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)


def bearer(user_id=1, role="HR"):
    token = jwt.encode(
        {
            "token_type": "access",
            "user_id": user_id,
            "email": f"u{user_id}@corp.com",
            "role": role,
            "groups": [],
            "iss": "smarthr360",
            "exp": int(time.time()) + 300,
        },
        PRIVATE_PEM,
        algorithm="RS256",
    )
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


class PolicyGenTests(TestCase):
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

    def test_analytics_reflect_seeded_data(self):
        resp = self.client.get("/api/policy/analytics/", **bearer())
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        # 5 terminated of 25 employees = 20% turnover
        self.assertEqual(body["turnover_rate"], 20.0)
        self.assertGreater(body["avg_performance"], 0)
        self.assertEqual(body["retention_stats"]["total"], 10)

    def test_simulation_static_fallback_without_groq(self):
        impact = PolicySimulatorService.simulate_policy_impact("salary_increase", 5)
        self.assertLess(impact["turnover_change"], 0)
        self.assertGreater(impact["cost_estimate"], 0)

        # zero-cost policies stay free
        free = PolicySimulatorService.simulate_policy_impact("mentorship", 5)
        self.assertEqual(free["cost_estimate"], 0.0)

    def test_simulate_endpoint_validation(self):
        bad_type = self.client.post(
            "/api/policy/simulate/",
            {"policy_type": "yachts_for_all", "magnitude": 5},
            content_type="application/json",
            **bearer(),
        )
        self.assertEqual(bad_type.status_code, 400)

        bad_mag = self.client.post(
            "/api/policy/simulate/",
            {"policy_type": "remote_work", "magnitude": 50},
            content_type="application/json",
            **bearer(),
        )
        self.assertEqual(bad_mag.status_code, 400)

        ok = self.client.post(
            "/api/policy/simulate/",
            {"policy_type": "remote_work", "magnitude": 5},
            content_type="application/json",
            **bearer(),
        )
        self.assertEqual(ok.status_code, 200, ok.content)
        self.assertIn("turnover_change", ok.json()["impact"])

    def test_recommendations_sorted_by_cost(self):
        resp = self.client.get("/api/policy/recommendations/", **bearer())
        self.assertEqual(resp.status_code, 200)
        recs = resp.json()["recommendations"]
        self.assertTrue(recs)
        costs = [r["estimated_cost_mad"] for r in recs]
        self.assertEqual(costs, sorted(costs))

    def test_apply_policy_changes_indicators(self):
        before = Employe.objects.filter(status="terminated").count()
        resp = self.client.post(
            "/api/policy/apply/",
            {"policy_type": "salary_increase", "magnitude": 5},
            content_type="application/json",
            **bearer(),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        after = Employe.objects.filter(status="terminated").count()
        self.assertLess(after, before)  # retention simulated

    def test_hr_only(self):
        for method, url in (
            ("get", "/api/policy/analytics/"),
            ("get", "/api/policy/recommendations/"),
            ("post", "/api/policy/simulate/"),
            ("post", "/api/policy/apply/"),
        ):
            resp = getattr(self.client, method)(url, **bearer(9, "EMPLOYEE"))
            self.assertEqual(resp.status_code, 403, url)
        self.assertEqual(
            self.client.get("/api/policy/analytics/").status_code, 401
        )


LIVE_STATS = {
    "source": "smarthr360-core-hr (live)",
    "headcount": 40, "active": 36, "turnover": 10.0,
    "performance": 3.4, "reviews_counted": 25,
}


class LiveWiringTests(PolicyGenTests.__bases__[0]):
    """Cross-service wiring: analytics/simulation over LIVE core-hr data."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._s2 = override_settings(
            SMARTHR_JWT_AUTH={"PUBLIC_KEY": PUBLIC_PEM, "ISSUER": "smarthr360"}
        )
        cls._s2.enable()
        conf.clear_cache()

    @classmethod
    def tearDownClass(cls):
        cls._s2.disable()
        conf.clear_cache()
        super().tearDownClass()

    @mock.patch("policies.views.CoreHRClient")
    def test_live_analytics(self, MockHR):
        MockHR.return_value.get_live_stats.return_value = LIVE_STATS
        resp = self.client.get("/api/policy/analytics/?source=live", **bearer())
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body["headcount"], 40)
        self.assertEqual(body["turnover_rate"], 10.0)
        self.assertIn("live", body["source"])

    @mock.patch("policies.views.CoreHRClient")
    def test_live_simulation_scales_cost_by_live_headcount(self, MockHR):
        MockHR.return_value.get_live_stats.return_value = LIVE_STATS
        resp = self.client.post(
            "/api/policy/simulate/",
            {"policy_type": "remote_work", "magnitude": 5, "use_live": True},
            content_type="application/json",
            **bearer(),
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertIn("live", body["data_source"])
        # static fallback: 3000 * 5 * 40 live headcount
        self.assertEqual(body["impact"]["cost_estimate"], 3000 * 5 * 40)

    @mock.patch("policies.views.CoreHRClient")
    def test_core_hr_down_yields_502(self, MockHR):
        from policies.clients import ServiceError

        MockHR.return_value.get_live_stats.side_effect = ServiceError("boom")
        resp = self.client.get("/api/policy/analytics/?source=live", **bearer())
        self.assertEqual(resp.status_code, 502)

    def test_local_mode_unchanged(self):
        resp = self.client.get("/api/policy/analytics/", **bearer())
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["source"], "local analytical store")
