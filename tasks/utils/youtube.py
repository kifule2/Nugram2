"""
YouTube verification with caching and batching
"""
import yt_dlp
import logging
import asyncio
from typing import Tuple, Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib

logger = logging.getLogger(__name__)

# Simple in-memory cache for comment lists
_comment_cache = {}  # {cache_key: (expires_at, comments_list)}


def _get_cache_key(video_url: str) -> str:
    """Generate cache key for video URL"""
    return hashlib.md5(video_url.encode()).hexdigest()


async def verify_comment(user_identifier: str, video_url: str, max_comments: int = 200) -> Tuple[Optional[bool], dict]:
    """
    Check if user commented on a YouTube video with caching
    
    Args:
        user_identifier: YouTube channel ID or @handle
        video_url: YouTube video URL
        max_comments: max comments to fetch
    
    Returns:
        (verified: bool, data: dict)
    """
    user_id = user_identifier.replace('@', '').strip().lower()
    cache_key = _get_cache_key(video_url)
    
    # Check cache first
    if cache_key in _comment_cache:
        expires_at, comments = _comment_cache[cache_key]
        if datetime.now() < expires_at:
            return _search_comments(user_id, comments, video_url)
    
    # Not in cache, fetch fresh
    result = await _fetch_comments_async(video_url, max_comments)
    
    if result is None:
        return None, {'error': 'Failed to fetch comments', 'needs_manual_review': True}
    
    comments, fetch_info = result
    
    # Cache for 2 minutes (120 seconds)
    _comment_cache[cache_key] = (datetime.now() + timedelta(seconds=120), comments)
    
    return _search_comments(user_id, comments, video_url, fetch_info)


def _search_comments(user_id: str, comments: list, video_url: str, fetch_info: dict = None) -> Tuple[Optional[bool], dict]:
    """Search comments list for user"""
    for comment in comments:
        author_id = comment.get('author_id', '').lower()
        author = comment.get('author', '').lower()
        
        if user_id in author_id or user_id in author:
            return True, {
                'comment': comment.get('text', '')[:200],
                'author': comment.get('author', ''),
                'timestamp': comment.get('timestamp'),
                'comment_id': comment.get('id'),
                'video_url': video_url,
                'method': 'cached' if fetch_info is None else 'fresh'
            }
    
    return False, {
        'reason': f'Comment not found in fetched comments',
        'video_url': video_url,
        'user_identifier': user_id,
        'comments_fetched': len(comments),
        'method': 'cached' if fetch_info is None else 'fresh'
    }


async def _fetch_comments_async(video_url: str, max_comments: int = 200) -> Tuple[list, dict]:
    """
    Fetch comments asynchronously using yt-dlp
    Runs in thread pool to avoid blocking
    """
    def sync_fetch():
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'getcomments': True,
            'max_comments': max_comments,
            'videostatus': 'newest',
        }
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=False)
                comments = info.get('comments', [])
                
                comments.sort(key=lambda x: x.get('timestamp', 0), reverse=True)
                
                fetch_info = {
                    'total_comments': len(comments),
                    'video_title': info.get('title', ''),
                    'video_id': info.get('id', '')
                }
                
                return comments, fetch_info
                
        except Exception as e:
            logger.error(f"YouTube fetch error: {e}")
            return None, {'error': str(e)}
    
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, sync_fetch)
    
    if result[0] is None:
        return None
    
    return result


async def verify_comment_batch(user_identifiers: list, video_url: str, max_comments: int = 200) -> Dict[str, bool]:
    """
    Batch verify multiple users against one video
    Fetches comments once for all users
    """
    user_ids = [uid.replace('@', '').strip().lower() for uid in user_identifiers]
    
    result = await _fetch_comments_async(video_url, max_comments)
    
    if result is None:
        return {uid: False for uid in user_identifiers}
    
    comments, fetch_info = result
    
    results = {}
    for original, normalized in zip(user_identifiers, user_ids):
        found = False
        for comment in comments:
            author_id = comment.get('author_id', '').lower()
            author = comment.get('author', '').lower()
            if normalized in author_id or normalized in author:
                found = True
                break
        results[original] = found
    
    return results


async def verify_watch(user_identifier: str, video_url: str, required_seconds: int = 30) -> Tuple[Optional[bool], dict]:
    """
    Verify user watched video for required time
    This requires client-side tracking
    """
    return None, {'message': 'Watch time tracked by client', 'required_seconds': required_seconds}


async def verify_subscribe(user_channel_id: str, target_channel_id: str) -> Tuple[Optional[bool], dict]:
    """
    Check if user subscribed to a channel
    Returns None (needs manual review)
    """
    return None, {
        'message': 'Subscription verification requires OAuth or manual review',
        'needs_manual_review': True
    }


def clear_cache() -> int:
    """Clear expired cache entries"""
    global _comment_cache
    now = datetime.now()
    expired = [k for k, (expires_at, _) in _comment_cache.items() if expires_at < now]
    for k in expired:
        del _comment_cache[k]
    return len(expired)


def extract_channel_id(url: str) -> Optional[str]:
    """Extract channel ID from YouTube URL"""
    import re
    patterns = [
        r'/channel/([^/?]+)',
        r'/c/([^/?]+)',
        r'/user/([^/?]+)',
        r'@([^/?]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None


def extract_video_id(url: str) -> Optional[str]:
    """Extract video ID from YouTube URL"""
    import re
    patterns = [
        r'v=([^&]+)',
        r'youtu.be/([^?]+)',
        r'embed/([^?]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    
    return None