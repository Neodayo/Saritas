from datetime import timedelta
from django.utils import timezone
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
from django.http import JsonResponse
from django.views.decorators.http import require_POST

@require_POST  # Optional: Only allow POST requests
def clear_welcome_message(request):
    if 'show_welcome_message' in request.session:
        del request.session['show_welcome_message']
    return JsonResponse({'status': 'ok'})


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
                return redirect('saritasapp/login')
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


@login_required
def customer_dashboard(request):
    return render(request, 'customerapp/dashboard.html')

def item_detail(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    return render(request, 'customerapp/view_item.html', {'item': item})

@login_required
def rent_item(request, inventory_id):
    # Verify customer profile exists
    if not hasattr(request.user, 'customer_profile'):
        messages.error(request, 'Please complete your customer profile')
        return redirect('customerapp:profile')

    item = get_object_or_404(Inventory, id=inventory_id)
    
    if not item.available or item.quantity <= 0:
        messages.error(request, 'This item is not currently available for rent')
        return redirect('customerapp:wardrobe')

    if request.method == 'POST':
        form = RentalForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    rental = form.save(commit=False)
                    rental.inventory = item
                    rental.customer = request.user.customer_profile
                    rental.status = 'Pending'
                    rental.save()
                    
                    messages.success(request, 'Your rental request has been submitted!')
                    return redirect('customerapp:homepage')
            except Exception as e:
                messages.error(request, f'Error processing rental: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below')
    else:
        form = RentalForm(initial={
            'rental_start': timezone.now().date(),
            'rental_end': (timezone.now() + timedelta(days=7)).date()
        })
    
    return render(request, 'customerapp/rent_item.html', {
        'form': form,
        'item': item
    })

@login_required
@transaction.atomic
def reserve_item(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    
    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            try:
                reservation = form.save(commit=False)
                # Assign required fields before saving
                reservation.item = item
                reservation.customer = request.user.customer
                reservation.status = 'pending'
                reservation.save()
                
                messages.success(request, f"{item.name} reserved successfully!")
                return redirect('customerapp:wardrobe')
                
            except Exception as e:
                messages.error(request, f"Reservation failed: {str(e)}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = ReservationForm(initial={
            'reservation_date': timezone.now().date(),
            'return_date': timezone.now().date() + timedelta(days=1),
            'quantity': 1
        })

    return render(request, 'customerapp/reserve_item.html', {
        'form': form,
        'item': item
    })

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

def about_us(request):
    return render(request, 'customerapp/about_us.html')
