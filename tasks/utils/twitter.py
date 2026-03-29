"""
Twitter/X verification using mobile endpoint for stealth
"""
import httpx
import logging
import random
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

# Mobile user agents for stealth
MOBILE_USER_AGENTS = [
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
    'Mozilla/5.0 (Linux; Android 13; SM-A055F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.144 Mobile Safari/537.36',
    'Mozilla/5.0 (Linux; Android 12; SM-A035F) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.6045.163 Mobile Safari/537.36',
]


async def verify_follow(user_handle: str, target_handle: str, client: httpx.AsyncClient = None) -> Tuple[Optional[bool], dict]:
    """
    Check if user_handle follows target_handle on Twitter using mobile endpoint
    
    Args:
        user_handle: user's Twitter handle (without @)
        target_handle: target account handle (without @)
        client: optional httpx client (for connection pooling)
    
    Returns:
        (verified: bool, data: dict)
    """
    user_handle = user_handle.lower().replace('@', '').strip()
    target_handle = target_handle.lower().replace('@', '').strip()
    
    # Use mobile URL - lightweight HTML version
    url = f"https://mobile.x.com/{target_handle}/followers"
    
    # Use rotating user agent
    headers = {
        'User-Agent': random.choice(MOBILE_USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    
    close_client = False
    if client is None:
        client = httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        close_client = True
    
    try:
        response = await client.get(url, headers=headers)
        
        if response.status_code == 200:
            # Simple string search - no DOM parsing to save RAM
            found = user_handle in response.text.lower()
            
            if found:
                return True, {
                    'method': 'mobile_followers',
                    'found': True,
                    'handle': user_handle,
                    'target': target_handle,
                    'status_code': response.status_code
                }
            else:
                return False, {
                    'method': 'mobile_followers',
                    'found': False,
                    'reason': f'@{user_handle} not found in followers list',
                    'target': target_handle
                }
        
        elif response.status_code == 429:
            return None, {'error': 'Rate limited', 'retry_after': response.headers.get('Retry-After', 60)}
        
        elif response.status_code == 404:
            return False, {'error': 'Account not found', 'target': target_handle}
        
        else:
            return False, {'error': f'HTTP {response.status_code}', 'target': target_handle}
            
    except httpx.TimeoutException:
        logger.warning(f"Twitter verification timeout for {target_handle}")
        return None, {'error': 'Request timeout', 'needs_manual_review': True}
    except Exception as e:
        logger.error(f"Twitter verification error: {e}")
        return None, {'error': str(e), 'needs_manual_review': True}
    finally:
        if close_client:
            await client.aclose()


async def verify_like(user_handle: str, tweet_url: str) -> Tuple[Optional[bool], dict]:
    """
    Check if user liked a tweet
    Note: Twitter doesn't expose who liked a tweet publicly
    Returns None (needs manual review)
    """
    # Twitter doesn't expose who liked a tweet publicly
    # For now, return None meaning manual review needed
    return None, {
        'message': 'Manual review required for likes',
        'tweet_url': tweet_url,
        'user_handle': user_handle,
        'needs_manual_review': True
    }


async def verify_follow_batch(user_handles: list, target_handle: str) -> dict:
    """
    Batch check multiple users against one target
    Saves requests by fetching followers list once
    
    Args:
        user_handles: list of user handles to check
        target_handle: target account to check against
    
    Returns:
        dict: {handle: bool} for each user
    """
    target_handle = target_handle.lower().replace('@', '').strip()
    url = f"https://mobile.x.com/{target_handle}/followers"
    
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
                results[handle] = clean_handle in response_lower
            
            return results
            
        except Exception as e:
            logger.error(f"Batch verification error: {e}")
            return {handle: False for handle in user_handles}


def extract_tweet_id(url: str) -> Optional[str]:
    """Extract tweet ID from URL"""
    import re
    match = re.search(r'/status/(\d+)', url)
    return match.group(1) if match else None