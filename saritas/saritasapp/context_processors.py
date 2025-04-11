from saritasapp.models import Notification

def notifications(request):
    if request.user.is_authenticated:
        return {
            'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
        }
    return {}