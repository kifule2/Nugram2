from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.core.paginator import Paginator
from django.utils import timezone
from django.utils.text import slugify
import json
import logging

from .models import Task, TaskCompletion, TaskRequest, SocialProfile
from .utils.verification import VerificationService
from .utils.rewards import apply_mining_boost
from users.models import Notification

logger = logging.getLogger(__name__)


@login_required
def connect_social(request):
    """Connect social media accounts"""
    profiles = {
        p.platform: p for p in request.user.social_profiles.all()
    }
    
    if request.method == 'POST':
        platform = request.POST.get('platform')
        handle = request.POST.get('handle', '').strip().replace('@', '')
        
        if platform and handle:
            profile, created = SocialProfile.objects.update_or_create(
                user=request.user,
                platform=platform,
                defaults={'handle': handle}
            )
            
            if created:
                messages.success(request, f"{profile.get_platform_display()} connected successfully!")
            else:
                messages.success(request, f"{profile.get_platform_display()} updated!")
            
            return redirect('tasks:connect_social')
        else:
            messages.error(request, "Please provide both platform and handle")
    
    context = {
        'profiles': profiles,
        'platforms': SocialProfile.PLATFORM_CHOICES,
        'user_points': request.user.userprofile.token_balance or 0,
    }
    return render(request, 'tasks/connect_social.html', context)


@login_required
def task_marketplace(request):
    """Main task marketplace - search first"""
    query = request.GET.get('q', '')
    search_results = None
    
    if query:
        search_results = Task.objects.filter(
            Q(name__icontains=query) |
            Q(task_code__icontains=query) |
            Q(description__icontains=query),
            is_active=True,
            expiry_date__gt=timezone.now()
        ).exclude(
            completions__user=request.user,
            completions__status='verified'
        ).select_related('created_by')[:20]
    
    # Get user's tasks
    user_completions = TaskCompletion.objects.filter(user=request.user)
    
    active_tasks = user_completions.filter(
        status__in=['pending', 'processing']
    ).select_related('task')
    
    completed_tasks = user_completions.filter(
        status='verified'
    ).select_related('task').order_by('-verified_at')[:10]
    
    pending_requests = TaskRequest.objects.filter(
        user=request.user,
        status='pending'
    ).select_related('task')
    
    # Stats
    user_points = request.user.userprofile.token_balance or 0
    today_points = user_completions.filter(
        verified_at__date=timezone.now().date(),
        status='verified'
    ).aggregate(total=Sum('task__points_reward'))['total'] or 0
    week_points = user_completions.filter(
        verified_at__gte=timezone.now() - timezone.timedelta(days=7),
        status='verified'
    ).aggregate(total=Sum('task__points_reward'))['total'] or 0
    
    # Get user's social profiles
    social_profiles = {p.platform: p.handle for p in request.user.social_profiles.all()}
    
    context = {
        'query': query,
        'search_results': search_results,
        'active_tasks': active_tasks,
        'completed_tasks': completed_tasks,
        'pending_requests': pending_requests,
        'user_points': user_points,
        'today_points': today_points,
        'week_points': week_points,
        'social_profiles': social_profiles,
    }
    
    return render(request, 'tasks/marketplace.html', context)


@login_required
def task_detail(request, task_code):
    """View single task details"""
    task = get_object_or_404(Task, task_code=task_code, is_active=True)
    
    # Check if already completed
    completion = TaskCompletion.objects.filter(task=task, user=request.user).first()
    pending_request = TaskRequest.objects.filter(task=task, user=request.user, status='pending').first()
    
    # Check if user has required social profile
    has_profile = False
    profile_handle = None
    if task.platform:
        profile = SocialProfile.objects.filter(
            user=request.user,
            platform=task.platform
        ).first()
        has_profile = bool(profile)
        profile_handle = profile.handle if profile else None
    
    # Get task stats
    total_completed = task.completions.filter(status='verified').count()
    recent_completions = task.completions.filter(status='verified').select_related('user')[:5]
    
    context = {
        'task': task,
        'completion': completion,
        'pending_request': pending_request,
        'has_profile': has_profile,
        'profile_handle': profile_handle,
        'total_completed': total_completed,
        'recent_completions': recent_completions,
        'task_type_icon': get_task_type_icon(task.platform or task.task_type),
        'task_type_color': get_task_type_color(task.platform or task.task_type),
        'user_points': request.user.userprofile.token_balance or 0,
    }
    
    return render(request, 'tasks/task_detail.html', context)


@login_required
@require_POST
def join_task(request, task_code):
    """Request to join a task"""
    task = get_object_or_404(Task, task_code=task_code)
    
    # Check if already completed
    if TaskCompletion.objects.filter(task=task, user=request.user).exists():
        messages.warning(request, "You've already completed or attempted this task!")
        return redirect('tasks:marketplace')
    
    # Check if has required profile
    if task.platform and task.platform != 'custom':
        if not SocialProfile.objects.filter(user=request.user, platform=task.platform).exists():
            messages.error(request, f"Please connect your {task.get_platform_display()} account first!")
            return redirect('tasks:connect_social')
    
    # Check if needs approval
    if task.requires_approval:
        request_obj, created = TaskRequest.objects.get_or_create(
            task=task,
            user=request.user,
            defaults={'status': 'pending'}
        )
        if created:
            messages.success(request, f"Request sent to join '{task.name}'! Waiting for creator approval.")
        else:
            messages.info(request, "You already have a pending request for this task.")
    else:
        # Create completion directly
        completion, created = TaskCompletion.objects.get_or_create(
            task=task,
            user=request.user,
            defaults={'status': 'pending'}
        )
        if created:
            messages.success(request, f"You've joined '{task.name}'! Complete the action and click Verify.")
        else:
            messages.info(request, "You're already working on this task.")
    
    return redirect('tasks:task_detail', task_code=task_code)


@login_required
def task_work(request, task_code):
    """Work on task interface"""
    task = get_object_or_404(Task, task_code=task_code)
    completion = get_object_or_404(TaskCompletion, task=task, user=request.user)
    
    # For TikTok and Social tasks, show redirect interface
    if task.platform in ['tiktok', 'social'] or task.task_type in ['tiktok', 'social']:
        return render(request, 'tasks/task_redirect.html', {
            'task': task,
            'completion': completion,
        })
    
    # For learning tasks with quiz
    if task.task_type == 'learning' and task.task_data.get('quiz'):
        return render(request, 'tasks/task_quiz.html', {
            'task': task,
            'completion': completion,
            'quiz': task.task_data.get('quiz', []),
        })
    
    # For YouTube watch tasks
    if task.platform == 'youtube' and task.action == 'watch':
        return render(request, 'tasks/task_watch.html', {
            'task': task,
            'completion': completion,
            'video_url': task.target_url,
            'required_seconds': task.task_data.get('required_seconds', 30),
        })
    
    context = {
        'task': task,
        'completion': completion,
        'target_url': task.target_url,
        'platform': task.platform,
        'action': task.action,
    }
    
    return render(request, 'tasks/task_work.html', context)


@login_required
@require_POST
def verify_task(request, task_code):
    """Trigger verification for a task"""
    task = get_object_or_404(Task, task_code=task_code)
    completion = get_object_or_404(TaskCompletion, task=task, user=request.user)
    
    # For TikTok/Social, track the click
    if task.platform in ['tiktok', 'social'] or task.task_type in ['tiktok', 'social']:
        completion.submission_data['clicked'] = True
        completion.submission_data['clicked_at'] = timezone.now().isoformat()
        completion.save()
        messages.success(request, "Click recorded! Waiting for verification...")
        return redirect('tasks:task_detail', task_code=task_code)
    
    # For quiz tasks
    if task.task_type == 'learning' and task.task_data.get('quiz'):
        answers = {}
        for key, value in request.POST.items():
            if key.startswith('q_'):
                answers[key] = value
        completion.submission_data['quiz_answers'] = answers
        completion.save()
    
    # For watch tasks
    if task.platform == 'youtube' and task.action == 'watch':
        watch_time = int(request.POST.get('watch_time', 0))
        completion.submission_data['watch_time'] = watch_time
        completion.save()
    
    # Run verification
    verified, data = VerificationService.verify(completion)
    
    if verified:
        messages.success(request, f"✓ Task verified! +{task.points_reward} points earned!")
    elif verified is False:
        messages.error(request, f"Verification failed. {data.get('reason', 'Please try again')}")
    else:
        messages.info(request, "Verification in progress. Check back in a moment or refresh the page.")
    
    return redirect('tasks:task_detail', task_code=task_code)


@login_required
def track_click(request, task_code):
    """Track link click for TikTok/Social tasks"""
    task = get_object_or_404(Task, task_code=task_code)
    
    if task.platform in ['tiktok', 'social'] or task.task_type in ['tiktok', 'social']:
        completion, _ = TaskCompletion.objects.get_or_create(
            task=task,
            user=request.user,
            defaults={'status': 'pending'}
        )
        
        completion.submission_data['clicked'] = True
        completion.submission_data['clicked_at'] = timezone.now().isoformat()
        completion.save()
        
        # Return the target URL to redirect to
        return JsonResponse({'url': task.target_url})
    
    return JsonResponse({'error': 'Invalid task type'}, status=400)


@login_required
def cancel_request(request, task_code):
    """Cancel pending join request"""
    task = get_object_or_404(Task, task_code=task_code)
    
    task_request = TaskRequest.objects.filter(
        task=task,
        user=request.user,
        status='pending'
    ).first()
    
    if task_request:
        task_request.delete()
        messages.success(request, f"Cancelled request to join '{task.name}'")
    else:
        messages.error(request, "No pending request found")
    
    return redirect('tasks:marketplace')


# Creator Views

@login_required
def my_created_tasks(request):
    """Tasks created by user (for agents/admins)"""
    if not request.user.is_superuser and not request.user.is_agent:
        messages.warning(request, "Only agents and admins can create tasks.")
        return redirect('tasks:marketplace')
    
    tasks = Task.objects.filter(created_by=request.user).order_by('-created_at')
    
    # Get stats for each task
    for task in tasks:
        task.completed_count = task.completions.filter(status='verified').count()
        task.pending_count = task.completions.filter(status='pending').count()
        task.requests_count = task.join_requests.filter(status='pending').count()
    
    pending_requests = TaskRequest.objects.filter(
        task__in=tasks,
        status='pending'
    ).select_related('task', 'user')
    
    context = {
        'tasks': tasks,
        'pending_requests': pending_requests,
        'total_tasks': tasks.count(),
        'total_participants': sum(t.completed_count for t in tasks),
    }
    return render(request, 'tasks/creator_dashboard.html', context)


@login_required
def create_task(request):
    """Create a new task"""
    if not request.user.is_superuser and not request.user.is_agent:
        messages.warning(request, "Only agents and admins can create tasks.")
        return redirect('tasks:marketplace')
    
    if request.method == 'POST':
        name = request.POST.get('name')
        description = request.POST.get('description')
        task_type = request.POST.get('task_type')
        platform = request.POST.get('platform')
        action = request.POST.get('action')
        target_url = request.POST.get('target_url')
        target_identifier = request.POST.get('target_identifier', '')
        points_reward = int(request.POST.get('points_reward', 50))
        mining_boost = float(request.POST.get('mining_boost', 1.05))
        boost_duration = int(request.POST.get('boost_duration', 1))
        verification_method = request.POST.get('verification_method', 'auto')
        requires_approval = request.POST.get('requires_approval') == 'on'
        max_participants = request.POST.get('max_participants')
        
        # Build task_data from additional fields
        task_data = {}
        if task_type == 'learning':
            task_data['video_url'] = request.POST.get('video_url')
            task_data['required_seconds'] = int(request.POST.get('required_seconds', 30))
        elif task_type == 'custom':
            task_data['keyword'] = request.POST.get('keyword', '')
            task_data['success_message'] = request.POST.get('success_message', '')
        
        task = Task.objects.create(
            name=name,
            description=description,
            task_type=task_type,
            platform=platform if platform != 'custom' else None,
            action=action,
            target_url=target_url,
            target_identifier=target_identifier,
            points_reward=points_reward,
            mining_boost=mining_boost,
            boost_duration_hours=boost_duration,
            verification_method=verification_method,
            requires_approval=requires_approval,
            max_participants=int(max_participants) if max_participants else None,
            task_data=task_data,
            created_by=request.user,
        )
        
        messages.success(request, f"Task '{name}' created! Task Code: {task.task_code}")
        return redirect('tasks:my_created_tasks')
    
    context = {
        'task_types': Task.PLATFORM_CHOICES,
        'actions': Task.ACTION_CHOICES,
        'platforms': [('twitter', 'Twitter/X'), ('youtube', 'YouTube'), ('tiktok', 'TikTok'), ('custom', 'Custom URL')],
    }
    return render(request, 'tasks/create_task.html', context)


@login_required
def edit_task(request, task_id):
    """Edit an existing task"""
    task = get_object_or_404(Task, id=task_id, created_by=request.user)
    
    if not request.user.is_superuser and not request.user.is_agent:
        messages.warning(request, "Only agents and admins can edit tasks.")
        return redirect('tasks:marketplace')
    
    if request.method == 'POST':
        task.name = request.POST.get('name')
        task.description = request.POST.get('description')
        task.target_url = request.POST.get('target_url')
        task.target_identifier = request.POST.get('target_identifier', '')
        task.points_reward = int(request.POST.get('points_reward', 50))
        task.mining_boost = float(request.POST.get('mining_boost', 1.05))
        task.boost_duration_hours = int(request.POST.get('boost_duration', 1))
        task.verification_method = request.POST.get('verification_method', 'auto')
        task.requires_approval = request.POST.get('requires_approval') == 'on'
        task.max_participants = request.POST.get('max_participants')
        task.is_active = request.POST.get('is_active') == 'on'
        
        task.save()
        messages.success(request, f"Task '{task.name}' updated!")
        return redirect('tasks:my_created_tasks')
    
    context = {
        'task': task,
        'task_types': Task.PLATFORM_CHOICES,
        'actions': Task.ACTION_CHOICES,
    }
    return render(request, 'tasks/edit_task.html', context)


@login_required
@require_POST
def delete_task(request, task_id):
    """Delete a task"""
    task = get_object_or_404(Task, id=task_id, created_by=request.user)
    
    if not request.user.is_superuser and not request.user.is_agent:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    task_name = task.name
    task.delete()
    messages.success(request, f"Task '{task_name}' deleted!")
    
    return redirect('tasks:my_created_tasks')


@login_required
@require_POST
def approve_participant(request, request_id):
    """Approve user to join task"""
    task_request = get_object_or_404(
        TaskRequest,
        id=request_id,
        task__created_by=request.user,
        status='pending'
    )
    
    task_request.approve(request.user)
    messages.success(request, f"Approved {task_request.user.username} to join {task_request.task.name}")
    
    return redirect('tasks:my_created_tasks')


@login_required
@require_POST
def reject_participant(request, request_id):
    """Reject user from task"""
    task_request = get_object_or_404(
        TaskRequest,
        id=request_id,
        task__created_by=request.user,
        status='pending'
    )
    
    reason = request.POST.get('reason', 'Not specified')
    task_request.reject(request.user, reason)
    messages.success(request, f"Rejected {task_request.user.username} from joining {task_request.task.name}")
    
    return redirect('tasks:my_created_tasks')


# API Endpoints

@login_required
def search_task_api(request):
    """AJAX endpoint for task search"""
    query = request.GET.get('q', '')
    
    if not query:
        return JsonResponse({'results': []})
    
    tasks = Task.objects.filter(
        Q(name__icontains=query) |
        Q(task_code__icontains=query),
        is_active=True,
        expiry_date__gt=timezone.now()
    ).exclude(
        completions__user=request.user,
        completions__status='verified'
    )[:10]
    
    results = []
    for task in tasks:
        results.append({
            'id': task.id,
            'name': task.name,
            'task_code': task.task_code,
            'task_type': task.task_type,
            'points_reward': task.points_reward,
            'mining_boost': task.mining_boost,
            'description': task.description[:100],
            'participants': task.completions.filter(status='verified').count(),
            'url': task.get_absolute_url() if hasattr(task, 'get_absolute_url') else f'/tasks/task/{task.task_code}/'
        })
    
    return JsonResponse({'results': results})


@login_required
def user_task_stats(request):
    """Get user task statistics"""
    completions = TaskCompletion.objects.filter(user=request.user)
    
    stats = {
        'total_completed': completions.filter(status='verified').count(),
        'total_points': completions.filter(status='verified').aggregate(total=Sum('task__points_reward'))['total'] or 0,
        'active_tasks': completions.filter(status__in=['pending', 'processing']).count(),
        'today_completed': completions.filter(verified_at__date=timezone.now().date(), status='verified').count(),
        'week_completed': completions.filter(verified_at__gte=timezone.now() - timezone.timedelta(days=7), status='verified').count(),
        'mining_boost_active': request.user.userprofile.mining_boost_active if hasattr(request.user.userprofile, 'mining_boost_active') else False,
    }
    
    return JsonResponse(stats)


@login_required
def task_leaderboard(request):
    """Get top task completers"""
    from django.db.models import Count, Sum
    
    leaders = User.objects.filter(
        task_completions__status='verified'
    ).annotate(
        tasks_completed=Count('task_completions', filter=Q(task_completions__status='verified')),
        total_points=Sum('task_completions__task__points_reward', filter=Q(task_completions__status='verified'))
    ).order_by('-total_points')[:10]
    
    results = []
    for user in leaders:
        results.append({
            'username': user.username,
            'display_name': user.userprofile.display_name if hasattr(user, 'userprofile') else user.username,
            'avatar': user.userprofile.profile_picture.url if hasattr(user, 'userprofile') and user.userprofile.profile_picture else None,
            'tasks_completed': user.tasks_completed,
            'total_points': user.total_points,
        })
    
    return JsonResponse({'leaders': results})


@csrf_exempt
def verification_webhook(request):
    """Webhook for external verification services"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        completion_id = data.get('completion_id')
        verified = data.get('verified', False)
        result_data = data.get('data', {})
        
        completion = TaskCompletion.objects.get(id=completion_id)
        
        if verified:
            completion.verify()
        else:
            completion.fail(result_data.get('reason', 'External verification failed'))
        
        return JsonResponse({'status': 'ok'})
        
    except TaskCompletion.DoesNotExist:
        return JsonResponse({'error': 'Completion not found'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


# Helper functions

def get_task_type_icon(platform):
    icons = {
        'twitter': 'fab fa-twitter',
        'youtube': 'fab fa-youtube',
        'tiktok': 'fab fa-tiktok',
        'custom': 'fas fa-link',
        'social': 'fas fa-share-alt',
        'kyc': 'fas fa-shield-alt',
        'learning': 'fas fa-graduation-cap',
        'referral': 'fas fa-users',
        'twitter': 'fab fa-twitter',
        'youtube': 'fab fa-youtube',
        'tiktok': 'fab fa-tiktok',
    }
    return icons.get(platform, 'fas fa-tasks')


def get_task_type_color(platform):
    colors = {
        'twitter': '#1DA1F2',
        'youtube': '#FF0000',
        'tiktok': '#000000',
        'custom': '#8B5CF6',
        'social': '#3B82F6',
        'kyc': '#10B981',
        'learning': '#F59E0B',
        'referral': '#8B5CF6',
    }
    return colors.get(platform, '#6B7280')