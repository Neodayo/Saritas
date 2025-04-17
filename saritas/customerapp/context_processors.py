from django.core.cache import cache
from saritasapp.models import Notification

def notifications(request):
    if request.user.is_authenticated:
        cache_key = f'unread_count_{request.user.id}'
        count = cache.get(cache_key)
        if count is None:
            count = Notification.objects.filter(
                user=request.user, 
                is_read=False
            ).count()
            cache.set(cache_key, count, 60)  # Cache for 60 seconds
        return {'unread_count': count}
    return {'unread_count': 0}