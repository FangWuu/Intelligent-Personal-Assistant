from django.urls import path
from .views import process_command, register, login, logout, create_task, delete_task, list_task, save_user_location

urlpatterns = [
    path('register/', register, name='register'),
    path('login/', login, name='login'),
    path('logout/', logout, name='logout'),
    path('process-command/', process_command, name='process_command'),
    path('create-task/', create_task, name='create_task'),
    path('delete-task/<int:task_id>/', delete_task, name='delete_task'),
    path('list-task/', list_task, name='list_task'),
    path('save-location/', save_user_location, name='save_user_location'),
]