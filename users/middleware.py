# users/middleware.py
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

class AjaxAuthenticationMiddleware(MiddlewareMixin):
    """Handle AJAX requests for unauthenticated users"""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and not request.user.is_authenticated:
            return JsonResponse({
                'status': 'auth_required',
                'message': 'Please log in to perform this action.',
                'login_url': '/users/login/',
                'register_url': '/users/register/'
            }, status=401)
        return None