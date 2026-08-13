from django.core.management.base import BaseCommand
from django.db import transaction
from crm.models import Pipeline, DealStageName, DealStage

DATA_SEARCH_STAGES = [
    ('Data Search', 0, False, False),
    ('Filtered Lead', 0, False, False),
    ('Calling', 0, False, False),
    ('Conversation', 0, False, False),
    ('Need Analysis', 0, False, False),
    ('Courier', 0, False, False),
    ('Quote', 0, False, False),
    ('Personal Visit', 1, False, False),
    ('Customer Visit', 1, False, False),
    ('Waiting', 1, False, False),          # ADD THIS
    ('Sample Design', 5, False, False),
    ('Design', 100, False, False),
    ('Final Deal', 100, False, False),
    ('Advance', 100, False, False),
    ('Closed Won', 100, True, False),
    ('Closed Lost', 0, False, True),
    ('Closed-Lost to Competition', 0, False, True),
]

VISIT_STAGES = [
    ('Data Search', 0, False, False),
    ('Filtered Lead', 0, False, False),
    ('Identify Decision Makers', 60, False, False),
    ('Introduction Email', 0, False, False),
    ('First Call', 0, False, False),
    ('Second Call', 0, False, False),
    ('Gate Visit', 0, False, False),
    ('Re-Gate Visit', 0, False, False),
    ('Personal Visit', 1, False, False),
    ('Customer Visit', 1, False, False),   # ADD THIS
    ('Social Media Relation', 0, False, False),
    ('Conversation', 0, False, False),
    ('Calling', 0, False, False),
    ('Need Analysis', 0, False, False),
    ('Quote', 0, False, False),
    ('Waiting', 1, False, False),
    ('Courier', 0, False, False),
    ('Final Deal', 100, False, False),     # ADD THIS
    ('Closed Won', 100, True, False),
    ('Closed Lost', 0, False, True),
]

PIPELINES = {
    'DATA SEARCH': DATA_SEARCH_STAGES,
    'VISIT': VISIT_STAGES,
}


from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import F
from crm.models import Pipeline, DealStageName, DealStage

# ... DATA_SEARCH_STAGES, VISIT_STAGES, PIPELINES dicts stay exactly as they are ...

class Command(BaseCommand):
    help = 'Seeds the DATA SEARCH and VISIT pipelines with their real stage lists and probabilities'

    @transaction.atomic
    def handle(self, *args, **options):
        for pipeline_name, stages in PIPELINES.items():
            pipeline, created = Pipeline.objects.get_or_create(name=pipeline_name)
            verb = 'Created' if created else 'Found existing'
            self.stdout.write(f'{verb} pipeline: {pipeline_name}')

            # Push all existing orders for this pipeline well out of the way first,
            # so reassigning final order values below can never collide mid-loop.
            DealStage.objects.filter(pipeline=pipeline).update(order=F('order') + 10000)

            for order, (stage_name, probability, is_won, is_lost) in enumerate(stages, start=1):
                stage_name_obj, _ = DealStageName.objects.get_or_create(name=stage_name)

                stage, created = DealStage.objects.update_or_create(
                    pipeline=pipeline,
                    dealstagename=stage_name_obj,
                    defaults={
                        'order': order,
                        'probability': probability,
                        'is_won': is_won,
                        'is_lost': is_lost,
                    },
                )
                verb = 'Created' if created else 'Updated'
                self.stdout.write(f'  {verb} stage: {stage_name} (order={order}, prob={probability}%)')

        self.stdout.write(self.style.SUCCESS('Done seeding CRM pipelines and stages.'))