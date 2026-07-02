from django.core.management.base import BaseCommand

from policies.services.policy import DemoDataService


class Command(BaseCommand):
    help = "Reset and populate demo HR data for the policy simulator."

    def handle(self, *args, **options):
        DemoDataService.reset_and_populate()
        self.stdout.write(self.style.SUCCESS("Demo data populated."))
