import uuid
from django.db import models
from django.utils import timezone

class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    code = models.TextField(null=True, blank=True)
    parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='sub_departments')
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class JobTitle(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    level = models.IntegerField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class Employe(models.Model):
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('terminated', 'Terminated'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee_number = models.TextField(unique=True, null=True, blank=True)
    first_name = models.TextField()
    last_name = models.TextField()
    email = models.TextField(unique=True)
    phone = models.TextField(null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    hire_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True)
    status = models.TextField(choices=STATUS_CHOICES, default='active')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    job_title = models.ForeignKey(JobTitle, on_delete=models.SET_NULL, null=True, blank=True)
    manager = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='subordinates')
    location = models.TextField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        db_table = 'core_employe'  # Nom de la table en base de données

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    category = models.TextField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name

class EmployeeSkill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.CASCADE)
    skill = models.ForeignKey(Skill, on_delete=models.CASCADE)
    proficiency = models.SmallIntegerField(null=True, blank=True)
    last_assessed_at = models.DateTimeField(null=True, blank=True)
    source = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'skill')

class Training(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.TextField()
    provider = models.TextField(null=True, blank=True)
    training_type = models.TextField(null=True, blank=True)
    duration_minutes = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class EmployeeTraining(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.CASCADE)
    training = models.ForeignKey(Training, on_delete=models.CASCADE)
    status = models.TextField(default='planned')
    assigned_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = ('employee', 'training')

class PerformanceReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='reviews')
    reviewer = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='given_reviews')
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    summary = models.TextField(null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class Contract(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.CASCADE)
    contract_type = models.TextField(null=True, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    hours_per_week = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    salary_reference_id = models.UUIDField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class Salary(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.CASCADE)
    base_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=3, default='EUR')
    pay_frequency = models.TextField(null=True, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    employer_costs = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class PayrollRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    run_name = models.TextField(null=True, blank=True)
    run_date = models.DateTimeField(default=timezone.now)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)
    status = models.TextField(default='pending')
    metadata = models.JSONField(null=True, blank=True)

class PayrollItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payroll_run = models.ForeignKey(PayrollRun, on_delete=models.CASCADE)
    employee = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True)
    gross_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    taxes = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    deductions = models.JSONField(null=True, blank=True)
    employer_costs = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    details = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class RetentionOffer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.CASCADE)
    offer_type = models.TextField(null=True, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=3, default='EUR')
    offered_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    status = models.TextField(default='offered')
    context = models.JSONField(null=True, blank=True)

class CareerPath(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class CareerPathStep(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    career_path = models.ForeignKey(CareerPath, on_delete=models.CASCADE)
    title = models.TextField()
    level = models.IntegerField(null=True, blank=True)
    # recommended_trainings handled via M2M or JSON if simple
    recommended_trainings = models.JSONField(null=True, blank=True) # Storing IDs as JSON for simplicity as per schema array
    expected_duration_days = models.IntegerField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    position = models.IntegerField(null=True, blank=True)

class SimulationRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True)
    career_path = models.ForeignKey(CareerPath, on_delete=models.SET_NULL, null=True, blank=True)
    scenario = models.JSONField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class CompetencePrediction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True)
    skill = models.ForeignKey(Skill, on_delete=models.SET_NULL, null=True, blank=True)
    predicted_proficiency = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    confidence = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    model_version = models.TextField(null=True, blank=True)
    features = models.JSONField(null=True, blank=True)
    predicted_at = models.DateTimeField(default=timezone.now)

class Template(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.TextField()
    template_type = models.TextField(null=True, blank=True)
    content = models.TextField(null=True, blank=True)
    variables = models.JSONField(null=True, blank=True)
    owner = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.TextField()
    target_table = models.TextField(null=True, blank=True)
    target_id = models.UUIDField(null=True, blank=True)
    changes = models.JSONField(null=True, blank=True)
    ip_address = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)

class Integration(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    system_name = models.TextField()
    config = models.JSONField(null=True, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now)

class Setting(models.Model):
    key = models.TextField(primary_key=True)
    value = models.JSONField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    updated_at = models.DateTimeField(default=timezone.now)
