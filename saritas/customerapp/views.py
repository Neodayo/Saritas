# Standard Library
import logging
from datetime import timedelta
from urllib import request

# Django Core
from django.db.models import Prefetch
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
    CustomerRegistrationForm, RentalForm,
    CustomerUpdateForm, ReservationForm, UserUpdateForm, WardrobePackageRentalForm
)
from saritasapp.forms import CustomizePackageForm, PackageCustomizationForm
from .tasks import send_reservation_notification, notify_staff_about_rental_request
from saritasapp.models import (
    CustomizedWardrobePackage, Inventory, Category, Color, PackageRentalItem, Size,
    Rental, Reservation, Notification, User, WardrobePackage, Customer, WardrobePackageRental
)
from core.utils.encryption import (
    encrypt_id, 
    decrypt_id,
    get_decrypted_object_or_404
)
from .models import HeroSection, EventSlide
from .forms import EventSlideForm
from .models import FeaturedCollectionsSection

logger = logging.getLogger(__name__)

@require_POST  # Optional: Only allow POST requests
def clear_welcome_message(request):
    if 'show_welcome_message' in request.session:
        del request.session['show_welcome_message']
    return JsonResponse({'status': 'ok'})


def homepage(request):
    """Public homepage (no login required)"""
    try:
        hero_section = HeroSection.objects.filter(is_active=True).latest('updated_at')
    except HeroSection.DoesNotExist:
        hero_section = None

    # Get or create featured collections section
    featured_section, created = FeaturedCollectionsSection.objects.get_or_create(is_active=True)
    if created:
        featured_section.restore_defaults()

    # Add featured item to each category
    for category in featured_section.categories.all():
        category.featured_item = category.items.filter(
            available=True, 
            image__isnull=False
        ).order_by('?').first()

    event_slides = EventSlide.objects.filter(is_active=True).order_by('order')

    return render(request, 'customerapp/homepage.html', {
        'hero_section': hero_section,
        'featured_section': featured_section,
        'all_categories': Category.objects.all(),
        'event_slides': event_slides,
    })


from .utils import send_otp_email  # Import the function
import random

def send_otp_email(user):
    otp = str(random.randint(100000, 999999))
    user.otp_code = otp
    user.otp_created_at = timezone.now()
    user.save()

    subject = 'Verify your email'
    message = f'Hello {user.username},\n\nYour OTP for verifying your email is: {otp}\n\nThank you!'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]

    print("Sending email to:", user.email)  # 👈 Add this to confirm it's triggering
    send_mail(subject, message, from_email, recipient_list)

def register(request):
    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                user = form.save()
                send_otp_email(user)  # Send OTP email after registration
                messages.success(request, "Registration successful! Please check your email to verify.")
                return redirect('customerapp:request_email')
            except IntegrityError as e:
                messages.error(request, "This username or email already exists.")
            except Exception as e:
                messages.error(request, "An error occurred during registration.")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.title()}: {error}")
    else:
        form = CustomerRegistrationForm()
    
    return render(request, 'customerapp/register.html', {'form': form})

def customer_register(request):
    if request.method == "POST":
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            # Save the form data to session
            request.session['temp_customer_data'] = form.cleaned_data
            request.session['verification_email'] = form.cleaned_data['email']
            return redirect('customerapp:request_email')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'customerapp/verify_otp.html', {'form': form})


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
    
    # Add proper URLs to notifications
    for notification in user_notifications:
        if notification.rental:
            notification.url = reverse('customerapp:rental_detail', args=[encrypt_id(notification.rental.id)])
        elif notification.reservation:
            notification.url = reverse('customerapp:reservation_detail', args=[encrypt_id(notification.reservation.id)])
        # Add other notification types as needed
    
    return render(request, 'customerapp/notifications.html', {
        'notifications': user_notifications
    })

@login_required
def mark_notification_as_read(request, encrypted_id):
    notification = get_decrypted_object_or_404(
        Notification, 
        encrypted_id,
        queryset=Notification.objects.filter(user=request.user)
    )
    notification.is_read = True
    notification.save()
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

def item_detail(request, encrypted_id):
    item = get_decrypted_object_or_404(Inventory, encrypted_id)
    return render(request, 'customerapp/view_item.html', {'item': item})


@login_required
def rent_item(request, encrypted_id):
    inventory = get_decrypted_object_or_404(Inventory, encrypted_id)
    
    try:
        customer = request.user.customer_profile
    except Customer.DoesNotExist:
        messages.error(request, "Customer profile not found")
        return redirect('customerapp:dashboard')

    if request.method == 'POST':
        form = RentalForm(
            request.POST,
            inventory=inventory,
            customer=customer
        )
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    rental = form.save()
                    
                    # Check for potential penalty
                    penalty_warning = form.get_penalty_warning()
                    if penalty_warning:
                        messages.warning(request, penalty_warning['message'])
                    
                    messages.success(
                        request,
                        "Rental request submitted successfully! "
                        "Please wait for approval."
                    )
                    return redirect(rental.get_absolute_url())
            except Exception as e:
                logger.error(f"Error creating rental: {str(e)}")
                messages.error(request, "An error occurred while processing your request")
    else:
        form = RentalForm(
            inventory=inventory,
            customer=customer
        )
    
    # Calculate potential penalty for initial display
    penalty_warning = None
    if form.is_bound and not form.errors:
        penalty_warning = form.get_penalty_warning()
    
    return render(request, 'customerapp/rent_item.html', {
        'form': form,
        'item': inventory,
        'is_available': inventory.sizes.filter(quantity__gt=0).exists(),
        'penalty_warning': penalty_warning,
        'rental_price': inventory.rental_price,
        'deposit_price': inventory.deposit_price or 0
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
def rental_detail(request, encrypted_id):
    rental = get_decrypted_object_or_404(
        Rental, 
        encrypted_id,
        queryset=Rental.objects.filter(customer=request.user.customer_profile)
    )
    return render(request, 'customerapp/rental_detail.html', {
        'rental': rental,
        'encrypted_id': rental.encrypted_id  # Pass to template if needed
    })


@login_required
def reserve_item(request, encrypted_id):
    inventory = get_decrypted_object_or_404(Inventory, encrypted_id)
    customer = request.user.customer_profile

    if request.method == "POST":
        form = ReservationForm(
            request.POST, 
            inventory=inventory, 
            customer=customer
        )
        if form.is_valid():
            try:
                reservation = form.save()
                messages.success(
                    request, 
                    "Your reservation has been created successfully!"
                )
                return redirect(
                    'customerapp:reservation_confirmation', 
                    encrypted_id=reservation.encrypted_id
                )
            except ValidationError as e:
                messages.error(request, e.message)
    else:
        form = ReservationForm(inventory=inventory, customer=customer)

    return render(request, 'customerapp/reserve_item.html', {
        'form': form,
        'inventory': inventory
    })

@login_required
def reservation_confirmation(request, encrypted_id):
    try:
        reservation = get_decrypted_object_or_404(Reservation, encrypted_id)
        if reservation.customer != request.user.customer_profile:
            raise Http404("Reservation not found")
            
        return render(request, 'customerapp/reservation_confirmation.html', {
            'reservation': reservation,
            'inventory': reservation.inventory_size.inventory
        })
    except Exception as e:
        messages.error(request, "Error accessing reservation details")
        return redirect('customerapp:dashboard')

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
def product_detail(request, encrypted_id):
    """Detailed view for a single inventory item"""
    item = get_decrypted_object_or_404(Inventory, encrypted_id)
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

def package_detail(request, encrypted_id):
    """Detailed view for a wardrobe package"""
    package = get_decrypted_object_or_404(WardrobePackage, encrypted_id)
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
    
    def get_object(self, queryset=None):
        return get_object_or_404(
            WardrobePackage,
            pk=self.kwargs['id'],
            status='fixed'
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = self.object

        # Group items by type
        items_by_type = {}
        for item in package.package_items.all():
            type_name = item.inventory_item.item_type.get_name_display()
            items_by_type.setdefault(type_name, []).append(item)

        context['items_by_type'] = items_by_type
        context['total_price'] = package.base_price + package.deposit_price
        return context

class CreateRentalView(LoginRequiredMixin, CreateView):
    model = WardrobePackageRental
    form_class = WardrobePackageRentalForm  # Now only asks for event_date
    template_name = 'customerapp/rent_package.html'

    def dispatch(self, request, *args, **kwargs):
        self.package = get_object_or_404(WardrobePackage, pk=kwargs['id'])
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                rental = form.save(commit=False)
                rental.customer = self.request.user.customer_profile
                rental.package = self.package
                rental.status = WardrobePackageRental.PENDING
                rental.save()
                
                # Create rental items for each package item
                for package_item in self.package.package_items.all():
                    PackageRentalItem.objects.create(
                        package_rental=rental,
                        inventory_item=package_item.inventory_item,
                        quantity=package_item.quantity,
                        rental_price=package_item.inventory_item.rental_price
                    )
                
                messages.success(self.request, f"Your {self.package.name} package has been reserved!")
                return redirect('customerapp:package_rental_detail', rental_id=rental.encrypted_id)
                
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
                    rental.save()
                    
                    messages.success(request, 
                        f"Your {package.name} package has been reserved for {rental.event_date}!"
                    )
                    return redirect('customerapp:package_rental_detail', rental_id=rental.encrypted_id)
                    
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
                return redirect('customerapp:package_detail', id=package.id)
    else:
        return redirect('customerapp:package_detail', id=package.id)

@login_required
def package_rental_detail(request, rental_id):
    try:
        decrypted_id = decrypt_id(rental_id)
        rental = get_object_or_404(
            WardrobePackageRental.objects.select_related('package', 'customer'),
            id=decrypted_id,
            customer=request.user.customer_profile
        )
        
        # Group items by type
        items_by_type = {}
        for item in rental.package.package_items.all():
            type_name = item.inventory_item.item_type.get_name_display()
            items_by_type.setdefault(type_name, []).append(item)
            
        return render(request, 'customerapp/package_rental_detail.html', {
            'rental': rental,
            'items_by_type': items_by_type
        })
            
    except (ValueError, TypeError):
        raise Http404("Invalid rental ID")
    
@login_required
def my_package_rentals(request):
    rentals = WardrobePackageRental.objects.filter(
        customer=request.user.customer_profile
    ).order_by('-created_at')
    return render(request, 'customerapp/customer_profile.html', {
        'rentals': rentals
    })


def terms(request):
    return render(request, 'customerapp/terms.html')

def privacy(request):
    return render(request, 'customerapp/privacy.html')

from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, redirect
from .models import HeroSection
from .forms import HeroSectionForm

def is_admin(user):
    return user.is_authenticated and user.is_superuser

@login_required
@user_passes_test(is_admin)
def edit_hero(request):
    try:
        hero = HeroSection.objects.filter(is_active=True).latest('updated_at')
    except HeroSection.DoesNotExist:
        hero = None
    
    if request.method == 'POST':
        form = HeroSectionForm(request.POST, request.FILES, instance=hero)
        if form.is_valid():
            new_hero = form.save(commit=False)
            new_hero.updated_by = request.user
            if hero:  # Deactivate previous hero
                hero.is_active = False
                hero.save()
            new_hero.save()
            return redirect('customerapp:homepage')
    else:
        form = HeroSectionForm(instance=hero)
    
    return render(request, 'customerapp/edit_hero.html', {'form': form})

from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.contrib.auth.decorators import user_passes_test

@require_GET
@login_required
@user_passes_test(lambda u: u.is_superuser)
def get_hero_data(request):
    """API endpoint to get current hero data (for modal)"""
    try:
        hero = HeroSection.objects.filter(is_active=True).latest('updated_at')
        data = {
            'title': hero.title,
            'subtitle': hero.subtitle,
            'background_image_url': hero.background_image.url if hero.background_image else None,
        }
        return JsonResponse({'success': True, 'data': data})
    except HeroSection.DoesNotExist:
        return JsonResponse({
            'success': True,
            'data': {
                'title': 'Elevate Your Special Occasion',
                'subtitle': 'Wedding Gowns, Wedding Entourage, Gowns and Suit for any occasions',
                'background_image_url': None,
            }
        })

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def update_hero(request):
    try:
        current_hero = HeroSection.objects.filter(is_active=True).latest('updated_at')
    except HeroSection.DoesNotExist:
        current_hero = None
    
    if request.POST.get('restore_defaults') == 'true':
        try:
            with transaction.atomic():
                # Deactivate current hero if exists
                if current_hero:
                    current_hero.is_active = False
                    current_hero.save()
                
                # Create new default hero (without any image)
                default_hero = HeroSection(
                    title="Elevate Your Special Occasion",
                    subtitle="Wedding Gowns, Wedding Entourage, Gowns and Suit for any occasions",
                    is_active=True,
                    updated_by=request.user
                )
                default_hero.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Hero section restored to defaults!',
                    'is_default': True
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error restoring defaults: {str(e)}'
            }, status=500)
    
    # Normal form processing
    form = HeroSectionForm(request.POST, request.FILES, instance=current_hero)
    
    if form.is_valid():
        try:
            with transaction.atomic():
                if current_hero:
                    current_hero.is_active = False
                    current_hero.save()
                
                new_hero = form.save(commit=False)
                new_hero.updated_by = request.user
                new_hero.is_active = True
                new_hero.save()
                
                return JsonResponse({
                    'success': True,
                    'message': 'Hero section updated successfully!'
                })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error saving hero section: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'success': False,
        'message': 'Invalid form data',
        'errors': form.errors
    }, status=400)

@login_required
@user_passes_test(lambda u: u.is_superuser)
def manage_event_slides(request):
    if request.method == 'POST':
        form = EventSlideForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            return JsonResponse({'success': True})
        return JsonResponse({'success': False, 'errors': form.errors})
    
    slides = EventSlide.objects.all().order_by('order')
    return render(request, 'customerapp/manage_event_slides.html', {
        'slides': slides,
        'form': EventSlideForm()
    })
@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def delete_event_slide(request, slide_id):
    try:
        slide = EventSlide.objects.get(id=slide_id)
        slide.delete()
        return JsonResponse({'success': True})
    except EventSlide.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Slide not found'}, status=404)
    

@require_POST
@login_required
@user_passes_test(lambda u: u.is_superuser)
def update_featured_collections(request):
    try:
        featured_section = FeaturedCollectionsSection.objects.filter(is_active=True).first()
        
        if request.POST.get('restore_defaults'):
            featured_section.restore_defaults()
        else:
            category_ids = request.POST.getlist('categories')
            featured_section.categories.set(Category.objects.filter(id__in=category_ids))
            featured_section.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
    

    # views.py
from django.shortcuts import get_object_or_404
from django.http import Http404
from core.utils.encryption import decrypt_id

def package_detail(request, package_id):
    try:
        # Try to decrypt if it's an encrypted ID
        try:
            decrypted_id = decrypt_id(package_id)
            package = get_object_or_404(WardrobePackage, pk=decrypted_id)
        except (ValueError, ValidationError):
            # Fall back to numeric ID if decryption fails
            if package_id.isdigit():
                package = get_object_or_404(WardrobePackage, pk=int(package_id))
            else:
                raise Http404("Invalid package ID format")
                
    except Exception as e:
        raise Http404("Package not found")
    
    return render(request, 'saritasapp/package_detail.html', {'package': package})