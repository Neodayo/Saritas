# utils.py
import random
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

def send_otp_email(user):
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_created_at = timezone.now()
    user.save()

    subject = 'Verify your email'
    message = f'Hello {user.username},\n\nYour OTP for verifying your email is: {otp}\n\nThank you!'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    send_mail(subject, message, from_email, recipient_list)
