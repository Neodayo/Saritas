from celery import shared_task
from django.core.mail import send_mail
from saritasapp.models import Inventory, Customer, Reservation, Rental
from django.conf import settings
from django.template.loader import render_to_string

@shared_task
def notify_staff_about_rental_request(rental_id):
    rental = Rental.objects.get(pk=rental_id)

@shared_task
def send_reservation_notification(reservation_id):
    reservation = Reservation.objects.get(id=reservation_id)
    
    # Email to customer
    subject = f"Reservation Confirmation: {reservation.item.name}"
    message = render_to_string('customerapp/emails/reservation_confirmation.txt', {'reservation': reservation})
    html_message = render_to_string('customerapp/emails/reservation_confirmation.html', {'reservation': reservation})
    send_mail(
        subject,
        message,
        'noreply@yourdomain.com',
        [reservation.customer.user.email],
        html_message=html_message
    )
    
    # Email to staff
    subject = f"New Reservation: {reservation.item.name}"
    message = render_to_string('customerapp/emails/new_reservation_staff.txt', {'reservation': reservation})
    send_mail(
        subject,
        message,
        'noreply@yourdomain.com',
        ['staff@yourdomain.com'],
    )
