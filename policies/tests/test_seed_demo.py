from django.core.management import call_command
from django.test import TestCase

from policies.models import Employe, SimulationRun


class SeedDemoTests(TestCase):
    def test_seed_demo_is_idempotent(self):
        call_command("seed_demo")
        first = (Employe.objects.count(), SimulationRun.objects.filter(scenario__seed_key__startswith="coherent-demo-").count())
        call_command("seed_demo")
        self.assertEqual((Employe.objects.count(), SimulationRun.objects.filter(scenario__seed_key__startswith="coherent-demo-").count()), first)
