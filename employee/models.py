from django.db import models
from django.contrib.auth.models import User


class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.PROTECT)
    designation = models.CharField(max_length=64, null=False, blank=True)
    picture = models.ImageField(upload_to='pictures/%Y/%m/%d/', max_length=255, null=True, blank=True)
    mobile = models.CharField(max_length=16, null=True, blank=True)
    icard = models.ImageField(upload_to='pictures/%Y/%m/%d/', max_length=255, null=True, blank=True)
    dob = models.DateField(null=True, blank=True)
    doj = models.DateField(null=True, blank=True)
    dor = models.DateField(null=True, blank=True)
    prefix = models.CharField(max_length=8, choices=(['Mr.', 'Mr.'], ['Mrs.', 'Mrs.'], ['Miss', 'Miss'],['Ms.','Ms.']), null=True)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='profilecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='profileedited')

    class Meta:
        ordering = ('-id',)

    def __str__(self):
        return "{0} - {1}".format(self.user.username, self.designation)


class ViewName(models.Model):
    viewname = models.CharField(max_length=50, unique=True)
    remark = models.CharField(max_length=500)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='viewnamecreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='viewnameedited')

    def __str__(self):
        return self.viewname + " :- (" + self.remark + " = " + str(self.id) + " )"


class Access(models.Model):
    username = models.ForeignKey(User, related_name='accesses', on_delete=models.PROTECT)
    viewname = models.ForeignKey(ViewName, on_delete=models.PROTECT)
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='accesscreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='accessedited')

    def __str__(self):
        return str(self.viewname)

    class Meta:
        # unique_together = ("username", "viewname")
        ordering = ["id"]


class ViewAccess(models.Model):
    viewname = models.CharField(max_length=50)
    username = models.ManyToManyField(Profile, related_name='viewaccess')
    created = models.DateTimeField(auto_now_add=True)
    createdby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT,
                                  related_name='viewaccesscreated')
    edited = models.DateTimeField(auto_now=True)
    editedby = models.ForeignKey(User, null=True, blank=True, on_delete=models.PROTECT, related_name='viewacessedited')


class Worker(models.Model):
    worker_name = models.CharField(max_length=64)
    emp_code = models.CharField(max_length=5, null=True, blank=True)
    profile_image = models.ImageField(upload_to='worker/profile/', null=True, blank=True)
    adhaar_card = models.ImageField(upload_to='worker/adhaar_card/', null=True, blank=True)
    agreement = models.ImageField(upload_to='worker/agreement/', null=True, blank=True)
    date_of_join = models.DateField()
    date_of_releave = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return str(self.worker_name+ " - " + (self.emp_code or "No-id"))

class Salary(models.Model):
    worker=models.ForeignKey(Worker,on_delete=models.PROTECT, related_name="monthlysalaries")
    salary=models.PositiveIntegerField(default=0)
    from_date=models.DateField()
    to_date=models.DateField(null=True, blank=True)
    
    def __str__(self):
        return str(self.salary)
    
    class Meta:
        ordering=["from_date"]
    
class Department(models.Model):
    department_name=models.CharField(max_length=32)
    user=models.ManyToManyField(User,blank=True,related_name='department')

    def __str__(self):
        return self.department_name



