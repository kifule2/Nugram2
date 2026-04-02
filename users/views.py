# users/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.db.models import Q, Count
from django.core.paginator import Paginator
from django.utils import timezone
from .models import CustomUser, UserProfile, Notification
from .forms import CustomUserCreationForm, ProfileUpdateForm
from social.models import Follow, Notification as SocialNotification, Post
from airdrop.models import UserMiningState
from tokens.models import TokenRate
from transactions.models import Transaction
import cloudinary.uploader


@login_required
def user_profile(request, username):
    """View user profile with all content"""
    profile_user = get_object_or_404(CustomUser, username=username)
    is_owner = (request.user == profile_user)
    
    followers_count = Follow.objects.filter(following=profile_user).count()
    following_count = Follow.objects.filter(follower=profile_user).count()
    
    is_following = False
    if request.user.is_authenticated and not is_owner:
        is_following = Follow.objects.filter(
            follower=request.user,
            following=profile_user
        ).exists()
    
    # Get all posts by user
    all_posts = Post.objects.filter(
        user=profile_user,
        is_reply=False
    ).select_related(
        'user', 'user__userprofile', 'background_template'
    ).prefetch_related(
        'likes', 'replies', 'views', 'media_items'
    ).order_by('-created_at')
    
    # Separate posts by type for tabs
    media_posts = all_posts.filter(
        post_type__in=['media', 'mixed']
    ).order_by('-created_at')[:30]
    
    text_posts = all_posts.filter(
        post_type='text'
    ).order_by('-created_at')[:20]
    
    # Get completed tasks for tasks tab
    completed_tasks = []
    if hasattr(profile_user, 'task_completions'):
        completed_tasks = profile_user.task_completions.filter(
            status='verified'
        ).select_related('task').order_by('-verified_at')[:20]
    
    mining_state = None
    if is_owner:
        mining_state, created = UserMiningState.objects.get_or_create(user=profile_user)
    else:
        try:
            mining_state = UserMiningState.objects.get(user=profile_user)
        except UserMiningState.DoesNotExist:
            pass
    
    transactions = Transaction.objects.filter(user=profile_user).order_by('-timestamp')[:5]
    
    # Get token balance and UGX value
    token_balance = profile_user.userprofile.token_balance if hasattr(profile_user, 'userprofile') else 0
    
    current_rate = None
    try:
        current_rate = TokenRate.objects.latest('effective_date')
        ugx_value = token_balance * float(current_rate.rate)
    except TokenRate.DoesNotExist:
        ugx_value = token_balance * 3800
    
    # Get referral count
    referrals_count = profile_user.referrals.count() if hasattr(profile_user, 'referrals') else 0
    
    # Pagination for all posts (for potential infinite scroll)
    paginator = Paginator(all_posts, 20)
    page = request.GET.get('page')
    posts_page = paginator.get_page(page)
    
    context = {
        # User info
        'profile_user': profile_user,
        'is_owner': is_owner,
        'is_following': is_following,
        
        # Stats
        'followers_count': followers_count,
        'following_count': following_count,
        'referrals_count': referrals_count,
        
        # Posts
        'posts': posts_page,
        'media_posts': media_posts,
        'text_posts': text_posts,
        'all_posts_count': all_posts.count(),
        
        # Tasks
        'completed_tasks': completed_tasks,
        
        # Mining & Tokens
        'mining_state': mining_state,
        'current_rate': current_rate,
        'token_balance': token_balance,
        'ugx_value': ugx_value,
        
        # Transactions
        'transactions': transactions,
        
        # Profile details
        'user_profile': profile_user.userprofile if hasattr(profile_user, 'userprofile') else None,
    }
    return render(request, 'users/profile.html', context)


@login_required
def edit_profile(request):
    """Edit user profile with Cloudinary upload"""
    if request.method == 'POST':
        form = ProfileUpdateForm(
            request.POST,
            request.FILES,
            instance=request.user.userprofile
        )
        
        if form.is_valid():
            profile = form.save(commit=False)
            
            if 'profile_picture' in request.FILES:
                try:
                    if profile.profile_picture and 'default' not in str(profile.profile_picture):
                        try:
                            cloudinary.uploader.destroy(profile.profile_picture.public_id)
                        except:
                            pass
                    
                    upload_result = cloudinary.uploader.upload(
                        request.FILES['profile_picture'],
                        folder='nusu/profiles',
                        transformation=[
                            {'width': 300, 'height': 300, 'crop': 'thumb', 'gravity': 'face'},
                            {'quality': 'auto'},
                            {'fetch_format': 'auto'}
                        ]
                    )
                    profile.profile_picture = upload_result['public_id']
                    messages.success(request, "Profile picture uploaded successfully!")
                except Exception as e:
                    messages.error(request, f"Profile picture upload failed: {str(e)}")
            
            if 'cover_photo' in request.FILES:
                try:
                    if profile.cover_photo and 'default' not in str(profile.cover_photo):
                        try:
                            cloudinary.uploader.destroy(profile.cover_photo.public_id)
                        except:
                            pass
                    
                    upload_result = cloudinary.uploader.upload(
                        request.FILES['cover_photo'],
                        folder='nusu/covers',
                        transformation=[
                            {'width': 1500, 'height': 500, 'crop': 'fill'},
                            {'quality': 'auto'},
                            {'fetch_format': 'auto'}
                        ]
                    )
                    profile.cover_photo = upload_result['public_id']
                    messages.success(request, "Cover photo uploaded successfully!")
                except Exception as e:
                    messages.error(request, f"Cover photo upload failed: {str(e)}")
            
            profile.save()
            messages.success(request, "Profile updated successfully!")
            return redirect('users:user_profile', username=request.user.username)
    else:
        form = ProfileUpdateForm(instance=request.user.userprofile)
    
    return render(request, 'users/edit_profile.html', {'form': form})


@login_required
def dashboard(request):
    """User dashboard with live stats"""
    user = request.user
    
    followers_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    
    recent_follows = Follow.objects.filter(
        following=user
    ).select_related('follower', 'follower__userprofile').order_by('-created_at')[:5]
    
    mining_state, created = UserMiningState.objects.get_or_create(user=user)
    recent_transactions = Transaction.objects.filter(user=user).order_by('-timestamp')[:5]
    current_rate = TokenRate.objects.last()
    
    # Get completed tasks count
    completed_tasks_count = 0
    if hasattr(user, 'task_completions'):
        completed_tasks_count = user.task_completions.filter(status='verified').count()
    
    context = {
        'user': user,
        'followers_count': followers_count,
        'following_count': following_count,
        'recent_followers': recent_follows,
        'mining_state': mining_state,
        'recent_transactions': recent_transactions,
        'current_rate': current_rate,
        'unread_notifications': SocialNotification.objects.filter(recipient=user, is_read=False).count(),
        'referrals_count': user.referrals.count(),
        'completed_tasks_count': completed_tasks_count,
        'token_balance': user.userprofile.token_balance if hasattr(user, 'userprofile') else 0,
    }
    return render(request, 'users/dashboard.html', context)


@login_required
def dashboard_stats(request):
    """API endpoint for dashboard live stats"""
    user = request.user
    
    followers_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    
    recent_follows = Follow.objects.filter(
        following=user
    ).select_related('follower', 'follower__userprofile').order_by('-created_at')[:3]
    
    recent_followers_data = []
    for follow in recent_follows:
        follower = follow.follower
        recent_followers_data.append({
            'username': follower.username,
            'display_name': follower.userprofile.display_name if hasattr(follower, 'userprofile') else follower.username,
            'avatar': follower.userprofile.profile_picture.url if follower.userprofile.profile_picture else f"https://ui-avatars.com/api/?name={follower.username[0]}&background=3b82f6&color=fff&size=40",
            'followed_at': follow.created_at.isoformat()
        })
    
    # Get mining stats
    mining_active = False
    mining_rate = 1.0
    try:
        mining_state = UserMiningState.objects.get(user=user)
        mining_active = mining_state.is_mining
        mining_rate = mining_state.current_rate
    except UserMiningState.DoesNotExist:
        pass
    
    # Get task stats
    completed_tasks = 0
    if hasattr(user, 'task_completions'):
        completed_tasks = user.task_completions.filter(status='verified').count()
    
    return JsonResponse({
        'followers': followers_count,
        'following': following_count,
        'referrals': user.referrals.count(),
        'mining_active': mining_active,
        'mining_rate': mining_rate,
        'completed_tasks': completed_tasks,
        'token_balance': float(user.userprofile.token_balance) if hasattr(user, 'userprofile') else 0,
        'recent_followers': recent_followers_data,
    })


def register(request):
    """User registration with referral"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            
            referrer = form.cleaned_data.get('referral_code')
            if referrer:
                user.referred_by = referrer
                user.save()
                
                SocialNotification.objects.create(
                    recipient=referrer,
                    sender=user,
                    notification_type='follow'
                )
                
                messages.success(request, f"Registration successful! You were referred by {referrer.username}")
            else:
                messages.success(request, "Registration successful!")
            
            login(request, user)
            return redirect('home')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'users/register.html', {'form': form})


def user_login(request):
    """User login"""
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('home')
        else:
            messages.error(request, "Invalid username or password.")
    
    return render(request, 'users/login.html')


def user_logout(request):
    """User logout"""
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect('home')


@login_required
def follow_list(request, username, list_type):
    """Show list of followers or following"""
    profile_user = get_object_or_404(CustomUser, username=username)
    
    if list_type == 'followers':
        follows = Follow.objects.filter(following=profile_user).select_related('follower', 'follower__userprofile')
        users = [follow.follower for follow in follows]
        list_title = f"Followers of {profile_user.username}"
    else:
        follows = Follow.objects.filter(follower=profile_user).select_related('following', 'following__userprofile')
        users = [follow.following for follow in follows]
        list_title = f"People followed by {profile_user.username}"
    
    current_user_following = set(
        Follow.objects.filter(follower=request.user).values_list('following_id', flat=True)
    )
    
    paginator = Paginator(users, 20)
    page = request.GET.get('page')
    users_page = paginator.get_page(page)
    
    context = {
        'profile_user': profile_user,
        'users': users_page,
        'list_type': list_type,
        'list_title': list_title,
        'current_user_following': current_user_following,
    }
    return render(request, 'users/follow_list.html', context)


@login_required
def notifications_list(request):
    """View all notifications"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    notifications.filter(is_read=False).update(is_read=True)
    
    paginator = Paginator(notifications, 20)
    page = request.GET.get('page')
    notifications = paginator.get_page(page)
    
    return render(request, 'users/notifications.html', {'notifications': notifications})


@login_required
def mark_notification_read(request, notification_id):
    """Mark notification as read"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'status': 'success'})
    return redirect('users:notifications')


@login_required
def delete_notification(request, notification_id):
    """Delete notification"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.delete()
    messages.success(request, "Notification deleted")
    return redirect('users:notifications')


@login_required
def admin_balances(request):
    """Admin view for managing balances"""
    if not request.user.is_superuser:
        return redirect('dashboard')
    
    users = CustomUser.objects.all().select_related('userprofile')
    total_tokens = sum(user.userprofile.token_balance for user in users)
    
    context = {
        'users': users,
        'total_tokens': total_tokens,
        'total_users': users.count(),
    }
    return render(request, 'users/admin_balances.html', context)


@login_required
def create_agent(request):
    """Create a new agent user (admin only)"""
    if not request.user.is_superuser:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if username and email and password:
            user = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                is_agent=True
            )
            messages.success(request, f"Agent {username} created successfully!")
            return redirect('users:admin_balances')
    
    return render(request, 'users/create_agent.html')


@login_required
def send_tokens(request):
    """Send tokens to user (admin only)"""
    if not request.user.is_superuser:
        return redirect('dashboard')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        amount = request.POST.get('amount')
        
        try:
            user = CustomUser.objects.get(username=username)
            amount = float(amount)
            
            user.userprofile.token_balance += amount
            user.userprofile.save()
            
            messages.success(request, f"Sent {amount} tokens to {username}")
            return redirect('users:admin_balances')
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found")
        except ValueError:
            messages.error(request, "Invalid amount")
    
    return render(request, 'users/send_tokens.html')
    
 # users/views.py - add this function
from django.http import JsonResponse
from django.shortcuts import redirect
from chat.models import Chat, ChatMessage

@login_required
def start_chat(request, username):
    """Start a chat with a user"""
    target_user = get_object_or_404(CustomUser, username=username)
    
    # Check if DM already exists
    existing_chat = Chat.objects.filter(
        chat_type='dm',
        participants=request.user
    ).filter(participants=target_user).first()
    
    if existing_chat:
        return redirect('chat:chat_detail', chat_id=existing_chat.id)
    
    # Create new DM
    chat = Chat.objects.create(
        chat_type='dm',
        created_by=request.user
    )
    chat.participants.add(request.user, target_user)
    chat.admins.add(request.user)
    
    return redirect('chat:chat_detail', chat_id=chat.id)   