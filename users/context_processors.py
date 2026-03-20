# users/context_processors.py
from .models import CustomUser

def referral_info(request):
    """Add referral info to context"""
    if request.user.is_authenticated:
        return {
            'referral_code': request.user.username,
            'referrals_count': request.user.referrals.count(),
        }
    return {}