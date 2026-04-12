# social/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.contrib import messages
from .models import Post, PostMedia, Like, Follow, Notification, FeedCache, BackgroundTemplate
from .forms import PostForm
from users.models import CustomUser
#from .video_utils import VideoOptimizer
import cloudinary.uploader
import json
import re
import logging
import os
import tempfile
import time
from django.urls import reverse
from io import BytesIO
from django.conf import settings
import uuid  # Add this import at the top with other imports


logger = logging.getLogger(__name__)

@login_required
def social_feed(request):
    """Main social feed showing all posts"""
    form = PostForm()
    
    # Get or create feed cache
    feed_cache, created = FeedCache.objects.get_or_create(
        user=request.user,
        defaults={'last_seen_post': None}
    )
    
    # Get all posts
    all_posts = Post.objects.filter(
        is_reply=False
    ).select_related(
        'user', 'original_post', 'user__userprofile', 'background_template'
    ).prefetch_related(
        'likes', 'replies', 'views', 'media_items'
    ).order_by('-created_at')
    
    # Count new posts
    if feed_cache.last_seen_post:
        new_posts_count = all_posts.filter(
            created_at__gt=feed_cache.last_seen_post.created_at
        ).count()
    else:
        new_posts_count = all_posts.count()
    
    # Update last seen post
    if all_posts.exists():
        feed_cache.last_seen_post = all_posts.first()
        feed_cache.save()
    
    # Pagination
    paginator = Paginator(all_posts, 20)
    page = request.GET.get('page')
    posts = paginator.get_page(page)
    
    # Check likes and add views
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_following = Follow.objects.filter(
            follower=request.user, 
            following=post.user
        ).exists()
        post.add_view(request.user)
    
    # Get trending users
    trending_users = CustomUser.objects.annotate(
        follower_count=Count('followers_set')
    ).exclude(id=request.user.id).order_by('-follower_count')[:5]
    
    # Get following IDs
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list('following_id', flat=True)
    
    # Get unread notifications
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'form': form,
        'posts': posts,
        'trending_users': trending_users,
        'following_ids': following_ids,
        'feed_title': 'For You',
        'new_posts_count': new_posts_count,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'social/feed.html', context)

@login_required
def following_feed(request):
    """Feed showing posts from followed users"""
    form = PostForm()
    
    following = Follow.objects.filter(
        follower=request.user
    ).values_list('following', flat=True)
    
    posts = Post.objects.filter(
        Q(user__in=following) | Q(user=request.user),
        is_reply=False
    ).select_related(
        'user', 'original_post', 'user__userprofile', 'background_template'
    ).prefetch_related(
        'likes', 'replies', 'views', 'media_items'
    ).order_by('-created_at')
    
    paginator = Paginator(posts, 20)
    page = request.GET.get('page')
    posts = paginator.get_page(page)
    
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.is_following = True
        post.add_view(request.user)
    
    trending_users = CustomUser.objects.annotate(
        follower_count=Count('followers_set')
    ).exclude(id=request.user.id).order_by('-follower_count')[:5]
    
    following_ids = following
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'form': form,
        'posts': posts,
        'trending_users': trending_users,
        'following_ids': following_ids,
        'feed_title': 'Following',
        'unread_notifications': unread_notifications,
    }
    return render(request, 'social/feed.html', context)


import uuid
import os
import tempfile
import cloudinary.uploader
from django.shortcuts import render, reverse
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required

@login_required
def create_post(request):
        # ----- TEXT POST (JSON) -----
    if request.content_type == 'application/json':
        try:
            data = json.loads(request.body)
            content = data.get('content', '').strip()
            if not content:
                return JsonResponse({'status': 'error', 'message': 'Content required'}, status=400)
            
            post = Post.objects.create(
                user=request.user,
                content=content,
                post_type='text'
            )
            return JsonResponse({'status': 'success', 'redirect_url': reverse('social:feed')})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
    if request.method == 'POST' and request.FILES.get('video'):
        video_file = request.FILES['video']
        content = request.POST.get('content', '').strip()
        
        # Get trim parameters from the frontend
        start_time = request.POST.get('start_time', 0)
        end_time = request.POST.get('end_time', None)

        # 1. Validation
        if video_file.size > 90 * 1024 * 1024:
            return JsonResponse({'status': 'error', 'message': 'File too large (Max 90MB)'}, status=400)

        # 2. Save to Temp File
        suffix = os.path.splitext(video_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            for chunk in video_file.chunks():
                tmp_file.write(chunk)
            input_path = tmp_file.name

        try:
            # 3. Cloudinary Async Upload with Trimming
            # We tell Cloudinary to do the trimming on THEIR servers
            eager_transformations = [
                {
                    "format": "webm", 
                    "codec": "vp9", 
                    "start_offset": start_time,
                }
            ]
            if end_time:
                eager_transformations[0]["end_offset"] = end_time

            upload_result = cloudinary.uploader.upload(
                input_path,
                folder=f'nusu/users/{request.user.id}/videos',
                resource_type='video',
                public_id=f"video_{uuid.uuid4().hex[:8]}",
                eager=eager_transformations,
                eager_async=True, # THIS STOPS THE TERMINAL LAG
            )

            # 4. Create Post Record
            post = Post.objects.create(
                user=request.user,
                content=content,
                post_type='media'
            )

            PostMedia.objects.create(
                post=post,
                media_type='video',
                video=upload_result['public_id'],
                file_size=video_file.size
            )

            return JsonResponse({'status': 'success', 'redirect_url': reverse('social:feed')})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
        finally:
            if os.path.exists(input_path):
                os.unlink(input_path)

    # Handle GET request
    templates = BackgroundTemplate.objects.filter(is_active=True)
    return render(request, 'social/create_post.html', {'templates': templates})
    
@login_required
def check_video_status(request, media_id):
    """Check if video processing is complete on Cloudinary"""
    media = get_object_or_404(PostMedia, id=media_id, post__user=request.user)
    
    try:
        # Get resource info from Cloudinary
        result = cloudinary.api.resource(media.video, resource_type='video')
        is_ready = result.get('status') == 'active'
        
        # Update local record with video info if available
        if is_ready and media.duration == 0:
            media.duration = result.get('duration', 0)
            media.width = result.get('width', 0)
            media.height = result.get('height', 0)
            media.format = result.get('format', 'mp4')
            media.save()
        
        return JsonResponse({
            'ready': is_ready,
            'duration': media.duration,
            'width': media.width,
            'height': media.height,
            'url': media.url,
            'thumbnail': media.thumbnail_url
        })
    except Exception as e:
        logger.error(f"Error checking video status: {e}")
        return JsonResponse({'ready': False, 'error': str(e)})


@login_required
def check_my_uploads(request):
    """Debug view to check user's own uploads"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    posts = Post.objects.filter(user=request.user, post_type__in=['media', 'mixed']).order_by('-created_at')[:5]
    
    data = {
        'user': request.user.username,
        'user_id': request.user.id,
        'total_posts': posts.count(),
        'posts': []
    }
    
    for post in posts:
        post_data = {
            'id': post.id,
            'created': str(post.created_at),
            'media_count': post.media_count,
            'media': []
        }
        for media in post.media_items.all():
            media_data = {
                'id': media.id,
                'type': media.media_type,
                'public_id': str(media.image or media.video),
                'url': media.url,
                'thumbnail': media.thumbnail_url,
                'width': media.width,
                'height': media.height,
                'file_size': media.file_size,
                'format': media.format
            }
            post_data['media'].append(media_data)
        data['posts'].append(post_data)
    
    return JsonResponse(data, json_dumps_params={'indent': 2})


@login_required
def get_templates(request):
    """API endpoint to get available background templates"""
    templates = BackgroundTemplate.objects.filter(is_active=True)
    data = []
    for template in templates:
        data.append({
            'id': template.id,
            'name': template.name,
            'type': template.template_type,
            'gradient_css': template.gradient_css,
            'css_class': template.css_class,
            'is_animated': template.is_animated,
            'animation_duration': template.animation_duration,
            'preview_url': template.preview_url,
            'background_url': template.background_url,
            'is_premium': template.is_premium
        })
    return JsonResponse({'templates': data})

@login_required
def post_detail(request, post_id):
    """View a single post with its replies"""
    post = get_object_or_404(
        Post.objects.select_related('user', 'user__userprofile', 'background_template').prefetch_related(
            'media_items', 'likes', 'views'
        ),
        id=post_id
    )
    replies = post.replies.all().select_related(
        'user', 'user__userprofile', 'background_template'
    ).prefetch_related('media_items', 'likes', 'views')
    
    post.add_view(request.user)
    post.is_liked = post.likes.filter(user=request.user).exists()
    
    for reply in replies:
        reply.is_liked = reply.likes.filter(user=request.user).exists()
        reply.add_view(request.user)
    
    if request.method == 'POST':
        content = request.POST.get('content', '').strip()
        
        if content:
            reply = Post.objects.create(
                user=request.user,
                content=content,
                is_reply=True,
                parent_post=post,
                post_type='text'
            )
            
            # Handle reply media
            media_files = request.FILES.getlist('media_files')
            for index, media_file in enumerate(media_files[:4]):
                try:
                    is_video = media_file.content_type.startswith('video/')
                    
                    if is_video:
                        # Optimize video for reply
                        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(media_file.name)[1]) as tmp_file:
                            for chunk in media_file.chunks():
                                tmp_file.write(chunk)
                            temp_input = tmp_file.name
                        
                        try:
                            result = VideoOptimizer.optimize_video(temp_input, output_format='webm')
                            
                            if 'error' not in result:
                                upload_result = cloudinary.uploader.upload(
                                    result['output_path'],
                                    folder=f'nusu/users/{request.user.id}/replies',
                                    resource_type='video'
                                )
                                
                                post_media = PostMedia(
                                    post=reply,
                                    media_type='video',
                                    order=index,
                                    video=upload_result['public_id']
                                )
                                
                                if 'duration' in result:
                                    reply.video_duration = result['duration']
                                    reply.save(update_fields=['video_duration'])
                                
                                post_media.save()
                                
                                # Clean up
                                if os.path.exists(result['output_path']):
                                    os.unlink(result['output_path'])
                        finally:
                            if os.path.exists(temp_input):
                                os.unlink(temp_input)
                    else:
                        upload_result = cloudinary.uploader.upload(
                            media_file,
                            folder=f'nusu/users/{request.user.id}/replies',
                            resource_type='image'
                        )
                        post_media = PostMedia(
                            post=reply,
                            media_type='image',
                            order=index,
                            image=upload_result['public_id']
                        )
                        post_media.save()
                        
                except Exception as e:
                    logger.error(f"Reply upload error: {e}")
            
            if post.user != request.user:
                Notification.objects.create(
                    recipient=post.user,
                    sender=request.user,
                    notification_type='reply',
                    post=reply
                )
            
            messages.success(request, 'Reply posted!')
            return redirect('social:post_detail', post_id=post.id)
    
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'post': post,
        'replies': replies,
        'unread_notifications': unread_notifications,
    }
    return render(request, 'social/post_detail.html', context)

@login_required
@require_POST
def like_post(request, post_id):
    """Like or unlike a post"""
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(user=request.user, post=post)
    
    if not created:
        like.delete()
        liked = False
        Notification.objects.filter(
            sender=request.user,
            recipient=post.user,
            notification_type='like',
            post=post
        ).delete()
    else:
        liked = True
        if post.user != request.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='like',
                post=post
            )
    
    return JsonResponse({
        'liked': liked,
        'likes_count': post.likes_count,
    })

@login_required
@require_POST
def repost(request, post_id):
    """Repost a post"""
    original_post = get_object_or_404(Post, id=post_id)
    
    existing_repost = Post.objects.filter(
        user=request.user,
        original_post=original_post,
        is_repost=True
    ).first()
    
    if existing_repost:
        existing_repost.delete()
        reposted = False
        Notification.objects.filter(
            sender=request.user,
            recipient=original_post.user,
            notification_type='repost',
            post=original_post
        ).delete()
    else:
        repost = Post.objects.create(
            user=request.user,
            content=f"RT: {original_post.content[:250]}",
            is_repost=True,
            original_post=original_post,
            post_type='text',
            song_name=original_post.song_name
        )
        reposted = True
        if original_post.user != request.user:
            Notification.objects.create(
                recipient=original_post.user,
                sender=request.user,
                notification_type='repost',
                post=original_post
            )
    
    return JsonResponse({
        'reposted': reposted,
        'reposts_count': original_post.reposts_count,
    })

@login_required
@require_POST
def delete_post(request, post_id):
    """Delete a post and its media from Cloudinary"""
    post = get_object_or_404(Post, id=post_id, user=request.user)
    
    for media in post.media_items.all():
        try:
            if media.image:
                cloudinary.uploader.destroy(media.image.public_id)
            elif media.video:
                cloudinary.uploader.destroy(media.video.public_id, resource_type='video')
        except:
            pass
    
    post.delete()
    messages.success(request, 'Post deleted')
    return redirect('social:feed')

@login_required
@require_POST
def toggle_follow(request, username):
    """Follow or unfollow a user"""
    user_to_follow = get_object_or_404(CustomUser, username=username)
    
    if request.user == user_to_follow:
        return JsonResponse({'error': 'Cannot follow yourself'}, status=400)
    
    follow, created = Follow.objects.get_or_create(
        follower=request.user,
        following=user_to_follow
    )
    
    if not created:
        follow.delete()
        status = 'unfollowed'
        follower_count = user_to_follow.followers_set.count()
        Notification.objects.filter(
            sender=request.user,
            recipient=user_to_follow,
            notification_type='follow'
        ).delete()
    else:
        status = 'followed'
        follower_count = user_to_follow.followers_set.count()
        Notification.objects.create(
            recipient=user_to_follow,
            sender=request.user,
            notification_type='follow'
        )
    
    return JsonResponse({
        'status': status,
        'follower_count': follower_count,
    })

@login_required
def notifications(request):
    """View all social notifications"""
    notifications_list = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender', 'post').order_by('-created_at')
    
    notifications_list.filter(is_read=False).update(is_read=True)
    
    paginator = Paginator(notifications_list, 20)
    page = request.GET.get('page')
    notifications = paginator.get_page(page)
    
    context = {
        'notifications': notifications,
    }
    return render(request, 'social/notifications.html', context)

@login_required
def mark_notification_read(request, notification_id):
    """Mark a single notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})

@login_required
def search_users(request):
    """Search for users to follow"""
    query = request.GET.get('q', '')
    
    if query:
        users = CustomUser.objects.filter(
            Q(username__icontains=query) | 
            Q(userprofile__display_name__icontains=query)
        ).exclude(id=request.user.id).distinct()[:20]
    else:
        users = []
    
    following_ids = Follow.objects.filter(
        follower=request.user
    ).values_list('following_id', flat=True)
    
    for user in users:
        user.is_following = user.id in following_ids
    
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return render(request, 'social/search_users.html', {
        'users': users,
        'query': query,
        'unread_notifications': unread_notifications
    })

@login_required
def get_new_posts_count(request):
    """API endpoint to get count of new posts"""
    feed_cache, created = FeedCache.objects.get_or_create(
        user=request.user,
        defaults={'last_seen_post': None}
    )
    
    if feed_cache.last_seen_post:
        new_count = Post.objects.filter(
            is_reply=False,
            created_at__gt=feed_cache.last_seen_post.created_at
        ).count()
    else:
        new_count = Post.objects.filter(is_reply=False).count()
    
    return JsonResponse({'new_posts_count': new_count})

@login_required
def get_unread_notifications_count(request):
    """API endpoint to get count of unread notifications"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    return JsonResponse({'unread_count': count})

@login_required
def get_user_stats(request, username):
    """API endpoint to get user stats"""
    user = get_object_or_404(CustomUser, username=username)
    
    followers_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    posts_count = Post.objects.filter(user=user, is_reply=False).count()
    
    return JsonResponse({
        'followers': followers_count,
        'following': following_count,
        'posts': posts_count,
    })

@login_required
def user_posts(request, username):
    """View a specific user's posts"""
    user = get_object_or_404(CustomUser, username=username)
    
    posts = Post.objects.filter(
        user=user,
        is_reply=False
    ).select_related(
        'user', 'user__userprofile', 'background_template'
    ).prefetch_related(
        'media_items', 'likes', 'views'
    ).order_by('-created_at')
    
    is_following = Follow.objects.filter(
        follower=request.user,
        following=user
    ).exists()
    
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.add_view(request.user)
    
    paginator = Paginator(posts, 20)
    page = request.GET.get('page')
    posts = paginator.get_page(page)
    
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'posts': posts,
        'profile_user': user,
        'is_following': is_following,
        'feed_title': f"{user.username}'s Posts",
        'unread_notifications': unread_notifications,
    }
    return render(request, 'social/user_posts.html', context)

@login_required
def video_upload_status(request, task_id):
    """Check status of video upload/optimization"""
    # You could implement this with Celery for async processing
    # For now, return mock status
    return JsonResponse({
        'status': 'processing',
        'progress': 50
    })
    
    
from django.http import JsonResponse
from django.db.models import Q
from social.models import Follow

# social/views.py - Add this if not already present

from django.db.models import Q
from users.models import CustomUser

@login_required
def search_users_api(request):
    """API endpoint for searching users with profile pictures"""
    query = request.GET.get('q', '').strip()
    
    if not query:
        return JsonResponse({'users': []})
    
    # Search by username or display name
    users = CustomUser.objects.filter(
        Q(username__icontains=query) | 
        Q(userprofile__display_name__icontains=query)
    ).select_related('userprofile')[:20]  # Limit to 20 results
    
    # Get current user's following list
    following_ids = set()
    if request.user.is_authenticated:
        from social.models import Follow
        following_ids = set(Follow.objects.filter(
            follower=request.user
        ).values_list('following_id', flat=True))
    
    user_list = []
    for user in users:
        user_list.append({
            'username': user.username,
            'display_name': user.userprofile.display_name if hasattr(user, 'userprofile') else user.username,
            'profile_picture_url': user.userprofile.profile_picture.url if hasattr(user, 'userprofile') and user.userprofile.profile_picture else None,
            'verified': getattr(user.userprofile, 'verified', False) or user.is_verified,
            'is_following': user.id in following_ids,
        })
    
    return JsonResponse({'users': user_list})
    
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import json

def get_comments(request, post_id):
    post = get_object_or_404(Post, id=post_id)
    replies = post.replies.all().select_related('user', 'user__userprofile').order_by('-created_at')
    comments_data = []
    for reply in replies:
        comments_data.append({
            'id': reply.id,
            'content': reply.content,
            'created_at': reply.created_at.isoformat(),
            'author': {
                'username': reply.user.username,
                'profile_pic': reply.user.userprofile.profile_picture.url if hasattr(reply.user, 'userprofile') and reply.user.userprofile.profile_picture else None,
                'verified': getattr(reply.user.userprofile, 'verified', False),
            }
        })
    return JsonResponse({'comments': comments_data})

@require_POST
@csrf_exempt
def add_comment(request, post_id):
    data = json.loads(request.body)
    content = data.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Empty comment'}, status=400)
    post = get_object_or_404(Post, id=post_id)
    comment = Post.objects.create(
        user=request.user,
        content=content,
        is_reply=True,
        parent_post=post,
        post_type='text'
    )
    return JsonResponse({'status': 'success', 'comment_id': comment.id})
    
# Add these imports at the top if not already there
import uuid
import tempfile
import os
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from .video_utils import VideoOptimizer
import cloudinary.uploader

@login_required
@require_POST
@csrf_exempt
def process_video_vp9(request):
    """
    Process uploaded video to VP9 WebM format
    """
    if not request.FILES.get('video'):
        return JsonResponse({'error': 'No video file provided'}, status=400)
    
    video_file = request.FILES['video']
    quality = request.POST.get('quality', 'balanced')
    
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_file.name)[1]) as tmp_file:
        for chunk in video_file.chunks():
            tmp_file.write(chunk)
        input_path = tmp_file.name
    
    try:
        # Get original info
        original_info = VideoOptimizer.get_video_info(input_path)
        
        # Process video to VP9
        result = VideoOptimizer.optimize_video(input_path, output_format='webm', quality=quality)
        
        if not result['success']:
            # Fallback to H.264 if VP9 fails
            logger.warning(f"VP9 failed, falling back to H.264: {result.get('error')}")
            result = VideoOptimizer.optimize_video(input_path, output_format='mp4', quality=quality)
        
        if not result['success']:
            return JsonResponse({'error': result.get('error', 'Video processing failed')}, status=500)
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            result['output_path'],
            folder=f'nusu/users/{request.user.id}/videos',
            resource_type='video',
            public_id=f"video_{uuid.uuid4().hex[:8]}",
            transformation=[
                {'quality': 'auto'},
                {'fetch_format': 'auto'},
                {'format': 'webm' if result['format'] == 'webm' else 'mp4'}
            ]
        )
        
        # Clean up temp files
        os.unlink(input_path)
        os.unlink(result['output_path'])
        
        return JsonResponse({
            'success': True,
            'url': upload_result['secure_url'],
            'public_id': upload_result['public_id'],
            'duration': result['duration'],
            'width': result['width'],
            'height': result['height'],
            'size_mb': result['size_mb'],
            'original_size_mb': original_info.get('size_mb', 0),
            'format': result['format'],
            'codec': result['codec'],
            'compression_ratio': round((1 - result['size_mb'] / original_info.get('size_mb', 1)) * 100, 1) if original_info.get('size_mb') else 0
        })
        
    except Exception as e:
        logger.error(f"Video processing error: {e}")
        if os.path.exists(input_path):
            os.unlink(input_path)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@csrf_exempt
def trim_video_vp9(request):
    """
    Trim video and convert to VP9 WebM
    """
    video_file = request.FILES.get('video')
    start_time = float(request.POST.get('start', 0))
    end_time = float(request.POST.get('end'))
    
    if not video_file:
        return JsonResponse({'error': 'No video file'}, status=400)
    
    # Save uploaded file
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(video_file.name)[1]) as tmp_file:
        for chunk in video_file.chunks():
            tmp_file.write(chunk)
        input_path = tmp_file.name
    
    try:
        # Trim video
        trim_result = VideoOptimizer.trim_video(input_path, start_time, end_time, output_format='webm')
        
        if not trim_result['success']:
            return JsonResponse({'error': trim_result.get('error')}, status=500)
        
        # Upload to Cloudinary
        upload_result = cloudinary.uploader.upload(
            trim_result['output_path'],
            folder=f'nusu/users/{request.user.id}/videos',
            resource_type='video',
            public_id=f"trimmed_{uuid.uuid4().hex[:8]}"
        )
        
        # Clean up
        os.unlink(input_path)
        os.unlink(trim_result['output_path'])
        
        return JsonResponse({
            'success': True,
            'url': upload_result['secure_url'],
            'duration': trim_result['duration'],
            'format': 'webm'
        })
        
    except Exception as e:
        if os.path.exists(input_path):
            os.unlink(input_path)
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
@csrf_exempt
def upload_video_chunk(request):
    """
    Handle large video uploads in chunks
    """
    chunk = request.FILES.get('chunk')
    chunk_index = int(request.POST.get('chunk_index', 0))
    total_chunks = int(request.POST.get('total_chunks', 1))
    upload_id = request.POST.get('upload_id')
    
    if not upload_id:
        upload_id = uuid.uuid4().hex
    
    # Create temp directory for chunks
    chunk_dir = os.path.join(tempfile.gettempdir(), f'video_upload_{upload_id}')
    os.makedirs(chunk_dir, exist_ok=True)
    
    # Save chunk
    chunk_path = os.path.join(chunk_dir, f'chunk_{chunk_index}')
    with open(chunk_path, 'wb') as f:
        for chunk_data in chunk.chunks():
            f.write(chunk_data)
    
    # Check if all chunks received
    received_chunks = len([f for f in os.listdir(chunk_dir) if f.startswith('chunk_')])
    
    if received_chunks == total_chunks:
        # Combine chunks
        output_path = os.path.join(tempfile.gettempdir(), f'complete_{upload_id}.mp4')
        with open(output_path, 'wb') as outfile:
            for i in range(total_chunks):
                chunk_path = os.path.join(chunk_dir, f'chunk_{i}')
                with open(chunk_path, 'rb') as infile:
                    outfile.write(infile.read())
        
        # Clean up chunks
        import shutil
        shutil.rmtree(chunk_dir)
        
        # Process the complete video
        result = VideoOptimizer.optimize_video(output_path, output_format='webm')
        
        if result['success']:
            upload_result = cloudinary.uploader.upload(
                result['output_path'],
                folder=f'nusu/users/{request.user.id}/videos',
                resource_type='video'
            )
            os.unlink(output_path)
            os.unlink(result['output_path'])
            
            return JsonResponse({
                'success': True,
                'url': upload_result['secure_url'],
                'upload_id': upload_id
            })
    
    return JsonResponse({
        'success': True,
        'upload_id': upload_id,
        'received_chunks': received_chunks,
        'total_chunks': total_chunks,
        'completed': received_chunks == total_chunks
    })    