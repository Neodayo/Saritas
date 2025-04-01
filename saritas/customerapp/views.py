from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import CustomerRegistrationForm, RentalForm, ReservationForm
from django.urls import reverse
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.shortcuts import render
from saritasapp.models import Inventory, Category, Color, Size, Rental, Reservation
from .models import WardrobePackage


def homepage(request):
    """Public homepage (no login required)"""
    featured_items = Inventory.objects.filter(
        available=True,
        quantity__gt=0
    ).order_by('?')[:8]
    
    categories = Category.objects.all()[:4]
    
    # Temporarily comment out the wardrobe packages query
    # wardrobe_packages = WardrobePackage.objects.filter(
    #     status='active'
    # ).order_by('tier')[:3]
    wardrobe_packages = []  # Empty list for now
    
    new_arrivals = Inventory.objects.filter(
        available=True
    ).order_by('-id')[:6]
    
    return render(request, 'customerapp/homepage.html', {
        'featured_items': featured_items,
        'categories': categories,
        'wardrobe_packages': wardrobe_packages,
        'new_arrivals': new_arrivals,
    })

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
                # Restrict staff accounts
                if user.role == 'staff':
                    messages.error(request, "Staff accounts cannot log in here.")
                    return redirect('customerapp:login')  # Redirect back to login page
                
                # Allow customer login
                login(request, user)
                return redirect('customerapp:dashboard')
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
@login_required
def item_detail(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    return render(request, 'customerapp/view_item.html', {'item': item})

@login_required
def rent_item(request, inventory_id):
    inventory_item = get_object_or_404(Inventory, id=inventory_id)

    if request.method == 'POST':
        form = RentalForm(request.POST)
        if form.is_valid():
            rental = form.save(commit=False)
            rental.customer = request.user.customer  # Automatically assigns the logged-in customer
            rental.deposit = inventory_item.deposit  # Set deposit from inventory data
            rental.status = 'Pending'                # Mark rental as 'Pending' by default
            rental.save()
            messages.success(request, 'Your rental request has been submitted successfully.')
            return redirect('customer_dashboard')   # Redirect to the customer's dashboard or desired page
    else:
        form = RentalForm()

    return render(request, 'customerapp/rent_item.html', {'form': form, 'inventory_item': inventory_item})

# Reserve Item View
@login_required
def reserve_item(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)

    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            reservation = form.save(commit=False)
            reservation.item = item
            reservation.customer = request.user.customer
            reservation.save()
            messages.success(request, f"{item.name} has been successfully reserved!")
            return redirect('customerapp:wardrobe')
    else:
        form = ReservationForm()

    return render(request, 'customerapp/reserve_item.html', {'form': form, 'item': item})

def wardrobe_view(request):
    inventory_items = Inventory.objects.filter(available=True)

    # Filtering
    selected_category = request.GET.get('category')
    selected_color = request.GET.get('color')
    selected_size = request.GET.get('size')
    sort = request.GET.get('sort')

    if selected_category:
        inventory_items = inventory_items.filter(category__id=selected_category)
    if selected_color:
        inventory_items = inventory_items.filter(color__id=selected_color)
    if selected_size:
        inventory_items = inventory_items.filter(size__id=selected_size)

    # Sorting
    if sort == "name_asc":
        inventory_items = inventory_items.order_by("name")
    elif sort == "name_desc":
        inventory_items = inventory_items.order_by("-name")
    elif sort == "price_asc":
        inventory_items = inventory_items.order_by("purchase_price")
    elif sort == "price_desc":
        inventory_items = inventory_items.order_by("-purchase_price")

    context = {
        'inventory_items': inventory_items,
        'categories': Category.objects.all(),
        'colors': Color.objects.all(),
        'sizes': Size.objects.all(),
        'selected_category': selected_category,
        'selected_color': selected_color,
        'selected_size': selected_size,
        'sort': sort
    }

    return render(request, 'customerapp/wardrobe.html', context)

def logout_view(request):
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect('saritasapp:sign_in')

@login_required
def product_detail(request, pk):
    """Detailed view for a single inventory item"""
    item = get_object_or_404(Inventory, id=pk)
    
    # Check if item is available for rental
    can_rent = item.available and item.quantity > 0
    
    context = {
        'item': item,
        'can_rent': can_rent,
    }
    return render(request, 'customerapp/product_detail.html', context)


def category_view(request, pk):
    """Show all items in a specific category"""
    category = get_object_or_404(Category, id=pk)
    items = Inventory.objects.filter(
        category=category,
        available=True
    ).order_by('name')
    
    context = {
        'category': category,
        'items': items,
    }
    return render(request, 'customerapp/category.html', context)

def package_detail(request, pk):
    """Detailed view for a wardrobe package"""
    package = get_object_or_404(WardrobePackage, id=pk)
    package_items = package.package_items.all()
    
    context = {
        'package': package,
        'package_items': package_items,
    }
    return render(request, 'customerapp/package_detail.html', context)

