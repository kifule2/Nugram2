"""
Rewards and mining boost utilities
"""
import logging
from datetime import timedelta
from django.utils import timezone

logger = logging.getLogger(__name__)


def apply_mining_boost(user, boost, duration_hours=1):
    """
    Apply mining boost to user
    
    Args:
        user: User object
        boost: float - multiplier (e.g., 1.05 = 5% boost)
        duration_hours: int - how long boost lasts
    """
    try:
        from airdrop.models import UserMiningState
        
        mining_state, created = UserMiningState.objects.get_or_create(user=user)
        
        # Store original rate if not already boosted
        if not hasattr(mining_state, 'boost_expires_at') or not mining_state.boost_expires_at or mining_state.boost_expires_at < timezone.now():
            mining_state.original_rate = mining_state.current_rate
            mining_state.boost_expires_at = timezone.now() + timedelta(hours=duration_hours)
        
        # Apply boost multiplicatively
        mining_state.current_rate = mining_state.current_rate * boost
        mining_state.save()
        
        from users.models import Notification
        Notification.objects.create(
            user=user,
            message=f"⚡ Mining boost active! {boost}x multiplier for {duration_hours} hours!"
        )
        
        logger.info(f"Mining boost applied to {user.username}: {boost}x for {duration_hours}h")
        return True
        
    except Exception as e:
        logger.error(f"Error applying mining boost: {e}")
        return False


def expire_boosts():
    """Expire mining boosts that have passed their time"""
    from airdrop.models import UserMiningState
    
    expired = UserMiningState.objects.filter(
        boost_expires_at__lt=timezone.now(),
        current_rate__gt=1.0
    )
    
    count = 0
    for state in expired:
        state.current_rate = state.original_rate
        state.boost_expires_at = None
        state.save()
        count += 1
    
    if count:
        logger.info(f"Expired {count} mining boosts")
    
    return count