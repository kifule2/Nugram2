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
from .video_utils import VideoOptimizer
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


@login_required
@csrf_exempt
def create_post(request):
    """Create a new post - handles both text posts with templates and video/image posts"""
    
    # GET request - show create post page with templates
    if request.method == 'GET':
        templates = BackgroundTemplate.objects.filter(is_active=True)
        return render(request, 'social/create_post.html', {'templates': templates})
    
    # POST request - handle post creation
    if request.method == 'POST':
        # Check if it's a JSON request (text post with template)
        if request.content_type == 'application/json':
            try:
                data = json.loads(request.body)
                content = data.get('content', '').strip()
                template_id = data.get('template_id')
                text_alignment = data.get('alignment', 'center')
                text_size = float(data.get('fontSize', 1.8))
                text_color = data.get('textColor', '#ffffff')
                text_font = data.get('font', 'default')
                
                if not content:
                    return JsonResponse({'status': 'error', 'message': 'Content is required'}, status=400)
                
                # Create text post with background template
                post = Post.objects.create(
                    user=request.user,
                    content=content,
                    post_type='text',
                    background_template_id=template_id if template_id else None,
                    text_alignment=text_alignment,
                    text_size=text_size,
                    text_color=text_color,
                    text_font=text_font,
                    song_name='Original Audio'
                )
                
                # Notify followers
                for follow in Follow.objects.filter(following=request.user):
                    Notification.objects.create(
                        recipient=follow.follower,
                        sender=request.user,
                        notification_type='post',
                        post=post
                    )
                
                return JsonResponse({
                    'status': 'success', 
                    'post_id': post.id,
                    'message': 'Text post created successfully',
                    'redirect_url': reverse('social:feed')
                })
                
            except json.JSONDecodeError:
                return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)
            except Exception as e:
                logger.error(f"Text post creation failed: {e}")
                return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
        
        # Handle multipart form data (media posts with files)
        else:
            content = request.POST.get('content', '').strip()
            song_name = request.POST.get('song_name', 'Original Audio')
            
            # Handle media files directly
            media_files = request.FILES.getlist('media_files')
            
            logger.info(f"Received {len(media_files)} files from user {request.user.id}")
            for f in media_files:
                logger.info(f"File: {f.name}, Size: {f.size}, Type: {f.content_type}")
            
            # Validate files
            if len(media_files) > 4:
                return JsonResponse({'status': 'error', 'message': 'Maximum 4 files allowed'}, status=400)
            
            # Determine post type
            post_type = 'text'
            if media_files:
                post_type = 'media' if not content else 'mixed'
            
            # Create post first
            post = Post.objects.create(
                user=request.user,
                content=content,
                post_type=post_type,
                song_name=song_name
            )
            
            logger.info(f"Created post {post.id} for user {request.user.id}")
            
            # Process each media file
            upload_results = []
            
            for index, media_file in enumerate(media_files):
                try:
                    is_video = media_file.content_type.startswith('video/')
                    
                    # Generate timestamp for unique filename
                    timestamp = int(time.time())
                    
                    # Read the file content
                    file_content = media_file.read()
                    file_size = len(file_content)
                    logger.info(f"Processing file {index}: {media_file.name}, size: {file_size} bytes")
                    
                    # Create a BytesIO object from the content
                    file_data = BytesIO(file_content)
                    
                    # Get Cloudinary settings
                    cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
                    api_key = settings.CLOUDINARY_STORAGE['API_KEY']
                    api_secret = settings.CLOUDINARY_STORAGE['API_SECRET']
                    
                    # Configure Cloudinary
                    cloudinary.config(
                        cloud_name=cloud_name,
                        api_key=api_key,
                        api_secret=api_secret,
                        secure=True
                    )
                    
                    # Determine folder and public_id based on media type
                    if is_video:
                        folder_path = f"nusu/users/{request.user.id}/videos"
                        public_id = f"video_{timestamp}_{index}"
                        resource_type = 'video'
                        logger.info(f"Uploading video to folder: {folder_path}")
                    else:
                        folder_path = f"nusu/users/{request.user.id}/images"
                        public_id = f"image_{timestamp}_{index}"
                        resource_type = 'image'
                        logger.info(f"Uploading image to folder: {folder_path}")
                    
                    # Upload to Cloudinary
                    upload_result = cloudinary.uploader.upload(
                        file_data,
                        folder=folder_path,
                        public_id=public_id,
                        resource_type=resource_type,
                        overwrite=True,
                        invalidate=True,
                        quality='auto',
                        fetch_format='auto'
                    )
                    
                    logger.info(f"✅ Upload successful! Public ID: {upload_result['public_id']}")
                    logger.info(f"   URL: {upload_result['secure_url']}")
                    
                    # Create PostMedia entry with correct media_type
                    if is_video:
                        post_media = PostMedia.objects.create(
                            post=post,
                            media_type='video',  # IMPORTANT: Must be 'video'
                            order=index,
                            video=upload_result['public_id'],
                            duration=upload_result.get('duration'),
                            width=upload_result.get('width'),
                            height=upload_result.get('height'),
                            file_size=upload_result.get('bytes'),
                            format=upload_result.get('format')
                        )
                        if upload_result.get('duration'):
                            post.video_duration = upload_result['duration']
                            post.save(update_fields=['video_duration'])
                    else:
                        post_media = PostMedia.objects.create(
                            post=post,
                            media_type='image',  # IMPORTANT: Must be 'image'
                            order=index,
                            image=upload_result['public_id'],
                            width=upload_result.get('width'),
                            height=upload_result.get('height'),
                            file_size=upload_result.get('bytes'),
                            format=upload_result.get('format')
                        )
                    
                    logger.info(f"✅ PostMedia {post_media.id} saved for post {post.id}")
                    
                    upload_results.append({
                        'success': True,
                        'type': 'video' if is_video else 'image',
                        'url': upload_result['secure_url'],
                        'public_id': upload_result['public_id'],
                        'folder': folder_path,
                        'size': file_size
                    })
                    
                except Exception as e:
                    logger.error(f"❌ Media upload error for file {index}: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    upload_results.append({
                        'success': False,
                        'error': str(e),
                        'file': media_file.name if media_file else 'Unknown'
                    })
            
            # Notify followers about the post
            successful_uploads = [r for r in upload_results if r.get('success')]
            if successful_uploads:
                for follow in Follow.objects.filter(following=request.user):
                    Notification.objects.create(
                        recipient=follow.follower,
                        sender=request.user,
                        notification_type='post',
                        post=post
                    )
                logger.info(f"Notified followers about new post")
            
            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                response_data = {
                    'status': 'success' if successful_uploads else 'error',
                    'post_id': post.id,
                    'message': f'Posted {len(successful_uploads)} of {len(media_files)} files' if successful_uploads else 'Failed to upload any files',
                    'uploads': upload_results,
                    'redirect_url': reverse('social:feed')
                }
                return JsonResponse(response_data)
            else:
                if successful_uploads:
                    messages.success(request, f'Posted {len(successful_uploads)} files successfully!')
                else:
                    messages.error(request, 'Failed to upload files')
                return redirect('social:feed')

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