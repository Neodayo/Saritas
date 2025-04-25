# Standard Library
import logging
from datetime import timedelta
from urllib import request
from utils.security import encrypt_id, decrypt_id

# Django Core
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from django.template.loader import render_to_string
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.db import transaction, IntegrityError
from django.views.decorators.http import require_POST
from django.views.generic import (
    ListView, CreateView, UpdateView, DetailView, DeleteView
)
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

# Local Apps
from .forms import (
    CustomerRegistrationForm, RentalForm, ReservationForm,
    CustomerUpdateForm, UserUpdateForm, WardrobePackageRentalForm
)
from saritasapp.forms import CustomizePackageForm, PackageCustomizationForm
from .tasks import send_reservation_notification, notify_staff_about_rental_request
from saritasapp.models import (
    CustomizedWardrobePackage, Inventory, Category, Color, PackageRentalItem, Size,
    Rental, Reservation, Notification, User, WardrobePackage, Customer, WardrobePackageRental
)



@require_POST  # Optional: Only allow POST requests
def clear_welcome_message(request):
    if 'show_welcome_message' in request.session:
        del request.session['show_welcome_message']
    return JsonResponse({'status': 'ok'})


from django.db.models import Prefetch

from django.db.models import Prefetch

def homepage(request):
    """Public homepage (no login required)"""
    # First get the 4 categories we want to feature
    featured_categories = Category.objects.filter(
        name__in=['Wedding Gown', 'Dress', 'Suit', 'Tuxedo']
    )[:4]
    
    # Now get the first available item for each category
    for category in featured_categories:
        category.featured_item = category.items.filter(
            available=True, 
            image__isnull=False
        ).order_by('?').first()  # Get random item
    
    categories = Category.objects.all()
    new_arrivals = Inventory.objects.filter(available=True).order_by('-id')[:6]
    
    return render(request, 'customerapp/homepage.html', {
        'featured_categories': featured_categories,
        'categories': categories,
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

@login_required
def customer_profile(request):
    customer = get_object_or_404(Customer, user=request.user)
    return render(request, 'customerapp/customer_profile.html', {'customer': customer})

@login_required
def edit_customer_profile(request):
    customer = get_object_or_404(Customer, user=request.user)

    if request.method == 'POST':
        user_form = UserUpdateForm(request.POST, instance=request.user)
        customer_form = CustomerUpdateForm(request.POST, request.FILES, instance=customer)

        if user_form.is_valid() and customer_form.is_valid():
            user_form.save()
            customer_form.save()
            messages.success(request, 'Your profile has been updated!')
            return redirect('customerapp:customer_profile')
    else:
        user_form = UserUpdateForm(instance=request.user)
        customer_form = CustomerUpdateForm(instance=customer)

    return render(request, 'customerapp/edit_customer_profile.html', {
        'user_form': user_form,
        'customer_form': customer_form,
    })

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
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.is_read = True
    notification.save()
    
    # Invalidate cache
    cache_key = f'unread_count_{request.user.id}'
    cache.delete(cache_key)
    
    return JsonResponse({'status': 'success'})

@login_required
def mark_all_notifications_as_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    
    # Invalidate cache
    cache_key = f'unread_count_{request.user.id}'
    cache.delete(cache_key)
    
    return redirect('customerapp:notifications')

@login_required
def customer_dashboard(request):
    return render(request, 'customerapp/dashboard.html')

def item_detail(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    return render(request, 'customerapp/view_item.html', {'item': item})

import logging
logger = logging.getLogger(__name__)

@login_required
def rent_item(request, inventory_id):
    inventory = get_object_or_404(Inventory, pk=inventory_id)
    
    if not hasattr(request.user, 'customer_profile'):
        messages.error(request, "Customer profile not found")
        return redirect('home')
    
    if request.method == 'POST':
        form = RentalForm(request.POST, inventory=inventory, customer=request.user.customer_profile)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Refresh inventory to prevent race conditions
                    inventory.refresh_from_db()
                    if inventory.quantity <= 0:
                        messages.error(request, "Item is no longer available")
                        return redirect('inventory_list')
                    
                    rental = form.save()
                    inventory.quantity -= 1
                    inventory.save()
                    rental.inventory_decremented = True
                    rental.save()
                    
                    messages.success(request, "Rental request submitted successfully!")
                    return redirect('my_rentals')
            
            except Exception as e:
                messages.error(request, f"Error processing rental: {str(e)}")
    else:
        initial = {
            'rental_start': timezone.now().date(),
            'rental_end': timezone.now().date() + timedelta(days=7)
        }
        form = RentalForm(initial=initial, inventory=inventory, customer=request.user.customer_profile)
    
    return render(request, 'rent_item.html', {
        'form': form,
        'inventory': inventory
    })

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

logger = logging.getLogger(__name__)

@login_required
@transaction.atomic
def reserve_item(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)

    if not item.available or item.quantity <= 0:
        messages.error(request, "This item is currently not available for reservation.")
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

                # Check if requested quantity is available
                if reservation.quantity > item.quantity:
                    messages.error(request, f"Only {item.quantity} unit(s) of {item.name} are available for reservation.")
                    return redirect('customerapp:item_detail', item_id=item.id)

                # Save the reservation
                reservation.save()

                # Send notification to staff
                send_reservation_notification.delay(reservation.id)

                messages.success(request, f"Your reservation for {item.name} was submitted successfully!")
                return redirect('customerapp:my_reservations')

            except IntegrityError:
                messages.error(request, "A database error occurred. Please try again.")
            except Exception as e:
                logger.exception("Unexpected error during reservation")
                messages.error(request, "An unexpected error occurred. Please contact support.")
        else:
            for field, errors in form.errors.items():
                label = form.fields[field].label if field in form.fields else field
                for error in errors:
                    messages.error(request, f"{label}: {error}")
    else:
        initial_data = {
            'reservation_date': timezone.now().date(),
            'return_date': timezone.now().date() + timedelta(days=1),
            'quantity': 1,
            'reservation_price': item.reservation_price,
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

def collections_view(request):
    # Get all categories with their first available item that has an image
    categories = Category.objects.prefetch_related(
        Prefetch(
            'items',
            queryset=Inventory.objects.filter(available=True, image__isnull=False).order_by('id'),
            to_attr='available_items'
        )
    ).all()

    # Attach the first image to each category
    for category in categories:
        category.first_image = category.available_items[0].image if category.available_items else None

    return render(request, 'customerapp/collections.html', {'categories': categories})

#wardrobe packages
class CustomerPackageListView(ListView):
    model = WardrobePackage
    template_name = 'customerapp/package_list.html'
    context_object_name = 'packages'
    
    def get_queryset(self):
        return WardrobePackage.objects.filter(
            status='fixed',
            package_items__isnull=False
        ).distinct().prefetch_related('package_items__inventory_item')

class CustomerPackageDetailView(DetailView):
    model = WardrobePackage
    template_name = 'customerapp/package_detail.html'
    context_object_name = 'package'
    
    def get_queryset(self):
        return WardrobePackage.objects.filter(
            status='fixed'
        ).prefetch_related(
            'package_items__inventory_item',
            'package_items__inventory_item__item_type'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = self.object
        
        # Group items by type for display
        items_by_type = {}
        for item in package.package_items.all():
            type_name = item.inventory_item.item_type.get_name_display()
            if type_name not in items_by_type:
                items_by_type[type_name] = []
            items_by_type[type_name].append(item)
        
        context['items_by_type'] = items_by_type
        context['total_price'] = package.base_price + package.deposit_price
        return context

class CreateRentalView(LoginRequiredMixin, CreateView):
    model = WardrobePackageRental
    form_class = WardrobePackageRentalForm
    template_name = 'customerapp/rent_package.html'  # Consistent with your other views

    def dispatch(self, request, *args, **kwargs):
        self.package = get_object_or_404(WardrobePackage, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'event_date': timezone.now().date() + timedelta(days=7)
        }
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['package'] = self.package
        context['min_date'] = (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        return context

    def form_valid(self, form):
        try:
            with transaction.atomic():
                rental = form.save(commit=False)
                rental.customer = self.request.user.customer_profile
                rental.package = self.package
                rental.status = 'pending'
                rental.save()
                
                # Send notification (if you have this functionality)
                notify_staff_about_rental_request.delay(rental.id)
                
                messages.success(
                    self.request, 
                    f"Your {self.package.name} package has been reserved for {rental.event_date}!"
                )
                return redirect('customerapp:package_rental_detail', rental_id=rental.pk)
                
        except Exception as e:
            messages.error(self.request, f"Error: {str(e)}")
            return self.form_invalid(form)
    
@login_required
def rent_package(request, package_id):
    package = get_object_or_404(WardrobePackage, pk=package_id)
    
    if request.method == 'POST':
        form = WardrobePackageRentalForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    rental = form.save(commit=False)
                    rental.customer = request.user.customer_profile
                    rental.package = package
                    rental.status = 'pending'
                    
                    # Save will automatically calculate dates and price
                    rental.save()
                    
                    messages.success(request, 
                        f"Your {package.name} package has been reserved for {rental.event_date}!"
                    )
                    return redirect('customerapp:my_package_rentals')
                    
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
    else:
        form = WardrobePackageRentalForm(initial={
            'event_date': timezone.now().date() + timedelta(days=7)  # Default: 1 week from today
        })
    
    return render(request, 'customerapp/rent_package.html', {
        'form': form,
        'package': package,
        'min_date': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    })

@login_required
def package_rental_detail(request, rental_id):
    rental = get_object_or_404(
        WardrobePackageRental, 
        pk=rental_id,
        customer=request.user.customer_profile
    )
    rental_items = rental.package.package_items.select_related(
        'inventory_item',
        'inventory_item__item_type',
        'inventory_item__color',
        'inventory_item__size'
    ).all()
    
    return render(request, 'customerapp/package_rental_detail.html', {
        'rental': rental,
        'rental_items': rental_items
    })

@login_required
def my_package_rentals(request):
    rentals = WardrobePackageRental.objects.filter(
        customer=request.user.customer_profile
    ).order_by('-created_at')
    return render(request, 'customerapp/my_package_rentals.html', {
        'rentals': rentals
    })
def terms(request):
    return render(request, 'customerapp/terms.html')

def privacy(request):
    return render(request, 'customerapp/privacy.html')