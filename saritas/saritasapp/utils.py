from .models import Notification

def send_notification(user, notification_type, rental=None, message=''):
    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        rental=rental,
        message=message
    )

def notify_customer_about_approval(rental):
    Notification.objects.create(
        user=rental.customer.user,
        rental=rental,
        notification_type='rental_approved',
        message=f"Your rental request for '{rental.inventory.name}' has been approved!"
    )

def notify_customer_about_rejection(rental):
    Notification.objects.create(
        user=rental.customer.user,
        rental=rental,
        notification_type='rental_rejected',
        message=f"Your rental request for '{rental.inventory.name}' was rejected."
    )

def notify_customer_about_completion(rental):
    Notification.objects.create(
        user=rental.customer.user,
        rental=rental,
        notification_type='rental_completed',
        message=f"Your rental for '{rental.inventory.name}' is now marked as completed. Thank you!"
    )

def create_reservation_notification(reservation, status):
    status_messages = {
        'approved': 'Your reservation has been approved.',
        'rejected': 'Your reservation has been rejected.',
        'completed': 'Your reservation has been marked as completed.'
    }

    status_icons = {
        'approved': 'reservation_approved',
        'rejected': 'reservation_rejected',
        'completed': 'reservation_completed'
    }

    Notification.objects.create(
        user=reservation.customer.user,
        message=f"{status_messages.get(status, 'Reservation status updated')}",
        notification_type=status_icons.get(status, 'info')
    )

