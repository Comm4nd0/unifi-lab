from django.core.management.base import BaseCommand

from netsim.seed import seed_demo_site


class Command(BaseCommand):
    help = "Create an example virtual site to explore."

    def add_arguments(self, parser):
        parser.add_argument("--name", default="Chiltern View")

    def handle(self, *args, **options):
        site = seed_demo_site(options["name"])
        self.stdout.write(self.style.SUCCESS(f"Created site {site.name} (id={site.pk})"))
