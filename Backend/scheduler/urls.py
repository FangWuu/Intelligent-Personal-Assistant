from django.urls import path
from .views import process_command, register, login, logout

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('process-command/', process_command, name='process_command'),
]