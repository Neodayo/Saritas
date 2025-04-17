from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from saritasapp.models import Rental, User, Reservation
import logging

# Set up logger
logger = logging.getLogger(__name__)


# ---------------------------------------
# TASK 1: Notify staff about rental request
# ---------------------------------------
@shared_task(bind=True, max_retries=3)
def notify_staff_about_rental_request(self, rental_id):
    try:
        rental = Rental.objects.select_related('inventory').get(pk=rental_id)
        staff_users = User.objects.filter(is_staff=True).exclude(email='')

        if not staff_users:
            logger.warning("No staff users with email addresses found for notification.")
            return

        subject = f"New Rental Request: {rental.inventory.name if rental.inventory else 'Unknown Item'}"
        context = {
            'rental': rental,
            'admin_url': f"{settings.SITE_URL}/admin/saritasapp/rental/{rental.id}/change/",
            'site_name': getattr(settings, 'SITE_NAME', 'Sarita\'s')
        }

        message = render_to_string('customerapp/emails/new_rental_request.txt', context)
        html_message = render_to_string('customerapp/emails/new_rental_request.html', context)

        recipient_list = [user.email for user in staff_users]

        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            recipient_list,
            html_message=html_message,
            fail_silently=False
        )

        logger.info(f"Rental notification sent for rental ID {rental_id} to staff.")

    except Rental.DoesNotExist:
        logger.error(f"Rental request ID {rental_id} not found.")
    except Exception as e:
        logger.exception(f"Failed to send rental notification for rental ID {rental_id}")
        raise self.retry(countdown=60, exc=e)


# ---------------------------------------
# TASK 2: Send reservation confirmation and notify staff
# ---------------------------------------
@shared_task(bind=True, max_retries=3)
def send_reservation_notification(self, reservation_id):
    try:
        reservation = Reservation.objects.select_related('item', 'customer__user').get(pk=reservation_id)

        # Email to customer
        customer_email = reservation.customer.user.email if reservation.customer and reservation.customer.user else None
        if customer_email:
            customer_subject = f"Reservation Confirmation: {reservation.item.name}"
            customer_message = render_to_string(
                'customerapp/emails/reservation_confirmation.txt', {'reservation': reservation}
            )
            customer_html = render_to_string(
                'customerapp/emails/reservation_confirmation.html', {'reservation': reservation}
            )

            send_mail(
                customer_subject,
                customer_message,
                settings.DEFAULT_FROM_EMAIL,
                [customer_email],
                html_message=customer_html,
                fail_silently=False
            )

            logger.info(f"Reservation confirmation sent to customer ({customer_email}).")
        else:
            logger.warning(f"No valid email found for customer in reservation ID {reservation_id}")

        # Email to staff
        staff_subject = f"New Reservation: {reservation.item.name}"
        staff_message = render_to_string(
            'customerapp/emails/new_reservation_staff.txt', {'reservation': reservation}
        )

        staff_users = User.objects.filter(is_staff=True).exclude(email='')
        staff_emails = [user.email for user in staff_users]

        if staff_emails:
            send_mail(
                staff_subject,
                staff_message,
                settings.DEFAULT_FROM_EMAIL,
                staff_emails,
                fail_silently=False
            )
            logger.info(f"Reservation notification sent to staff for reservation ID {reservation_id}.")
        else:
            logger.warning("No staff users with email addresses found for reservation notification.")

    except Reservation.DoesNotExist:
        logger.error(f"Reservation ID {reservation_id} not found.")
    except Exception as e:
        logger.exception(f"Failed to send reservation notification for reservation ID {reservation_id}")
        raise self.retry(countdown=60, exc=e)
