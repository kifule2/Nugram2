from django.urls import path
from . import views

app_name = 'tasks'

urlpatterns = [
    # Main marketplace
    path('', views.task_marketplace, name='marketplace'),
    path('connect/', views.connect_social, name='connect_social'),
    
    # Task actions
    path('task/<str:task_code>/', views.task_detail, name='task_detail'),
    path('task/<str:task_code>/join/', views.join_task, name='join_task'),
    path('task/<str:task_code>/work/', views.task_work, name='task_work'),
    path('task/<str:task_code>/verify/', views.verify_task, name='verify_task'),
    path('task/<str:task_code>/track/', views.track_click, name='track_click'),
    path('task/<str:task_code>/cancel/', views.cancel_request, name='cancel_request'),
    
    # Creator views
    path('my-tasks/', views.my_created_tasks, name='my_created_tasks'),
    path('create/', views.create_task, name='create_task'),
    path('edit/<int:task_id>/', views.edit_task, name='edit_task'),
    path('delete/<int:task_id>/', views.delete_task, name='delete_task'),
    path('approve/<int:request_id>/', views.approve_participant, name='approve_participant'),
    path('reject/<int:request_id>/', views.reject_participant, name='reject_participant'),
    
    # API endpoints
    path('api/search/', views.search_task_api, name='search_task_api'),
    path('api/stats/', views.user_task_stats, name='user_task_stats'),
    path('api/leaderboard/', views.task_leaderboard, name='task_leaderboard'),
    
    # Verification webhook (for external services)
    path('webhook/verify/', views.verification_webhook, name='verification_webhook'),
]