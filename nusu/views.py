# nusu/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count
from users.models import CustomUser, UserProfile
from social.models import Notification, Follow, FeedCache, Post
from transactions.models import Transaction
from tokens.models import TokenRate
from airdrop.models import UserMiningState

def home(request):
    """Home page view with live data"""
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
def global_stats_api(request):
    """API endpoint for global stats (for AJAX updates)"""
    return JsonResponse(get_global_stats())

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
    token_balance = float(user.userprofile.token_balance)
    try:
        current_rate = TokenRate.objects.latest('effective_date')
        ugx_value = token_balance * float(current_rate.rate)
    except TokenRate.DoesNotExist:
        ugx_value = token_balance * 3800
    
    return JsonResponse({
        'followers': followers_count,
        'following': following_count,
        'referrals': user.referrals.count(),
        'token_balance': token_balance,
        'ugx_balance': round(ugx_value, 2),
        'mining': mining_data,
    })

def health_check(request):
    """Health check endpoint for monitoring"""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': timezone.now().isoformat()
    })