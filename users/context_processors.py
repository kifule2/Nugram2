from .models import CustomUser

def referral_info(request):
    if request.user.is_authenticated:
        return {
            'referral_code': request.user.username,
            'referrals': CustomUser.objects.filter(referred_by=request.user)
        }
    return {}