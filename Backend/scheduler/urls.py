from django.urls import path
from .views import process_command, register, login

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('process-command/', process_command, name='process_command'),
]