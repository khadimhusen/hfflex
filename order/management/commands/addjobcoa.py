from django.core.management.base import BaseCommand, CommandError
from order.models import Job, JobCoa
from itemmaster.models import ItemStandardParameter


class Command(BaseCommand):
    help = 'Create MachineSchedule for pending JobProcess records of a given job (no schedule yet)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--job_id',
            type=int,
            required=True,
            help='Only create schedules for JobProcess records belonging to this job ID',
        )

    def handle(self, *args, **kwargs):
        job_id = kwargs['job_id']

        # Find JobProcess with no schedule, job pending, process pending — scoped to job_id
        job = Job.objects.get(id=job_id)

        if job is None:
            raise CommandError(
                f"No Job with job_id={job_id}"
            )
        if job.jobcoa.count() > 0:
            raise CommandError(
                f"all ready coa added to job {job}"
            )


        from itemmaster.models import ItemStandardParameter

        jobcoas = ItemStandardParameter.objects.filter(itemmaster=job.itemmaster)

        for itemtestparam in jobcoas:
            JobCoa.objects.create(job=job, standard_parameter=itemtestparam.standard_parameter,
                                  value=itemtestparam.value)

        self.stdout.write(
            self.style.SUCCESS(f"\n Coa added to {job}")
        )
