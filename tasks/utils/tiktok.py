"""
TikTok verification with cooldown and HTML checking
"""
import httpx
import logging
import random
from typing import Tuple, Optional
from django.utils import timezone

logger = logging.getLogger(__name__)

# Mobile user agents for TikTok
MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (Linux; Android 13; SM-A055F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 12; SM-A035F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36',
]


async def verify_follow(user_handle: str, target_handle: str, completion=None) -> Tuple[Optional[bool], dict]:
    """
    Verify TikTok follow with cooldown and HTML check
    
    Args:
        user_handle: user's TikTok handle (without @)
        target_handle: target account handle (without @)
        completion: optional TaskCompletion object for checking click time
    
    Returns:
        (verified: bool, data: dict)
    """
    user_handle = user_handle.lower().replace('@', '').strip()
    target_handle = target_handle.lower().replace('@', '').strip()
    
    # Step 1: Check cooldown if completion provided
    if completion and completion.submission_data.get('clicked_at'):
        clicked_at = completion.submission_data.get('clicked_at')
        if isinstance(clicked_at, str):
            from dateutil import parser
            clicked_at = parser.parse(clicked_at)
        
        time_since_click = (timezone.now() - clicked_at).total_seconds()
        
        # Require at least 15 seconds on the page
        if time_since_click < 15:
            return None, {
                'message': f'Please wait {int(15 - time_since_click)} more seconds before verifying',
                'time_remaining': int(15 - time_since_click),
                'cooldown_active': True
            }
    
    # Step 2: Hard verification via HTML check
    url = f"https://www.tiktok.com/@{target_handle}"
    
    headers = {
        'User-Agent': random.choice(MOBILE_USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            response = await client.get(url, headers=headers)
            
            if response.status_code == 200:
                response_lower = response.text.lower()
                
                patterns = [
                    f'"{user_handle}"',
                    f'{user_handle}',
                ]
                
                for pattern in patterns:
                    if pattern in response_lower:
                        return True, {
                            'method': 'hard_verify',
                            'found': True,
                            'pattern_used': pattern,
                            'handle': user_handle,
                            'target': target_handle
                        }
                
                return False, {
                    'method': 'hard_verify',
                    'found': False,
                    'reason': f'@{user_handle} not found in followers data',
                    'target': target_handle,
                    'suggestion': 'Make sure your account is public and you followed @' + target_handle
                }
            
            elif response.status_code == 429:
                return None, {'error': 'Rate limited', 'retry_after': 60, 'needs_manual_review': True}
            
            elif response.status_code == 404:
                return False, {'error': 'Account not found', 'target': target_handle}
            
            else:
                return None, {
                    'error': f'HTTP {response.status_code}',
                    'needs_manual_review': True,
                    'fallback': 'screenshot'
                }
                
        except httpx.TimeoutException:
            logger.warning(f"TikTok verification timeout for {target_handle}")
            return None, {'error': 'Request timeout', 'needs_manual_review': True}
        except Exception as e:
            logger.error(f"TikTok verification error: {e}")
            return None, {'error': str(e), 'needs_manual_review': True}


def track_click(completion) -> bool:
    """Record that user clicked the TikTok link"""
    completion.submission_data['clicked'] = True
    completion.submission_data['clicked_at'] = timezone.now().isoformat()
    completion.save()
    return True


async def verify_follow_batch(user_handles: list, target_handle: str) -> dict:
    """
    Batch check multiple users against one TikTok profile
    """
    target_handle = target_handle.lower().replace('@', '').strip()
    url = f"https://www.tiktok.com/@{target_handle}"
    
    headers = {
        'User-Agent': random.choice(MOBILE_USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    }
    
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(url, headers=headers)
            
            if response.status_code != 200:
                return {handle: False for handle in user_handles}
            
            response_lower = response.text.lower()
            results = {}
            
            for handle in user_handles:
                clean_handle = handle.lower().replace('@', '').strip()
                found = clean_handle in response_lower
                results[handle] = found
            
            return results
            
        except Exception as e:
            logger.error(f"TikTok batch verification error: {e}")
            return {handle: False for handle in user_handles}