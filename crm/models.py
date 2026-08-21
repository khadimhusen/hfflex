from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal


class Pipeline(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['id']


class DealStageName(models.Model):
    name = models.CharField(max_length=50, unique=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class DealStage(models.Model):
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT, related_name='stages')
    dealstagename = models.ForeignKey(DealStageName, on_delete=models.PROTECT, related_name='stages')
    order = models.PositiveIntegerField()
    probability = models.PositiveSmallIntegerField(default=0)
    is_won = models.BooleanField(default=False)
    is_lost = models.BooleanField(default=False)
    max_stall_time = models.DurationField(null=True, blank=True)
    color = models.CharField(max_length=7, default='#1976D2')

    class Meta:
        unique_together = [('pipeline', 'dealstagename'), ('pipeline', 'order')]
        ordering = ["pipeline", 'order']
        constraints  = [
            models.CheckConstraint(
                check=~models.Q(is_won=True, is_lost=True),
                name='dealstage_not_won_and_lost',
            ),
        ]

    def __str__(self):
        return f'{self.pipeline} - {self.dealstagename}'

    @property
    def is_open(self):
        return not self.is_won and not self.is_lost


class Account(models.Model):
    zoho_record_id = models.CharField(max_length=30, unique=True, null=True, blank=True)  # for import traceability
    name = models.CharField(max_length=255)
    account_number = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=30, blank=True)

    billing_street = models.CharField(max_length=255, blank=True)
    billing_city = models.CharField(max_length=100, blank=True)
    billing_state = models.CharField(max_length=100, blank=True)
    billing_country = models.CharField(max_length=100, blank=True)
    billing_code = models.CharField(max_length=20, blank=True)

    website = models.URLField(blank=True)
    industry = models.CharField(max_length=100, blank=True)
    annual_revenue = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)

    enquiry_notes = models.TextField(
        blank=True)  # was "Description" — actually stores product/qty/order-value enquiry text

    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='accounts',
                              limit_choices_to={'department__department_name__iexact': 'crm_user'})

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    def __str__(self):
        return self.name


class Contact(models.Model):
    zoho_record_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    salutation = models.CharField(max_length=10, choices=[("Mr.", "Mr."), ("Ms.", "Ms.")], blank=True, null=True)
    first_name = models.CharField(max_length=100, blank=True)  # 58% filled
    last_name = models.CharField(max_length=100)  # 100% filled

    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='contacts')  # 94%

    title = models.CharField(max_length=100, blank=True)  # 71% — designation
    email = models.EmailField(blank=True)  # 67%
    phone = models.CharField(max_length=30, blank=True)  # 74%
    mobile = models.CharField(max_length=30, blank=True)  # 58%

    mailing_street = models.CharField(max_length=255, blank=True)  # 72%
    mailing_city = models.CharField(max_length=100, blank=True)  # 94%
    mailing_state = models.CharField(max_length=100, blank=True)  # 90%
    mailing_country = models.CharField(max_length=100, blank=True)  # 41%
    mailing_zip = models.CharField(max_length=20, blank=True)  # 15%

    lead_source = models.CharField(max_length=50, blank=True)  # 96%
    description = models.TextField(blank=True)  # 68%

    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='contacts',
                              limit_choices_to={'department__department_name__iexact': 'crm_user'}, )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    @property
    def name(self):
        return f'{self.first_name} {self.last_name}'.strip()


class Deal(models.Model):
    zoho_record_id = models.CharField(max_length=30, unique=True, null=True, blank=True)
    name = models.CharField(max_length=255)
    pipeline = models.ForeignKey(Pipeline, on_delete=models.PROTECT)
    stage = models.ForeignKey(DealStage, on_delete=models.PROTECT)
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True, related_name='deals')
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True, related_name='deals')
    amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    deal_type = models.CharField(max_length=30, blank=True)  # "Existing Business" / "New Business"
    city = models.CharField(max_length=100, blank=True)
    lost_reason = models.CharField(max_length=100, blank=True)
    lead_source = models.CharField(max_length=50, blank=True)
    closing_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='deals',
        limit_choices_to={'department__department_name__iexact': 'crm_user'},
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-id']

    @property
    def expected_revenue(self):
        if self.amount is None:
            return 0
        return self.amount * (Decimal(self.stage.probability) / Decimal(100))

    def __str__(self):
        return self.name


class DealStageHistory(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='stage_history')
    from_stage = models.ForeignKey(DealStage, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    to_stage = models.ForeignKey(DealStage, on_delete=models.PROTECT, related_name='+')
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='dealstagechanges')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:

        ordering = ['-id']
        verbose_name_plural = 'Deal stage histories'

    def __str__(self):
        return f'{self.deal} changed from {self.from_stage} to {self.to_stage} by {self.changed_by}'


class Lead(models.Model):
    zoho_record_id = models.CharField(max_length=30, unique=True, null=True, blank=True)

    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    company = models.CharField(max_length=255, blank=True)
    title = models.CharField(max_length=100, blank=True)

    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=30, blank=True)
    mobile = models.CharField(max_length=30, blank=True)

    street = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)

    lead_source = models.CharField(max_length=50, blank=True)
    lead_status = models.CharField(max_length=50, blank=True)
    industry = models.CharField(max_length=100, blank=True)
    annual_revenue = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    description = models.TextField(blank=True)

    im_query_type = models.CharField(max_length=100, blank=True)
    im_query_id = models.CharField(max_length=100, blank=True)
    im_enquiry_time = models.DateTimeField(null=True, blank=True)
    im_product = models.CharField(max_length=255, blank=True)

    is_converted = models.BooleanField(default=False)
    converted_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='converted_from_leads')
    converted_contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name='converted_from_leads')
    converted_deal = models.ForeignKey(Deal, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='converted_from_leads')
    converted_at = models.DateTimeField(null=True, blank=True)

    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='leads',
        limit_choices_to={'department__department_name__iexact': 'crm_user'},
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


    class Meta:
        ordering = ['-created_at']


    @property
    def name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def __str__(self):
        return self.name


class Note(models.Model):
    content = models.TextField()
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, null=True, blank=True, related_name='notes')
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, null=True, blank=True, related_name='notes')
    account = models.ForeignKey(Account, on_delete=models.CASCADE, null=True, blank=True, related_name='notes')
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, null=True, blank=True, related_name='notes')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.content[:50]


def deal_attachment_path(instance, filename):
    return f'deal_attachments/{instance.deal_id}/{filename}'


class DealAttachment(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=deal_attachment_path)
    original_filename = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.original_filename or self.file.name

class DealTask(models.Model):
    PRIORITY_CHOICES = [('High', 'High'), ('Normal', 'Normal'), ('Low', 'Low')]

    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name='tasks')
    subject = models.CharField(max_length=255)
    due_date = models.DateField(null=True, blank=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='Normal')
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name='deal_tasks',
        limit_choices_to={'department__department_name__iexact': 'crm_user'},
    )
    is_closed = models.BooleanField(default=False)

    reminder_enabled = models.BooleanField(default=False)
    reminder_at = models.DateTimeField(null=True, blank=True)
    reminder_dismissed = models.BooleanField(default=False)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['is_closed', 'due_date']

    def __str__(self):
        return self.subject