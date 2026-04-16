from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Main feed views
    path('', views.social_feed, name='feed'),
    path('following/', views.following_feed, name='following_feed'),
    
    # Post CRUD
    path('create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    
    # Interactions
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/repost/', views.repost, name='repost'),
    
    # Follow system
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    
    # User posts
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
    path('api/search/', views.search_users_api, name='search_users_api'),
    
    # Comments API (if you have them)
    path('api/comments/<int:post_id>/', views.get_comments, name='get_comments'),
    path('api/comments/<int:post_id>/add/', views.add_comment, name='add_comment'),
    
    # Video fallback endpoint (for Chrome compatibility)
    path('api/video-fallback/<int:post_id>/', views.video_fallback_url, name='video_fallback'),
    path('api/upload-audio/', views.upload_audio, name='upload_audio'),
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    path('post/<int:post_id>/repost/', views.repost, name='repost'),
]

# Note: If you don't have these views yet, add them to views.py:
# - post_detail
# - get_comments  
# - add_comment
# - video_fallback_url