from django.core.management.base import BaseCommand

from company.models import Company

# H F Flex exactly as its letterhead is typed into the purchase order PDFs and
# the dispatch challan page today (purchase/pdfviews.py, dispatch detail), so
# the first Company row reproduces what those documents already say. The GSTIN
# matches Customer "H F FLEX PRIVATE LIMITED".
HF_FLEX = dict(
    name='H F FLEX PVT. LTD.',
    gstin='27AADCH3462K1ZF',
    address_line1='25, Lucky Lark Textile Park, Gardi, Vita',
    address_line2='Tal- Khanapur, Dist- Sangli, Maharashtra-415311',
    phone='8552827683, 9765643576',
    email='hfflexpvtltd@gmail.com',
    website='www.hfflex.co.in',
    is_default=True,
)


class Command(BaseCommand):
    help = (
        'Create the H F Flex company row from the letterhead details typed into the '
        'documents today. Safe to re-run: it never changes a company that already exists. '
        'Other companies (e.g. H F Printpack) are added in the admin.'
    )

    def handle(self, *args, **options):
        company, created = Company.objects.get_or_create(short_name='HF', defaults=HF_FLEX)
        if created:
            self.stdout.write(self.style.SUCCESS(f'Created {company.name} (default company).'))
        else:
            self.stdout.write(f'{company.name} already exists -- left as it is.')
