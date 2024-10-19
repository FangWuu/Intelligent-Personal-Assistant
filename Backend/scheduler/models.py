from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task_description = models.CharField(max_length=255)
    is_complete = models.BooleanField(default=False)
    task_date = models.DateField(null=True, blank=True) 
    task_time = models.TimeField(null=True, blank=True)
    weather = models.CharField(max_length=255, null=True, blank=True)  

    def __str__(self):
        return f"{self.task_description} - {'Complete' if self.is_complete else 'Incomplete'}"
    
class EventTask(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    event_description = models.CharField(max_length=255)
    date = models.DateField() 
    time = models.TimeField()  
    weather = models.CharField(max_length=255)  
    is_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.event_description} - {'Complete' if self.is_complete else 'Incomplete'} on {self.date} at {self.time}"
    
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    
    def __str__(self):
        return self.user.username