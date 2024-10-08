from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Task(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    task_description = models.CharField(max_length=255)  
    is_complete = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.task_description} - {'Complete' if self.is_complete else 'Incomplete'}"