from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import CustomerRegistrationForm
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction

def register(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Registration successful!")
                return redirect('customerapp/login')
            except IntegrityError as e:
                messages.error(request, "Database error. Please try again.")
                # Log the error: print(e) or use logging module
        else:
            # Show specific phone number errors
            if 'phone' in form.errors:
                messages.error(request, "Invalid or duplicate phone number")
            else:
                messages.error(request, "Please correct the errors below")
    else:
        form = CustomerRegistrationForm()
    
    return render(request, 'customerapp/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('customerapp:dashboard')  # Redirect to your desired page
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = AuthenticationForm()

    return render(request, 'customerapp/login.html', {'form': form})

@login_required
def customer_dashboard(request):
    return render(request, 'customerapp/dashboard.html')
