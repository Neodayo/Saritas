from saritasapp.models import User
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

def notify_staff_about_rental_request(rental):
    staff_users = User.objects.filter(is_staff=True)
    subject = f"New Rental Request: {rental.inventory.name}"
    
    message = render_to_string('customerapp/emails/new_rental_request.txt', {
        'rental': rental,
    })
    
    html_message = render_to_string('customerapp/emails/new_rental_request.html', {
        'rental': rental,
    })
    
    recipient_list = [user.email for user in staff_users if user.email]
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        html_message=html_message,
        fail_silently=True
    )