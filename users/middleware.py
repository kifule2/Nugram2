from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin

class AjaxAuthenticationMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # No action needed for process_request
        pass

    def process_view(self, request, view_func, view_args, view_kwargs):
        # Check if the request is AJAX and the user is not authenticated
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' and not request.user.is_authenticated:
            return JsonResponse({
                'status': 'auth_required',
                'message': 'Please log in or register to perform this action.',
                'login_url': '/users/login/',
                'register_url': '/users/register/'
            }, status=401)
        return None

    def process_response(self, request, response):
        # Add custom headers to the response if needed
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response