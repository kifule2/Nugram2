from django import template
from django.utils.safestring import mark_safe
import re

register = template.Library()

@register.filter
def linkify(text):
    """
    Convert URLs in text to clickable HTML links
    """
    if not text:
        return text
    
    # URL regex pattern
    url_pattern = re.compile(
        r'(https?://[^\s]+)|(www\.[^\s]+)|([a-zA-Z0-9.-]+\.[a-zA-Z]{2,}(?:/[^\s]*)?)'
    )
    
    def replace_url(match):
        url = match.group(0)
        # Add https:// if missing for www or domain-only links
        if url.startswith('www.'):
            full_url = 'https://' + url
        elif not url.startswith('http'):
            full_url = 'https://' + url
        else:
            full_url = url
        
        # Truncate long URLs for display
        display_url = url if len(url) <= 50 else url[:40] + '...'
        
        return f'<a href="{full_url}" target="_blank" rel="noopener noreferrer" style="color: #3b82f6; text-decoration: none; border-bottom: 1px solid rgba(59,130,246,0.3);">{display_url}</a>'
    
    result = url_pattern.sub(replace_url, text)
    return mark_safe(result)