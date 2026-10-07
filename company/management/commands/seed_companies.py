from django.core.management.base import BaseCommand

from company.defaults import HF_FLEX
from company.models import Company

class Command(BaseCommand):
    help = (
        'Create the H F Flex company row from the letterhead details typed into the '
        'documents today. Safe to re-run: it never changes a company that already exists. '
        'Other companies (e.g. H F Printpack) are added in the admin.'
    )

    def handle(self, *args, **options):
        # Recognise an existing H F Flex by its GSTIN (or its name), not by the
        # short code: the code is edited in the admin (FLEX, HF, ...), and
        # looking it up by 'HF' would try to create a second copy and crash
        # on the unique name.
        existing = (Company.objects.filter(gstin=HF_FLEX['gstin']).first()
                    or Company.objects.filter(name=HF_FLEX['name']).first())
        if existing:
            self.stdout.write(f'{existing.name} already exists -- left as it is.')
            return
        company = Company.objects.create(**HF_FLEX)
        self.stdout.write(self.style.SUCCESS(f'Created {company.name} (default company).'))
