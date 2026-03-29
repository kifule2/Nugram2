"""
Custom URL verification with streaming and fallback
"""
import httpx
import logging
from typing import Tuple, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Maximum bytes to read (50KB) - enough for most verification pages
MAX_STREAM_BYTES = 50 * 1024  # 50KB


async def verify_url_contains(url: str, keyword: str, streaming: bool = True) -> Tuple[Optional[bool], dict]:
    """
    Check if URL contains a specific keyword using streaming
    
    Args:
        url: URL to check
        keyword: keyword to search for
        streaming: if True, only read first 50KB
    
    Returns:
        (verified: bool, data: dict)
    """
    if not keyword:
        return True, {'message': 'No keyword required', 'url': url}
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        try:
            if streaming:
                # Stream response to limit memory usage
                async with client.stream('GET', url, headers=headers) as response:
                    if response.status_code != 200:
                        return False, {
                            'url': url,
                            'keyword': keyword,
                            'found': False,
                            'error': f'HTTP {response.status_code}'
                        }
                    
                    # Read in chunks, stop when keyword found or limit reached
                    bytes_read = 0
                    content = ''
                    keyword_lower = keyword.lower()
                    
                    async for chunk in response.aiter_bytes():
                        chunk_str = chunk.decode('utf-8', errors='ignore')
                        content += chunk_str
                        bytes_read += len(chunk_str)
                        
                        if keyword_lower in content.lower():
                            return True, {
                                'url': url,
                                'keyword': keyword,
                                'found': True,
                                'bytes_read': bytes_read,
                                'method': 'streaming'
                            }
                        
                        if bytes_read >= MAX_STREAM_BYTES:
                            # Keyword not found within limit
                            return False, {
                                'url': url,
                                'keyword': keyword,
                                'found': False,
                                'bytes_read': bytes_read,
                                'reason': f'Keyword not found in first {MAX_STREAM_BYTES} bytes',
                                'method': 'streaming'
                            }
                    
                    # End of stream, keyword not found
                    return False, {
                        'url': url,
                        'keyword': keyword,
                        'found': False,
                        'bytes_read': bytes_read,
                        'reason': 'End of page reached',
                        'method': 'streaming'
                    }
            
            else:
                # Full page download (fallback)
                response = await client.get(url, headers=headers)
                
                if response.status_code != 200:
                    return False, {
                        'url': url,
                        'keyword': keyword,
                        'found': False,
                        'error': f'HTTP {response.status_code}'
                    }
                
                found = keyword.lower() in response.text.lower()
                return found, {
                    'url': url,
                    'keyword': keyword,
                    'found': found,
                    'content_length': len(response.text),
                    'method': 'full'
                }
                
        except httpx.TimeoutException:
            logger.warning(f"Custom URL timeout: {url}")
            return None, {'error': 'Request timeout', 'url': url, 'needs_manual_review': True}
        except Exception as e:
            logger.error(f"Custom URL verification error: {e}")
            return None, {'error': str(e), 'needs_manual_review': True}


async def verify_redirect_chain(start_url: str, expected_end_url: str, follow_redirects: bool = True) -> Tuple[Optional[bool], dict]:
    """
    Verify that redirect chain ends at expected URL
    """
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=follow_redirects) as client:
            response = await client.get(start_url)
            final_url = str(response.url)
            
            if expected_end_url.lower() in final_url.lower():
                return True, {
                    'start_url': start_url,
                    'final_url': final_url,
                    'matched': True,
                    'redirect_count': len(response.history)
                }
            else:
                return False, {
                    'start_url': start_url,
                    'final_url': final_url,
                    'expected': expected_end_url,
                    'matched': False,
                    'redirect_count': len(response.history)
                }
                
    except Exception as e:
        return None, {'error': str(e), 'needs_manual_review': True}


def extract_domain(url: str) -> str:
    """Extract domain from URL"""
    parsed = urlparse(url)
    return parsed.netloc