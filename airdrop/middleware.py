from django.utils import timezone
from .models import UserMiningState

class MiningIntegrityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        if request.user.is_authenticated:
            try:
                state = UserMiningState.objects.get(user=request.user)
                if state.last_tap and state.last_tap > timezone.now():
                    state.last_tap = timezone.now()
                    state.save()
            except UserMiningState.DoesNotExist:
                pass
        
        return response