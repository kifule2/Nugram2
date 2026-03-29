# nusu/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta
from users.models import CustomUser, UserProfile
from social.models import Notification, Follow, FeedCache, Post
from transactions.models import Transaction
from tokens.models import TokenRate
from airdrop.models import UserMiningState
from tasks.models import Task, TaskCompletion


def home(request):
    """Home page view with live data and modern feed"""
    context = {}
    
    # Global stats for all users
    context['global_stats'] = get_global_stats()
    
    if request.user.is_authenticated:
        # Get user profile and related data
        user = request.user
        
        # Get follower counts
        context['followers_count'] = Follow.objects.filter(following=user).count()
        context['following_count'] = Follow.objects.filter(follower=user).count()
        
        # Get mining state
        try:
            context['mining_state'] = UserMiningState.objects.get(user=user)
        except UserMiningState.DoesNotExist:
            context['mining_state'] = None
        
        # Get recent transactions
        context['recent_transactions'] = Transaction.objects.filter(
            user=user
        ).select_related(
            'user', 'user__userprofile', 'agent'
        ).order_by('-timestamp')[:10]
        
        # Get unread notifications count
        context['unread_notifications_count'] = Notification.objects.filter(
            recipient=user,
            is_read=False
        ).count()
        
        # Get new posts count for social tab
        try:
            feed_cache = FeedCache.objects.get(user=user)
            if feed_cache.last_seen_post:
                context['new_posts_count'] = Post.objects.filter(
                    is_reply=False,
                    created_at__gt=feed_cache.last_seen_post.created_at
                ).count()
            else:
                context['new_posts_count'] = Post.objects.filter(is_reply=False).count()
        except FeedCache.DoesNotExist:
            context['new_posts_count'] = Post.objects.filter(is_reply=False).count()
        
        # ========== NEW DATA FOR MODERN HOME PAGE ==========
        
        # Get trending posts (most engagement in last 7 days)
        last_week = timezone.now() - timedelta(days=7)
        trending_posts = Post.objects.filter(
            is_reply=False,
            created_at__gte=last_week
        ).select_related(
            'user', 'user__userprofile'
        ).prefetch_related(
            'media_items', 'likes'
        ).annotate(
            engagement=Count('likes') + Count('replies')
        ).order_by('-engagement', '-created_at')[:10]
        context['trending_posts'] = trending_posts
        
        # Get system updates from admin posts (last 30 days)
        admin_updates = Post.objects.filter(
            user__is_superuser=True,
            is_reply=False,
            created_at__gte=timezone.now() - timedelta(days=30)
        ).select_related('user').order_by('-created_at')[:5]
        
        system_updates = []
        for update in admin_updates:
            system_updates.append({
                'type': 'announcement',
                'title': f'Announcement from @{update.user.username}',
                'message': update.content[:150],
                'created_at': update.created_at,
                'link': f'/social/post/{update.id}/'
            })
        context['system_updates'] = system_updates
        
        # Get featured task (most popular active task user hasn't completed)
        featured_task = Task.objects.filter(
            is_active=True,
            expiry_date__gt=timezone.now()
        ).exclude(
            completions__user=user
        ).annotate(
            participant_count=Count('completions')
        ).order_by('-participant_count').first()
        
        # If no featured task, get any active task user hasn't completed
        if not featured_task:
            featured_task = Task.objects.filter(
                is_active=True,
                expiry_date__gt=timezone.now()
            ).exclude(
                completions__user=user
            ).first()
        context['featured_task'] = featured_task
        
        # Get user's completed tasks count
        context['completed_tasks_count'] = TaskCompletion.objects.filter(
            user=user,
            status='verified'
        ).count()
        
        # Get user's total points earned from tasks
        total_points_from_tasks = TaskCompletion.objects.filter(
            user=user,
            status='verified'
        ).aggregate(
            total=Sum('task__points_reward')
        )['total'] or 0
        context['total_points_from_tasks'] = total_points_from_tasks
        
        # Get referral stats
        context['referrals_count'] = user.referrals.count()
        context['referral_points'] = context['referrals_count'] * 200
        
        # Get user's posts count
        context['user_posts_count'] = Post.objects.filter(user=user, is_reply=False).count()
        
        # Get user's token balance with UGX conversion
        context['token_balance'] = float(user.userprofile.token_balance) if hasattr(user, 'userprofile') else 0
        context['ugx_balance'] = context['token_balance'] * context['global_stats']['ugx_rate']
        
        # Get recent followers (for activity feed)
        recent_followers = Follow.objects.filter(
            following=user
        ).select_related('follower', 'follower__userprofile').order_by('-created_at')[:5]
        context['recent_followers'] = recent_followers
        
        # Get user profile object
        context['user_profile'] = user.userprofile if hasattr(user, 'userprofile') else None
    
    else:
        # For non-authenticated users - get sample posts for sneak peek
        sample_posts = Post.objects.filter(
            is_reply=False
        ).select_related('user', 'user__userprofile').prefetch_related('media_items')[:6]
        context['sample_posts'] = sample_posts
        
        # Get featured task for non-authenticated users
        featured_task = Task.objects.filter(
            is_active=True,
            expiry_date__gt=timezone.now()
        ).annotate(
            participant_count=Count('completions')
        ).order_by('-participant_count').first()
        context['featured_task'] = featured_task
        
        # Sample stats for sneak peek
        context['total_users_sample'] = context['global_stats']['total_users']
        context['total_tokens_sample'] = round(context['global_stats']['total_tokens'])
    
    return render(request, 'home.html', context)


def get_global_stats():
    """Get global statistics for the platform"""
    stats = {}
    
    # Get total users
    stats['total_users'] = CustomUser.objects.count()
    
    # Get total tokens in circulation
    total_tokens = UserProfile.objects.aggregate(
        total=Sum('token_balance')
    )['total'] or 0
    stats['total_tokens'] = round(total_tokens, 2)
    
    # Get current token rate
    try:
        current_rate = TokenRate.objects.latest('effective_date')
        stats['ugx_rate'] = float(current_rate.rate)
    except TokenRate.DoesNotExist:
        stats['ugx_rate'] = 3800  # Default rate
    
    # Get current mining multiplier (average)
    mining_states = UserMiningState.objects.filter(is_mining=True)
    if mining_states.exists():
        avg_rate = mining_states.aggregate(
            avg=Sum('current_rate')
        )['avg'] / mining_states.count()
        stats['current_multiplier'] = round(avg_rate, 2)
    else:
        stats['current_multiplier'] = 1.0
    
    # Get total transactions count
    stats['total_transactions'] = Transaction.objects.count()
    
    # Get active users (users active in last 24 hours)
    from django.utils import timezone
    from datetime import timedelta
    last_24h = timezone.now() - timedelta(hours=24)
    stats['active_users'] = CustomUser.objects.filter(
        last_login__gte=last_24h
    ).count()
    
    return stats


@login_required
def user_stats_api(request):
    """API endpoint for user-specific stats (for AJAX updates)"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    user = request.user
    
    # Get follower counts
    followers_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    
    # Get mining state
    try:
        mining_state = UserMiningState.objects.get(user=user)
        mining_data = {
            'is_mining': mining_state.is_mining,
            'elapsed_hours': mining_state.elapsed_hours,
            'progress_percentage': mining_state.progress_percentage,
            'points_earned_today': mining_state.points_earned_today,
            'current_rate': mining_state.current_rate,
            'remaining_time': f"{mining_state.remaining_time[0]:02d}:{mining_state.remaining_time[1]:02d}:{mining_state.remaining_time[2]:02d}"
        }
    except UserMiningState.DoesNotExist:
        mining_data = {
            'is_mining': False,
            'elapsed_hours': 0,
            'progress_percentage': 0,
            'points_earned_today': 0,
            'current_rate': 1.0,
            'remaining_time': '24:00:00'
        }
    
    # Get token balance and UGX value
    token_balance = float(user.userprofile.token_balance) if hasattr(user, 'userprofile') else 0
    try:
        current_rate = TokenRate.objects.latest('effective_date')
        ugx_value = token_balance * float(current_rate.rate)
    except TokenRate.DoesNotExist:
        ugx_value = token_balance * 3800
    
    # Get completed tasks count
    completed_tasks = 0
    if hasattr(user, 'task_completions'):
        completed_tasks = user.task_completions.filter(status='verified').count()
    
    # Get referral points
    referrals_count = user.referrals.count()
    referral_points = referrals_count * 200
    
    # Get unread notifications
    unread_notifications = Notification.objects.filter(recipient=user, is_read=False).count()
    
    return JsonResponse({
        'followers': followers_count,
        'following': following_count,
        'referrals': referrals_count,
        'referral_points': referral_points,
        'token_balance': token_balance,
        'ugx_balance': round(ugx_value, 2),
        'mining': mining_data,
        'completed_tasks': completed_tasks,
        'unread_notifications': unread_notifications,
    })


@login_required
def global_stats_api(request):
    """API endpoint for global stats"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Not authenticated'}, status=401)
    
    user = request.user
    
    # Get followers/following counts
    followers_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    
    # Get mining state
    try:
        mining_state = UserMiningState.objects.get(user=user)
        mining_data = {
            'is_mining': mining_state.is_mining,
            'elapsed_hours': mining_state.elapsed_hours,
            'progress_percentage': mining_state.progress_percentage,
            'points_earned_today': mining_state.points_earned_today,
            'current_rate': mining_state.current_rate,
            'remaining_time': f"{mining_state.remaining_time[0]:02d}:{mining_state.remaining_time[1]:02d}:{mining_state.remaining_time[2]:02d}"
        }
    except UserMiningState.DoesNotExist:
        mining_data = {
            'is_mining': False,
            'elapsed_hours': 0,
            'progress_percentage': 0,
            'points_earned_today': 0,
            'current_rate': 1.0,
            'remaining_time': '24:00:00'
        }
    
    # Get token balance and UGX value
    token_balance = float(user.userprofile.token_balance) if hasattr(user, 'userprofile') else 0
    
    try:
        current_rate = TokenRate.objects.latest('effective_date')
        ugx_value = token_balance * float(current_rate.rate)
    except TokenRate.DoesNotExist:
        ugx_value = token_balance * 3800
    
    # Get global stats
    global_stats = get_global_stats()
    
    return JsonResponse({
        'followers': followers_count,
        'following': following_count,
        'referrals': user.referrals.count(),
        'token_balance': token_balance,
        'ugx_balance': round(ugx_value, 2),
        'mining': mining_data,
        'global': global_stats,
    })


def health_check(request):
    """Health check endpoint for monitoring"""
    from django.utils import timezone
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'database': 'connected',
        'users': CustomUser.objects.count(),
    })