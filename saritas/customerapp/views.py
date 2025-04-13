from datetime import timedelta
from urllib import request
from django.conf import settings
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
from saritasapp.models import Inventory, Category, Color, Size, Rental, Reservation, Notification, User, WardrobePackage
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from django.core.mail import send_mail


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
                user = form.save()
                messages.success(request, "Registration successful! Please sign in.")
                return redirect('saritasapp:sign_in')  # Using namespace
            except IntegrityError as e:
                messages.error(request, "This username or email already exists.")
            except Exception as e:
                messages.error(request, "An error occurred during registration.")
        else:
            # Show specific field errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        form = CustomerRegistrationForm()
    
    return render(request, 'customerapp/register.html', {'form': form})

def notifications(request):
    if request.user.is_authenticated:
        return {
            'unread_count': Notification.objects.filter(user=request.user, is_read=False).count()
        }
    return {}

@login_required
def notifications(request):
    user_notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    unread_count = user_notifications.filter(is_read=False).count()
    
    return render(request, 'customerapp/notifications.html', {
        'notifications': user_notifications,
        'unread_count': unread_count
    })

@login_required
def mark_notification_as_read(request, notification_id):
    notification = Notification.objects.filter(id=notification_id, user=request.user).first()
    if notification:
        notification.is_read = True
        notification.save()
    return redirect('customerapp:notifications')

@login_required
def mark_all_notifications_as_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('customerapp:notifications')

@login_required
def customer_dashboard(request):
    return render(request, 'customerapp/dashboard.html')

def item_detail(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    return render(request, 'customerapp/view_item.html', {'item': item})

@login_required
def rent_item(request, inventory_id):
    try:
        with transaction.atomic():
            # Use select_for_update() to lock the inventory row
            item = Inventory.objects.select_for_update().get(pk=inventory_id)
            
            if not item.available or item.quantity <= 0:
                messages.error(request, 'Item no longer available')
                return redirect('customerapp:wardrobe')
            
            rental = Rental(
                inventory=item,
                customer=request.user.customer_profile,
                status='Pending',
                deposit=item.deposit_price or 0.00,
                rental_start=form.cleaned_data['rental_start'],
                rental_end=form.cleaned_data['rental_end'],
                notes=form.cleaned_data.get('notes', '')
            )
            rental.save()
            
            # Decrement inventory
            item.quantity -= 1
            item.save()
            
            # Async email task
            from .tasks import notify_staff_about_rental_request
            notify_staff_about_rental_request.delay(rental.id)
            
            messages.success(request, 'Rental request submitted!')
            return redirect('customerapp:my_rentals')
            
    except Exception as e:
        messages.error(request, f'Error: {str(e)}')
        return redirect('customerapp:wardrobe')

@login_required
def rental_list(request):
    rentals = Rental.objects.filter(customer=request.user.customer_profile)
    return render(request, 'customerapp/rental_list.html', {'rentals': rentals})

@login_required
def my_rentals(request):
    rentals = Rental.objects.filter(
        customer=request.user.customer_profile
    ).order_by('-created_at')
    return render(request, 'customerapp/my_rentals.html', {'rentals': rentals})

@login_required
def rental_detail(request, rental_id):
    rental = get_object_or_404(
        Rental, 
        id=rental_id, 
        customer=request.user.customer_profile
    )
    return render(request, 'customerapp/rental_detail.html', {'rental': rental})

@login_required
@transaction.atomic
def reserve_item(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    
    if not item.available or item.quantity <= 0:
        messages.error(request, "This item is currently not available for reservation")
        return redirect('customerapp:item_detail', item_id=item.id)
    
    if request.method == 'POST':
        form = ReservationForm(request.POST, item=item, user=request.user)
        if form.is_valid():
            try:
                reservation = form.save(commit=False)
                reservation.item = item
                reservation.customer = request.user.customer_profile
                reservation.created_by = request.user
                reservation.status = 'pending'
                
                # Save the reservation
                reservation.save()
                
                # Send notifications
                from .tasks import send_reservation_notification
                send_reservation_notification.delay(reservation.id)
                
                messages.success(request, f"Your reservation for {item.name} was submitted successfully!")
                return redirect('customerapp:my_reservations')
                
            except IntegrityError as e:
                messages.error(request, "A database error occurred. Please try again.")
            except Exception as e:
                messages.error(request, f"Reservation failed: {str(e)}")
        else:
            # Collect all form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        # Initial form setup
        initial_data = {
            'reservation_date': timezone.now().date(),
            'return_date': timezone.now().date() + timedelta(days=1),
            'quantity': 1
        }
        form = ReservationForm(initial=initial_data, item=item, user=request.user)

    context = {
        'form': form,
        'item': item,
        'available_quantity': item.quantity
    }
    return render(request, 'customerapp/reserve_item.html', context)

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

def notify_staff_about_rental_request(rental):
    staff_users = User.objects.filter(is_staff=True)
    subject = f"New Rental Request: {rental.inventory.name} (ID: #{rental.id})"
    
    admin_url = request.build_absolute_uri(
        reverse('admin:customerapp_rental_change', args=[rental.id])
    )
    
    context = {
        'rental': rental,
        'admin_url': admin_url,
        'site_name': 'Your Site Name'  # Or use settings.SITE_NAME
    }
    
    message = render_to_string(
        'customerapp/emails/new_rental_request.txt',
        context
    )
    
    html_message = render_to_string(
        'customerapp/emails/new_rental_request.html',
        context
    )
    
    recipient_list = [user.email for user in staff_users if user.email]
    
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        recipient_list,
        html_message=html_message
    )