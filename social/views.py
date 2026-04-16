from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from django.urls import reverse
import cloudinary.uploader
import json
import logging
import time
from datetime import datetime

from .models import Post, PostMedia, Like, Follow, Notification, FeedCache, BackgroundTemplate
from .forms import PostForm, BackgroundTemplateForm
from users.models import CustomUser

logger = logging.getLogger(__name__)


@login_required
def social_feed(request):
    """Main social feed - Keep your existing structure"""
    form = PostForm()
    
    # Get posts from followed users + current user
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
    
    # Add like status to each post
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
        post.add_view(request.user)
    
    # Trending users
    trending_users = CustomUser.objects.annotate(
        follower_count=Count('followers_set')
    ).exclude(id=request.user.id).order_by('-follower_count')[:5]
    
    following_ids = list(following)
    
    # Unread notifications count
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


# social/views.py - REPLACE the entire create_post function with this

# social/views.py - Complete working create_post with all features

import base64
import time
import json
from datetime import datetime
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
import cloudinary.uploader
import cloudinary.utils
import logging

from .models import Post, PostMedia, Like, Follow, Notification, FeedCache, BackgroundTemplate
from .forms import PostForm
from users.models import CustomUser

logger = logging.getLogger(__name__)


@login_required
def create_post(request):
    """Create post with video trim, custom audio support - Chrome compatible"""
    
    if request.method == 'POST':
        try:
            # Get form data
            content = request.POST.get('content', '')
            post_type = request.POST.get('post_type', 'mixed')
            background_template_id = request.POST.get('background_template')
            text_alignment = request.POST.get('text_alignment', 'center')
            text_color = request.POST.get('text_color', '#ffffff')
            text_font = request.POST.get('text_font', 'default')
            song_name = request.POST.get('song_name', 'Original Audio')
            audio_public_id = request.POST.get('audio_public_id', '')
            trim_start = float(request.POST.get('trim_start', 0))
            trim_end = request.POST.get('trim_end')
            
            if trim_end:
                trim_end = float(trim_end)
            
            # Handle file upload
            media_files = request.FILES.getlist('media_files')
            
            # Also check for single file upload
            if not media_files and request.FILES.get('file_data'):
                media_files = [request.FILES['file_data']]
            
            # Check if we have media
            has_media = len(media_files) > 0
            
            # Validate based on post type
            if post_type == 'text' and not content:
                return JsonResponse({'error': 'Text content is required for text posts'}, status=400)
            
            if post_type == 'media' and not has_media:
                return JsonResponse({'error': 'At least one media file is required'}, status=400)
            
            # Create the post
            post = Post.objects.create(
                user=request.user,
                content=content,
                post_type='media' if has_media else post_type,
                background_template_id=background_template_id if background_template_id else None,
                text_alignment=text_alignment,
                text_color=text_color,
                text_font=text_font,
                song_name=song_name if not audio_public_id else 'Custom Audio',
                trim_start=trim_start,
                trim_end=trim_end,
            )
            
            # Handle media files
            video_url = None
            thumbnail_url = None
            
            if has_media:
                for index, media_file in enumerate(media_files[:4]):
                    try:
                        is_video = media_file.content_type.startswith('video/')
                        file_size_mb = media_file.size / (1024 * 1024)
                        
                        if file_size_mb > 90:
                            post.delete()
                            return JsonResponse({'error': f'File too large: {file_size_mb:.1f}MB'}, status=400)
                        
                        # Generate unique public ID
                        timestamp = int(time.time())
                        public_id = f"post_{post.id}_{index}_{timestamp}"
                        
                        # Prepare upload options - NO eager transformations for faster upload
                        upload_options = {
                            'folder': "nusu/social/posts",
                            'public_id': public_id,
                            'timeout': 180,
                            'overwrite': True,
                        }
                        
                        if is_video:
                            upload_options['resource_type'] = 'video'
                        else:
                            upload_options['resource_type'] = 'image'
                        
                        # Upload to Cloudinary
                        upload_result = cloudinary.uploader.upload(media_file, **upload_options)
                        
                        # Create PostMedia
                        post_media = PostMedia.objects.create(
                            post=post,
                            media_type='video' if is_video else 'image',
                            order=index,
                            file_size=media_file.size,
                            duration=upload_result.get('duration') if is_video else None,
                            format=upload_result.get('format'),
                            width=upload_result.get('width'),
                            height=upload_result.get('height'),
                        )
                        
                        if is_video:
                            post_media.video = upload_result['public_id']
                            if upload_result.get('duration'):
                                post.video_duration = upload_result.get('duration')
                                post.save(update_fields=['video_duration'])
                            
                            # Generate URLs for response
                            video_url = post.get_trimmed_video_url() or post.get_original_video_url()
                            thumbnail_url = post.get_video_thumbnail()
                        else:
                            post_media.image = upload_result['public_id']
                            video_url = post_media.url
                        
                        post_media.save()
                        
                        logger.info(f"Uploaded {media_file.name} to Cloudinary: {upload_result['public_id']}")
                        
                    except Exception as e:
                        logger.error(f"Media upload error: {e}")
                        post.delete()
                        return JsonResponse({'error': str(e)}, status=500)
            
            # Handle custom audio upload (if provided separately)
            if request.FILES.get('audio_file'):
                try:
                    audio_file = request.FILES['audio_file']
                    audio_result = cloudinary.uploader.upload(
                        audio_file,
                        resource_type='video',
                        folder='nusu/social/audio',
                        public_id=f"audio_{post.id}_{int(time.time())}",
                    )
                    post.song_name = audio_file.name.replace('.mp3', '').replace('.wav', '')[:50]
                    post.save(update_fields=['song_name'])
                except Exception as e:
                    logger.error(f"Audio upload error: {e}")
            
            # Return success response
            return JsonResponse({
                'success': True,
                'status': 'success',
                'post_id': post.id,
                'redirect_url': reverse('social:feed'),
                'post': {
                    'id': post.id,
                    'type': 'video' if post.has_video else post.post_type,
                    'url': video_url,
                    'thumbnail': thumbnail_url,
                    'duration': post.video_duration,
                    'content': content,
                    'song_name': post.song_name,
                }
            })
                
        except Exception as e:
            logger.error(f"Create post error: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    # GET request - show form
    templates = BackgroundTemplate.objects.filter(is_active=True)
    return render(request, 'social/create_post.html', {'templates': templates})


@login_required
def upload_audio(request):
    """Upload custom audio for videos"""
    if request.method == 'POST' and request.FILES.get('audio'):
        audio_file = request.FILES['audio']
        
        try:
            upload_result = cloudinary.uploader.upload(
                audio_file,
                resource_type='video',
                folder='nusu/social/audio',
                public_id=f"audio_{request.user.id}_{int(time.time())}",
                timeout=60
            )
            
            return JsonResponse({
                'success': True,
                'public_id': upload_result['public_id'],
                'url': upload_result['secure_url'],
                'name': audio_file.name
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'No audio file'}, status=400)


def get_csrf_token(request):
    """Return CSRF token for AJAX requests"""
    return JsonResponse({'csrfToken': request.META.get('CSRF_COOKIE', '')})


@login_required
def following_feed(request):
    """Feed showing only posts from followed users"""
    following = Follow.objects.filter(follower=request.user).values_list('following', flat=True)
    
    posts = Post.objects.filter(
        user__in=following,
        is_reply=False
    ).select_related(
        'user', 'user__userprofile', 'background_template'
    ).prefetch_related(
        'likes', 'media_items'
    ).order_by('-created_at')
    
    paginator = Paginator(posts, 20)
    page = request.GET.get('page')
    posts = paginator.get_page(page)
    
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
    
    trending_users = CustomUser.objects.annotate(
        follower_count=Count('followers_set')
    ).exclude(id=request.user.id).order_by('-follower_count')[:5]
    
    following_ids = list(following)
    unread_notifications = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context = {
        'posts': posts,
        'trending_users': trending_users,
        'following_ids': following_ids,
        'feed_title': 'Following',
        'unread_notifications': unread_notifications,
    }
    
    return render(request, 'social/feed.html', context)


@login_required
@require_POST
def delete_post(request, post_id):
    """Delete a post and its media from Cloudinary"""
    post = get_object_or_404(Post, id=post_id, user=request.user)
    
    # Delete media from Cloudinary
    for media in post.media_items.all():
        media.delete_from_cloudinary()
    
    # Delete the post
    post.delete()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def like_post(request, post_id):
    """Like/unlike a post"""
    post = get_object_or_404(Post, id=post_id)
    like, created = Like.objects.get_or_create(
        user=request.user,
        post=post
    )
    
    if not created:
        like.delete()
        liked = False
    else:
        liked = True
        # Create notification if not self-like
        if post.user != request.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='like',
                post=post
            )
    
    return JsonResponse({
        'liked': liked,
        'likes_count': post.likes.count()
    })


@login_required
@require_POST
def repost(request, post_id):
    """Repost a post - copy original content properly"""
    original_post = get_object_or_404(Post, id=post_id)
    
    # Check if already reposted
    existing_repost = Post.objects.filter(
        user=request.user,
        original_post=original_post,
        is_repost=True
    ).first()
    
    if existing_repost:
        existing_repost.delete()
        reposted = False
        # Delete notification
        Notification.objects.filter(
            sender=request.user,
            recipient=original_post.user,
            notification_type='repost',
            post=original_post
        ).delete()
    else:
        # Create repost - copy the original post's content type
        repost = Post.objects.create(
            user=request.user,
            content=original_post.content,  # Copy the original text
            is_repost=True,
            original_post=original_post,
            post_type=original_post.post_type,  # Copy the post type (text/media/mixed)
            song_name=original_post.song_name if original_post.song_name else '',  # Copy song name
            background_template=original_post.background_template,  # Copy background template if text post
            text_alignment=original_post.text_alignment,
            text_color=original_post.text_color,
            text_font=original_post.text_font,
            trim_start=original_post.trim_start,
            trim_end=original_post.trim_end,
            video_duration=original_post.video_duration,
        )
        
        # Copy media items if the original has media
        for media in original_post.media_items.all():
            PostMedia.objects.create(
                post=repost,
                media_type=media.media_type,
                image=media.image,  # Copy the Cloudinary reference
                video=media.video,  # Copy the Cloudinary reference
                external_url=media.external_url,
                width=media.width,
                height=media.height,
                duration=media.duration,
                file_size=media.file_size,
                format=media.format,
                order=media.order,
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
        'reposts_count': original_post.reposts.count()
    })


@login_required
def toggle_follow(request, username):
    """Follow/unfollow a user"""
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
        # Delete notification
        Notification.objects.filter(
            sender=request.user,
            recipient=user_to_follow,
            notification_type='follow'
        ).delete()
    else:
        status = 'followed'
        Notification.objects.create(
            recipient=user_to_follow,
            sender=request.user,
            notification_type='follow'
        )
    
    follower_count = user_to_follow.followers_set.count()
    
    return JsonResponse({
        'status': status,
        'follower_count': follower_count,
    })


@login_required
def notifications(request):
    """View notifications"""
    notifications_list = Notification.objects.filter(
        recipient=request.user
    ).select_related('sender', 'post').order_by('-created_at')
    
    paginator = Paginator(notifications_list, 30)
    page = request.GET.get('page')
    notifications = paginator.get_page(page)
    
    return render(request, 'social/notifications.html', {'notifications': notifications})


@login_required
@require_POST
def mark_notification_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, recipient=request.user)
    notification.is_read = True
    notification.save()
    return JsonResponse({'status': 'success'})


@login_required
def user_posts(request, username):
    """View posts by a specific user"""
    user_profile = get_object_or_404(CustomUser, username=username)
    posts = Post.objects.filter(user=user_profile, is_reply=False).order_by('-created_at')
    
    paginator = Paginator(posts, 20)
    page = request.GET.get('page')
    posts = paginator.get_page(page)
    
    for post in posts:
        post.is_liked = post.likes.filter(user=request.user).exists()
    
    context = {
        'profile_user': user_profile,
        'posts': posts,
        'is_following': Follow.objects.filter(
            follower=request.user, following=user_profile
        ).exists() if request.user.is_authenticated else False,
    }
    
    return render(request, 'users/user_posts.html', context)


@login_required
def search_users(request):
    """Search for users"""
    query = request.GET.get('q', '')
    users = []
    
    if query:
        users = CustomUser.objects.filter(
            Q(username__icontains=query) |
            Q(userprofile__display_name__icontains=query)
        ).select_related('userprofile')[:20]
        
        # Add following status
        following_ids = set(
            Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
        )
        for user in users:
            user.is_following = user.id in following_ids
    
    context = {
        'query': query,
        'users': users,
    }
    
    return render(request, 'social/search_users.html', context)


@login_required
def get_templates(request):
    """API endpoint to get background templates"""
    templates = BackgroundTemplate.objects.filter(is_active=True).order_by('order')
    
    templates_data = []
    for template in templates:
        templates_data.append({
            'id': template.id,
            'name': template.name,
            'template_type': template.template_type,
            'gradient_css': template.gradient_css,
            'css_class': template.css_class,
            'is_animated': template.is_animated,
            'animation_duration': template.animation_duration,
            'preview_url': template.preview_url,
            'is_premium': template.is_premium,
        })
    
    return JsonResponse({'templates': templates_data})


@login_required
@require_GET
def get_new_posts_count(request):
    """Get count of new posts since last view"""
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
@require_GET
def get_unread_notifications_count(request):
    """Get count of unread notifications"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    return JsonResponse({'unread_count': count})


@login_required
def get_user_stats(request, username):
    """Get user statistics for profile"""
    user_profile = get_object_or_404(CustomUser, username=username)
    
    followers_count = Follow.objects.filter(following=user_profile).count()
    following_count = Follow.objects.filter(follower=user_profile).count()
    posts_count = Post.objects.filter(user=user_profile, is_reply=False).count()
    
    return JsonResponse({
        'followers': followers_count,
        'following': following_count,
        'posts': posts_count,
    })


@login_required
def search_users_api(request):
    """API endpoint for user search (autocomplete)"""
    query = request.GET.get('q', '')
    
    if len(query) < 2:
        return JsonResponse({'users': []})
    
    users = CustomUser.objects.filter(
        Q(username__icontains=query) |
        Q(userprofile__display_name__icontains=query)
    ).select_related('userprofile')[:10]
    
    following_ids = set(
        Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    )
    
    users_data = []
    for user in users:
        users_data.append({
            'id': user.id,
            'username': user.username,
            'display_name': user.userprofile.display_name if hasattr(user, 'userprofile') else user.username,
            'avatar': user.userprofile.profile_picture.url if user.userprofile.profile_picture else None,
            'is_following': user.id in following_ids,
        })
    
    return JsonResponse({'users': users_data})
    
    
@login_required
def post_detail(request, post_id):
    """View single post with replies"""
    post = get_object_or_404(
        Post.objects.select_related('user', 'user__userprofile', 'background_template')
        .prefetch_related('media_items', 'likes', 'views'),
        id=post_id
    )
    
    # Get replies
    replies = post.replies.all().select_related(
        'user', 'user__userprofile', 'background_template'
    ).prefetch_related('media_items', 'likes', 'views')
    
    # Add view
    post.add_view(request.user)
    post.is_liked = post.likes.filter(user=request.user).exists()
    
    # Mark as liked for replies
    for reply in replies:
        reply.is_liked = reply.likes.filter(user=request.user).exists()
        reply.add_view(request.user)
    
    # Handle comment submission
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
            
            # Handle media in reply
            media_files = request.FILES.getlist('media_files')
            for index, media_file in enumerate(media_files[:4]):
                try:
                    is_video = media_file.content_type.startswith('video/')
                    upload_options = {
                        'folder': f'nusu/users/{request.user.id}/replies',
                        'public_id': f"reply_{reply.id}_{index}_{int(time.time())}",
                        'resource_type': 'video' if is_video else 'image',
                        'eager': [{'quality': 'auto', 'fetch_format': 'auto', 'crop': 'limit', 'width': 1080, 'height': 1920}]
                    }
                    
                    upload_result = cloudinary.uploader.upload(media_file, **upload_options)
                    
                    post_media = PostMedia.objects.create(
                        post=reply,
                        media_type='video' if is_video else 'image',
                        order=index,
                        file_size=media_file.size,
                        duration=upload_result.get('duration') if is_video else None,
                    )
                    
                    if is_video:
                        post_media.video = upload_result['public_id']
                    else:
                        post_media.image = upload_result['public_id']
                    post_media.save()
                    
                except Exception as e:
                    logger.error(f"Reply upload error: {e}")
            
            # Create notification
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
def get_comments(request, post_id):
    """API endpoint to get comments for a post"""
    post = get_object_or_404(Post, id=post_id)
    replies = post.replies.filter(is_reply=True).select_related('user', 'user__userprofile').order_by('-created_at')
    
    comments_data = []
    for reply in replies:
        comments_data.append({
            'id': reply.id,
            'user': reply.user.username,
            'display_name': reply.user.userprofile.display_name or reply.user.username,
            'avatar': reply.user.userprofile.profile_picture.url if reply.user.userprofile.profile_picture else None,
            'content': reply.content,
            'created_at': reply.created_at.isoformat(),
            'likes_count': reply.likes_count,
            'is_liked': reply.likes.filter(user=request.user).exists(),
        })
    
    return JsonResponse({'comments': comments_data})


@login_required
@require_POST
def add_comment(request, post_id):
    """API endpoint to add a comment"""
    try:
        post = get_object_or_404(Post, id=post_id)
        
        # Try to get JSON data first, then fallback to POST data
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            content = data.get('content', '').strip()
        else:
            content = request.POST.get('content', '').strip()
        
        if not content:
            return JsonResponse({'error': 'Comment cannot be empty', 'status': 'error'}, status=400)
        
        # Create the reply post
        reply = Post.objects.create(
            user=request.user,
            content=content,
            is_reply=True,
            parent_post=post,
            post_type='text'
        )
        
        # Create notification for post owner
        if post.user != request.user:
            Notification.objects.create(
                recipient=post.user,
                sender=request.user,
                notification_type='reply',
                post=reply
            )
        
        return JsonResponse({
            'status': 'success',
            'comment': {
                'id': reply.id,
                'user': reply.user.username,
                'content': reply.content,
                'created_at': reply.created_at.isoformat(),
            }
        })
    except Exception as e:
        return JsonResponse({'error': str(e), 'status': 'error'}, status=500)


@login_required
def video_fallback_url(request, post_id):
    """API endpoint to get fallback video URL if trimmed version fails (Chrome compatibility)"""
    post = get_object_or_404(Post, id=post_id)
    
    if post.has_video:
        original_url = post.get_original_video_url()
        return JsonResponse({'url': original_url, 'success': True})
    
    return JsonResponse({'error': 'No video found'}, status=404)