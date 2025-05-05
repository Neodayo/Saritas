# customerapp/email_verification.py

import random
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages

def request_email(request):
    if request.method == "POST":
        email = request.POST.get('email')
        otp = random.randint(100000, 999999)
        request.session['verification_email'] = email
        request.session['otp'] = str(otp)

        subject = "Your Sarita's Email Verification OTP"
        message = f"Hello! Your OTP for verification is: {otp}"
        from_email = settings.DEFAULT_FROM_EMAIL

        send_mail(subject, message, from_email, [email], fail_silently=False)
        return redirect('customerapp:verify_otp')

    return render(request, 'customerapp/request_email.html')


def verify_otp(request):
    if request.method == "POST":
        input_otp = request.POST.get('otp')
        session_otp = request.session.get('otp')

        if input_otp == session_otp:
            messages.success(request, "Email successfully verified!")
            # You can now create user or redirect as needed
            return redirect('customerapp:homepage')
        else:
            messages.error(request, "Invalid OTP. Try again.")
            return redirect('customerapp:verify_otp')

    return render(request, 'customerapp/verify_otp.html')
