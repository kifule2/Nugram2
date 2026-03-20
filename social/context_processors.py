# social/context_processors.py
from .models import Notification, FeedCache, Post

def notification_counts(request):
    """Context processor to add notification counts to all templates"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).count()
        
        try:
            feed_cache = FeedCache.objects.get(user=request.user)
            if feed_cache.last_seen_post:
                new_posts_count = Post.objects.filter(
                    is_reply=False,
                    created_at__gt=feed_cache.last_seen_post.created_at
                ).count()
            else:
                new_posts_count = Post.objects.filter(is_reply=False).count()
        except FeedCache.DoesNotExist:
            new_posts_count = Post.objects.filter(is_reply=False).count()
        
        return {
            'unread_notifications_count': unread_count,
            'new_posts_count': new_posts_count,
        }
    return {
        'unread_notifications_count': 0,
        'new_posts_count': 0,
    }