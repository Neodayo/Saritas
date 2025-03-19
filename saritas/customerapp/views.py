from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from .forms import CustomerSignUpForm, CustomerLoginForm
from saritasapp.models import Customer

def customer_signup(request):
    if request.method == 'POST':
        form = CustomerSignUpForm(request.POST, request.FILES)
        if form.is_valid():
            # Create User
            user = form.save()
            
            # Create Customer
            Customer.objects.create(
                user=user,
                first_name=form.cleaned_data['first_name'],
                last_name=form.cleaned_data['last_name'],
                email=form.cleaned_data['email'],
                phone=form.cleaned_data['phone'],
                address=form.cleaned_data['address'],
                image=form.cleaned_data['image']
            )
            
            # Auto-login after signup
            login(request, user)
            return redirect('customer_dashboard')
    else:
        form = CustomerSignUpForm()
    return render(request, 'customerapp/register.html', {'form': form})

def customer_login(request):
    if request.method == 'POST':
        form = CustomerLoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                return redirect('customerapp:customer_dashboard')
    else:
        form = CustomerLoginForm()
    return render(request, 'customerapp/login.html', {'form': form})

def customer_dashboard(request):
    return render(request, 'customerapp/customer_dashboard.html')
