from django.shortcuts import render
from users.models import Notification

def home(request):
    if request.user.is_authenticated:
        # Fetch the latest 5 unread notifications
        unread_notifications = request.user.notifications.filter(is_read=False).order_by('-created_at')[:5]
    else:
        unread_notifications = []

    context = {
        'unread_notifications': unread_notifications,
    }
    return render(request, 'home.html', context)