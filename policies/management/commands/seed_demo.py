from django.core.management.base import BaseCommand
from django.db import transaction

from policies.models import SimulationRun
from policies.services.policy import DemoDataService, PolicySimulatorService


class Command(BaseCommand):
    help = "Reset/populate the policy analytical demo store and tracked outcomes."

    @transaction.atomic
    def handle(self, *args, **options):
        DemoDataService.reset_and_populate()
        SimulationRun.objects.filter(scenario__seed_key__startswith="coherent-demo-").delete()
        policies = (
            ("salary_increase", 5, -3.2, 72000, "Compensation adjustment improved retention."),
            ("mentorship", 8, -2.1, 18000, "Mentoring participation exceeded target."),
            ("training_budget", 12, -1.4, 43000, "Upskilling reduced regretted exits."),
        )
        for index, (policy_type, magnitude, observed_turnover, observed_cost, note) in enumerate(policies, 1):
            predicted = PolicySimulatorService.simulate_policy_impact(policy_type, magnitude)
            SimulationRun.objects.create(
                scenario={"seed_key": f"coherent-demo-{index}", "policy_type": policy_type, "magnitude": magnitude, "applied": True, "applied_by_user_id": 2},
                result={"predicted": predicted, "outcome": {"observed_turnover_change": observed_turnover, "observed_cost": observed_cost, "note": note, "recorded_by_user_id": 2}},
            )
        self.stdout.write(self.style.SUCCESS("Policy analytics and outcomes demo data ready."))
