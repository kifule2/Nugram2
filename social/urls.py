from django.urls import path
from . import views

app_name = 'social'

urlpatterns = [
    # Main feed URLs
    path('', views.social_feed, name='feed'),
    path('following/', views.following_feed, name='following_feed'),
    
    # Post URLs
    path('create/', views.create_post, name='create_post'),
    path('post/<int:post_id>/', views.post_detail, name='post_detail'),
    path('post/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('post/<int:post_id>/like/', views.like_post, name='like_post'),
    path('post/<int:post_id>/repost/', views.repost, name='repost'),
    
    # Video processing URLs (NEW - for Cloudinary upload)
    path('api/video/process/', views.process_video_vp9, name='process_video_vp9'),
    path('api/video/trim/', views.trim_video_vp9, name='trim_video_vp9'),
    path('api/video/upload-chunk/', views.upload_video_chunk, name='upload_video_chunk'),
    path('api/video-status/<int:media_id>/', views.check_video_status, name='check_video_status'),
    
    # User URLs
    path('follow/<str:username>/', views.toggle_follow, name='toggle_follow'),
    path('user/<str:username>/posts/', views.user_posts, name='user_posts'),
    
    # Notification URLs
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', views.mark_notification_read, name='mark_notification_read'),
    
    # Search URLs
    path('search/users/', views.search_users, name='search_users'),
    path('api/search/', views.search_users_api, name='search_users_api'),
    
    # API URLs
    path('api/templates/', views.get_templates, name='get_templates'),
    path('api/new-posts-count/', views.get_new_posts_count, name='new_posts_count'),
    path('api/unread-notifications/', views.get_unread_notifications_count, name='unread_notifications'),
    path('api/user/<str:username>/stats/', views.get_user_stats, name='user_stats'),
    path('api/video-status/<str:task_id>/', views.video_upload_status, name='video_upload_status'),
    
    # Comments URLs
    path('api/comments/<int:post_id>/', views.get_comments, name='get_comments'),
    path('api/comments/<int:post_id>/add/', views.add_comment, name='add_comment'),
    
    # Debug URLs
    path('check-my-uploads/', views.check_my_uploads, name='check_my_uploads'),
]