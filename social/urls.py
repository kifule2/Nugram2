# social/urls.py
from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Main feeds
    path('', views.social_feed, name='feed'),
    path('following/', views.following_feed, name='following_feed'),
    
    # Post creation and management
    path('create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    
    # Interactions
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/repost/', views.repost, name='repost'),
    
    # User interactions
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    path('user/<str:username>/posts/', views.user_posts, name='user_posts'),
    
    # Notifications
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    
    # Search
    path('search/users/', views.search_users, name='search_users'),
    
    # API endpoints
    path('api/templates/', views.get_templates, name='get_templates'),
    path('api/new-posts-count/', views.get_new_posts_count, name='new_posts_count'),
    path('api/unread-notifications/', views.get_unread_notifications_count, name='unread_notifications'),
    path('api/user/<str:username>/stats/', views.get_user_stats, name='user_stats'),
    path('api/video-status/<str:task_id>/', views.video_upload_status, name='video_upload_status'),
    path('check-my-uploads/', views.check_my_uploads, name='check_my_uploads'),
]