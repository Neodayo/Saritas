from celery import shared_task
from django.utils import timezone
from .models import Rental, Notification
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def check_and_mark_overdue_rentals(self):
    try:
        today = timezone.now().date()
        overdue = Rental.objects.filter(
            status="Rented", 
            rental_end__lt=today
        ).update(status="Overdue")
        
        logger.info(f"Marked {overdue} rentals as overdue")
        return overdue
    except Exception as e:
        logger.error(f"Error marking overdue rentals: {str(e)}")
        self.retry(exc=e, countdown=300)  # Retry after 5 minutes

@shared_task
def send_notification(user_id, notification_type, message, rental_id=None):
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = User.objects.get(pk=user_id)
        rental = Rental.objects.get(pk=rental_id) if rental_id else None
        
        Notification.objects.create(
            user=user,
            notification_type=notification_type,
            rental=rental,
            message=message
        )
    except Exception as e:
        logger.error(f"Failed to create notification: {str(e)}")
        raise