from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .models import UserMiningState
from django.shortcuts import render

@login_required
def dashboard(request):
    state, created = UserMiningState.objects.get_or_create(user=request.user)
    session_completed = state.check_session_completion()
    
    # Format remaining time
    hours, minutes, seconds = state.remaining_time
    remaining_time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    context = {
        'state': state,
        'elapsed_hours': state.elapsed_hours,
        'remaining_time': remaining_time_str,
        'progress_percentage': state.progress_percentage,
        'session_completed': session_completed,
    }
    return render(request, 'airdrop/dashboard.html', context)

@login_required
@require_POST
def toggle_mining(request):
    state, created = UserMiningState.objects.get_or_create(user=request.user)
    
    if state.is_mining:
        state.stop_mining()
        status = 'stopped'
    else:
        state.start_mining()
        status = 'started'
    
    hours, minutes, seconds = state.remaining_time
    
    return JsonResponse({
        'status': status,
        'is_mining': state.is_mining,
        'elapsed_hours': state.elapsed_hours,
        'remaining_time': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        'progress_percentage': state.progress_percentage,
        'total_points': state.total_points,
        'session_points': state.points_earned_today,
        'current_rate': state.current_rate,
    })

@login_required
def mining_status(request):
    state, created = UserMiningState.objects.get_or_create(user=request.user)
    session_completed = state.check_session_completion()
    
    hours, minutes, seconds = state.remaining_time
    
    return JsonResponse({
        'is_mining': state.is_mining,
        'elapsed_hours': state.elapsed_hours,
        'remaining_time': f"{hours:02d}:{minutes:02d}:{seconds:02d}",
        'progress_percentage': state.progress_percentage,
        'total_points': state.total_points,
        'session_points': state.points_earned_today,
        'current_rate': state.current_rate,
        'session_completed': session_completed,
    })