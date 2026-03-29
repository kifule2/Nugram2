from django import template
from django.utils import timezone
from datetime import timedelta

register = template.Library()


@register.filter
def divide(value, arg):
    """Divide value by arg"""
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0


@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0


@register.filter
def format_points(value):
    """Format points with thousands separator"""
    if not value:
        return "0"
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return "0"


@register.filter
def task_progress(completion):
    """Get task progress percentage"""
    if not completion:
        return 0
    if hasattr(completion, 'progress_percentage'):
        return completion.progress_percentage
    return 0


@register.filter
def time_left(expiry_date):
    """Get time left as string"""
    if not expiry_date:
        return "No expiry"
    
    now = timezone.now()
    if expiry_date < now:
        return "Expired"
    
    delta = expiry_date - now
    
    if delta.days > 0:
        return f"{delta.days} days left"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600} hours left"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60} minutes left"
    else:
        return f"{delta.seconds} seconds left"


@register.filter
def platform_icon(platform):
    """Get FontAwesome icon for platform"""
    icons = {
        'twitter': 'fab fa-twitter',
        'youtube': 'fab fa-youtube',
        'tiktok': 'fab fa-tiktok',
        'custom': 'fas fa-link',
        'social': 'fas fa-share-alt',
        'kyc': 'fas fa-shield-alt',
        'learning': 'fas fa-graduation-cap',
        'referral': 'fas fa-users',
    }
    return icons.get(platform, 'fas fa-tasks')


@register.filter
def platform_color(platform):
    """Get color for platform"""
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


@register.filter
def status_badge(status):
    """Get Bootstrap badge class for status"""
    badges = {
        'pending': 'warning',
        'processing': 'info',
        'verified': 'success',
        'failed': 'danger',
        'expired': 'secondary',
        'rejected': 'dark',
        'approved': 'success',
    }
    return badges.get(status, 'secondary')


@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    try:
        return dictionary.get(key, '')
    except (AttributeError, TypeError):
        return ''