# Standard library imports
import base64
from calendar import month_name
from datetime import date, datetime, timedelta
from decimal import Decimal
import logging

# Django core imports
from django import forms
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractWeek, ExtractYear, TruncMonth, Coalesce
from django.http import Http404, HttpResponse, HttpResponseBadRequest, HttpResponseNotFound, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView, TemplateView

# Third-party imports
import plotly.graph_objects as go
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Local app imports
from .forms import (
    AddPackageItemForm, AdminSignUpForm, BranchForm, BulkPackageItemForm, CategoryForm, ColorForm, EditProfileForm, EditStaffForm, EventForm,
    InventoryForm, InventorySizeFormSet, LoginForm, MaterialForm, PackageItemForm, PackageReturnForm, SizeForm, StaffRentalApprovalForm, StaffSignUpForm, StyleForm, TagForm,
    WardrobePackageForm, WardrobePackageItemForm,
    PackageCustomizationForm, CustomizePackageForm
)
from .models import (
    Branch, Category, Color, Customer, Event, Inventory, InventorySize, ItemType, Material, Notification, PackageCustomization,
    Receipt, Rental, Reservation, Size, Style, Tag, User, Venue,
    WardrobePackage, CustomizedWardrobePackage, WardrobePackageItem, WardrobePackageRental
)
# In your views.py
from .tasks import send_notification
from customerapp.tasks import notify_staff_about_rental_request
from django.core.exceptions import BadRequest
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.utils.timezone import now
from core.utils.encryption import (
    get_decrypted_object_or_404,
    encrypt_id,
    decrypt_id
)

logger = logging.getLogger(__name__)


def manage_branches(request):
    # Handle edit request
    edit_id = request.GET.get('edit')
    if edit_id:
        branch = get_object_or_404(Branch, id=edit_id)
        form = BranchForm(instance=branch)
    else:
        form = BranchForm()

    # Handle form submission
    if request.method == 'POST':
        branch_id = request.POST.get('branch_id')
        if branch_id:
            branch = get_object_or_404(Branch, id=branch_id)
            form = BranchForm(request.POST, instance=branch)
            action = 'updated'
        else:
            form = BranchForm(request.POST)
            action = 'added'
            
        if form.is_valid():
            form.save()
            messages.success(request, f'Branch {action} successfully!')
            return redirect('saritasapp:manage_branches')
    
    # Get all branches
    branches = Branch.objects.all().order_by('branch_name')
    
    return render(request, 'saritasapp/manage_branches.html', {
        'form': form,
        'branches': branches
    })

def delete_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id)
    if request.method == 'POST':
        branch.delete()
        messages.success(request, 'Branch deleted successfully!')
        return redirect('saritasapp:manage_branches')
    
    return render(request, 'saritasapp/confirm_delete_branch.html', {
        'branch': branch
    })

    
# views.py
@staff_member_required
def add_inventory(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # 1. First save the Inventory instance alone
                    inventory = form.save(commit=False)
                    if hasattr(request.user, 'staff_profile'):
                        inventory.created_by = request.user
                    inventory.save()  # This creates the PK
                    form.save_m2m()  # Save many-to-many relationships
                    
                    # 2. Now handle sizes with the saved inventory instance
                    size_formset = InventorySizeFormSet(
                        request.POST,
                        instance=inventory,
                        queryset=InventorySize.objects.none()
                    )
                    
                    if size_formset.is_valid():
                        sizes = size_formset.save(commit=False)
                        for size in sizes:
                            size.inventory = inventory  # Ensure relationship is set
                            size.save()
                        
                        # Update inventory availability
                        inventory.available = inventory.sizes.filter(quantity__gt=0).exists()
                        inventory.save(update_fields=['available'])
                        
                        messages.success(request, f"Successfully added {inventory.name}")
                        return redirect('saritasapp:inventory_list')
                    else:
                        # Handle formset errors
                        for form in size_formset:
                            for field, errors in form.errors.items():
                                for error in errors:
                                    messages.error(request, f"Size {form.cleaned_data.get('size', '')}: {error}")
                        for error in size_formset.non_form_errors():
                            messages.error(request, error)
                        
                        # Rollback if size data is invalid
                        raise ValidationError("Invalid size data")
            except Exception as e:
                messages.error(request, f"Error saving item: {str(e)}")
                # Re-initialize forms for correction
                size_formset = InventorySizeFormSet(queryset=InventorySize.objects.none())
        else:
            # Form is invalid, initialize empty formset
            size_formset = InventorySizeFormSet(queryset=InventorySize.objects.none())
            # Handle form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    else:
        # GET request - initialize empty forms
        form = InventoryForm(user=request.user)
        size_formset = InventorySizeFormSet(queryset=InventorySize.objects.none())
    
    context = {
        'form': form,
        'size_formset': size_formset,
        'user': request.user,
        'categories': Category.objects.all().order_by('name'),
        'colors': Color.objects.all().order_by('name'),
        'sizes': Size.objects.all().order_by('name'),
        'item_types': ItemType.objects.all().order_by('name'),
        'styles': Style.objects.all().order_by('name'),
        'materials': Material.objects.all().order_by('name'),
        'tags': Tag.objects.all().order_by('name'),
        'branches': Branch.objects.all().order_by('branch_name')
    }
    return render(request, 'saritasapp/add_item.html', context)

@staff_member_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category "{form.cleaned_data["name"]}" was added successfully!')
            if request.GET.get('next'):
                return redirect(request.GET.get('next'))
            return redirect('saritasapp:add_inventory')
    else:
        form = CategoryForm()

    return render(request, 'saritasapp/add_category.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })

@staff_member_required
def add_color(request):
    if request.method == 'POST':
        form = ColorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('saritasapp:add_inventory')
    else:
        form = ColorForm()
    return render(request, 'saritasapp/add_color.html', {'form': form})

@staff_member_required
def add_size(request):
    if request.method == 'POST':
        form = SizeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('saritasapp:add_inventory')
    else:
        form = SizeForm()
    return render(request, 'saritasapp/add_size.html', {'form': form})

@staff_member_required
def add_material(request):
    if request.method == 'POST':
        form = MaterialForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Material "{form.cleaned_data["name"]}" was added successfully!')
            if request.GET.get('next'):
                return redirect(request.GET.get('next'))
            return redirect('saritasapp:add_inventory')
    else:
        form = MaterialForm()

    return render(request, 'saritasapp/add_material.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })

@staff_member_required
def add_style(request):
    if request.method == 'POST':
        form = StyleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Style "{form.cleaned_data["name"]}" was added successfully!')
            if request.GET.get('next'):
                return redirect(request.GET.get('next'))
            return redirect('saritasapp:add_inventory')
    else:
        form = StyleForm()

    return render(request, 'saritasapp/add_style.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })

@staff_member_required
def add_tag(request):
    if request.method == 'POST':
        form = TagForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'Tag "{form.cleaned_data["name"]}" was added successfully!')
            if request.GET.get('next'):
                return redirect(request.GET.get('next'))
            return redirect('saritasapp:add_inventory')
    else:
        form = TagForm()

    return render(request, 'saritasapp/add_tag.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })

@staff_member_required
def view_item(request, encrypted_id):
    try:
        item = get_decrypted_object_or_404(Inventory, encrypted_id)
        return render(request, 'saritasapp/view_item.html', {'item': item})
    except BadRequest:
        return HttpResponseBadRequest("Invalid item ID")
    except Http404:
        return HttpResponseNotFound("Item not found")

@staff_member_required
def edit_inventory(request, encrypted_id):
    item = get_decrypted_object_or_404(Inventory, encrypted_id)
    
    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES, instance=item, user=request.user)
        size_formset = InventorySizeFormSet(request.POST, instance=item)
        
        if form.is_valid() and size_formset.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                    size_formset.save()
                    messages.success(request, 'Inventory item updated successfully!')
                    return redirect('saritasapp:inventory_list')
            except Exception as e:
                messages.error(request, f"Error updating item: {str(e)}")
    else:
        form = InventoryForm(instance=item, user=request.user)
        size_formset = InventorySizeFormSet(instance=item)
    
    return render(request, 'saritasapp/edit_inventory.html', {
        'form': form,
        'size_formset': size_formset,
        'categories': Category.objects.all(),
        'colors': Color.objects.all(),
        'sizes': Size.objects.all(),
        'branches': Branch.objects.all(),
        'item': item
    })


@staff_member_required
def delete_inventory(request, encrypted_id):
    item = get_decrypted_object_or_404(Inventory, encrypted_id)
    
    if request.method == 'POST':
        item.delete()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/confirm_delete.html', {'item': item})

@staff_member_required
def view_item(request, encrypted_id):
    try:
        item = get_decrypted_object_or_404(Inventory, encrypted_id)
        sizes = item.sizes.all().order_by('size__name')
        
        # Calculate total quantity by summing all sizes
        total_quantity = sizes.aggregate(total=Sum('quantity'))['total'] or 0
        
        return render(request, 'saritasapp/view_item.html', {
            'item': item,
            'sizes': sizes,
            'total_quantity': total_quantity  # Pass the calculated total
        })
    except BadRequest:
        return HttpResponseBadRequest("Invalid item ID")
    except Http404:
        return HttpResponseNotFound("Item not found")

@staff_member_required
def inventory_view(request):
    # Get all filter options
    categories = Category.objects.all()
    colors = Color.objects.all()
    materials = Material.objects.all()
    tags = Tag.objects.all()
    styles = Style.objects.all()
    item_types = ItemType.objects.all()
    sizes = Size.objects.all()
    branches = Branch.objects.all()

    # Get selected filters from request
    selected_category = request.GET.get('category', '')
    selected_color = request.GET.get('color', '')
    selected_material = request.GET.get('material', '')
    selected_tag = request.GET.get('tag', '')
    selected_style = request.GET.get('style', '')
    selected_item_type = request.GET.get('item_type', '')
    selected_size = request.GET.get('size', '')
    selected_branch = request.GET.get('branch', '')
    selected_available = request.GET.get('available', '')
    sort = request.GET.get('sort', '')

    # Start with all inventory items
    inventory_items = Inventory.objects.all().prefetch_related('sizes')

    # Apply filters
    if selected_category:
        inventory_items = inventory_items.filter(category_id=selected_category)
    if selected_color:
        inventory_items = inventory_items.filter(color_id=selected_color)
    if selected_material:
        inventory_items = inventory_items.filter(material_id=selected_material)
    if selected_style:
        inventory_items = inventory_items.filter(style_id=selected_style)
    if selected_item_type:
        inventory_items = inventory_items.filter(item_type_id=selected_item_type)
    if selected_tag:
        inventory_items = inventory_items.filter(tags__id=selected_tag)
    if selected_size:
        inventory_items = inventory_items.filter(sizes__size_id=selected_size)
    if selected_branch:
        inventory_items = inventory_items.filter(branch_id=selected_branch)
    if selected_available:
        inventory_items = inventory_items.filter(available=selected_available)

    # Annotate with total quantity (fixed version)
    inventory_items = inventory_items.annotate(
        item_quantity=Coalesce(Sum('sizes__quantity'), 0)
    ).distinct()

    # Apply sorting
    if sort == 'name_asc':
        inventory_items = inventory_items.order_by('name')
    elif sort == 'name_desc':
        inventory_items = inventory_items.order_by('-name')
    elif sort == 'price_asc':
        inventory_items = inventory_items.order_by('rental_price')
    elif sort == 'price_desc':
        inventory_items = inventory_items.order_by('-rental_price')
    elif sort == 'quantity_asc':
        inventory_items = inventory_items.order_by('item_quantity')
    elif sort == 'quantity_desc':
        inventory_items = inventory_items.order_by('-item_quantity')

    # Pagination
    paginator = Paginator(inventory_items, 25)
    page_number = request.GET.get('page')
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    return render(request, 'saritasapp/inventory.html', {
        'categories': categories,
        'colors': colors,
        'materials': materials,
        'tags': tags,
        'styles': styles,
        'item_types': item_types,
        'sizes': sizes,
        'branches': branches,
        'page_obj': page_obj,
        'selected_category': selected_category,
        'selected_color': selected_color,
        'selected_material': selected_material,
        'selected_tag': selected_tag,
        'selected_style': selected_style,
        'selected_item_type': selected_item_type,
        'selected_size': selected_size,
        'selected_branch': selected_branch,
        'selected_available': selected_available,
        'sort': sort
    })


@staff_member_required
def rental_tracker(request):
    status_filter = request.GET.get('status')
    today = timezone.now().date()

    rentals = Rental.objects.select_related(
        'inventory_size__inventory',
        'inventory_size__inventory__category',
        'inventory_size__size',
        'customer__user',
        'staff'
    ).order_by('-created_at')

    # Status filtering
    if status_filter == 'Renting':
        rentals = rentals.filter(
            status=Rental.RENTED,
            rental_start__lte=today,
            rental_end__gte=today
        )
    elif status_filter == 'Overdue':
        # First mark overdue rentals
        overdue_rentals = rentals.filter(
            status=Rental.RENTED,
            rental_end__lt=today
        )
        overdue_rentals.update(status=Rental.OVERDUE)
        
        # Then filter for display
        rentals = rentals.filter(status=Rental.OVERDUE)
    elif status_filter == 'Returned':
        rentals = rentals.filter(status=Rental.RETURNED)
    elif status_filter:
        rentals = rentals.filter(status=status_filter)

    return render(request, 'saritasapp/rental_tracker.html', {
        'rentals': rentals,
        'today': today,
        'status_choices': [
            ('Renting', 'Renting'),
            ('Overdue', 'Overdue'),
            ('Returned', 'Returned')
        ]
    })

@staff_member_required
def rental_approvals(request):
    try:
        # Get pending rentals with proper relationships
        pending_rentals = Rental.objects.filter(
            status=Rental.PENDING
        ).select_related(
            'customer__user',
            'inventory_size__inventory',
            'inventory_size__size',
            'staff'
        ).order_by('-created_at')

        # Filter rentals with valid encryption
        valid_rentals = []
        for rental in pending_rentals:
            if rental.encrypted_id:
                valid_rentals.append(rental)
            else:
                logger.error(f"Rental ID {rental.id} - encryption failed")

        # Get approval statistics
        stats = {
            'pending': pending_rentals.count(),
            'approved': Rental.objects.filter(status=Rental.APPROVED).count(),
            'rejected': Rental.objects.filter(status=Rental.REJECTED).count(),
        }

        return render(request, 'saritasapp/rental_approvals.html', {
            'pending_rentals': valid_rentals,
            'stats': stats,
        })

    except Exception as e:
        logger.error(f"Error in rental_approvals: {str(e)}", exc_info=True)
        messages.error(request, "Failed to load rental approvals. Please try again later.")
        return redirect('saritasapp:dashboard')

@staff_member_required
def approve_or_reject_rental(request, encrypted_id, action):
    try:
        rental = get_decrypted_object_or_404(Rental, encrypted_id)
        
        if action not in ('approve', 'reject'):
            raise BadRequest("Invalid action")

        if request.method == 'POST':
            with transaction.atomic():
                if action == 'approve':
                    rental.approve(request.user)
                    action_message = 'approved'
                    
                    Notification.objects.create(
                        user=rental.customer.user,
                        notification_type='rental_approved',
                        rental=rental,
                        message=f"Your rental for {rental.inventory_size.inventory.name} has been approved!",
                        is_read=False
                    )
                else:
                    reason = request.POST.get('rejection_reason', 'No reason provided')
                    rental.reject(request.user, reason)
                    action_message = 'rejected'

                messages.success(request, f"Rental successfully {action_message}!")
                return redirect('saritasapp:rental_approvals')

        # For GET requests - show confirmation form
        if action == 'approve':
            return render(request, 'saritasapp/confirm_approve.html', {
                'rental': rental,
                'encrypted_id': encrypted_id
            })
        elif action == 'reject':
            return render(request, 'saritasapp/confirm_reject.html', {
                'rental': rental,
                'encrypted_id': encrypted_id
            })

    except Exception as e:
        messages.error(request, f"Error processing request: {str(e)}")
        logger.error(f"Error {action} rental {encrypted_id}: {str(e)}")
    
    return redirect('saritasapp:rental_approvals')

@staff_member_required
def view_reservations(request):
    status = request.GET.get('status', 'all')
    
    # Updated query to match new model structure
    reservations = Reservation.objects.select_related(
        'inventory_size__inventory',  # Access item through inventory_size
        'customer__user',             # Access user through customer
        'staff'                       # Previously approved_by
    ).order_by('-reservation_date')   # Changed from created_at to reservation_date
    
    if status != 'all':
        reservations = reservations.filter(status=status)
    
    # Map old status names to new ones if needed
    status_mapping = {
        'pending': 'pending',
        'approved': 'paid',
        'rejected': 'cancelled',
        'completed': 'fulfilled'
    }
    
    # If using different status names in the new model
    if status in status_mapping:
        reservations = reservations.filter(status=status_mapping[status])
    
    context = {
        'reservations': reservations,
        'status': status,
        'status_choices': [
            ('pending', 'Pending'),
            ('paid', 'Approved'),      # Mapping paid to approved for UI
            ('fulfilled', 'Completed'),
            ('cancelled', 'Rejected'),
            ('expired', 'Expired')
        ],
    }
    return render(request, 'saritasapp/view_reservation.html', context)

@staff_member_required
def update_reservation(request, encrypted_id, action):
    reservation = get_decrypted_object_or_404(Reservation, encrypted_id)

    if request.method == 'POST':
        if action == 'approve':
            try:
                reservation.approve(request.user)
                messages.success(request, f"Reservation #{reservation.id} approved")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error approving reservation: {str(e)}")
                messages.error(request, "Error approving reservation")
                
        elif action == 'reject':
            try:
                reservation.status = 'cancelled'
                reservation.staff = request.user
                reservation.save()
                messages.success(request, f"Reservation #{reservation.id} rejected")
            except Exception as e:
                messages.error(request, "Error rejecting reservation")
        
        # Add this new handler for complete action
        elif action == 'complete':
            try:
                rental = reservation.convert_to_rental(request.user)
                messages.success(request, f"Reservation #{reservation.id} converted to rental #{rental.id}")
            except ValidationError as e:
                messages.error(request, str(e))
            except Exception as e:
                logger.error(f"Error completing reservation: {str(e)}")
                messages.error(request, "Error completing reservation")
                
        return redirect('saritasapp:view_reservations')
    
    return redirect('saritasapp:view_reservations')


@staff_member_required
def rental_detail(request, encrypted_id):
    try:
        rental = get_decrypted_object_or_404(
            Rental,
            encrypted_id,
            queryset=Rental.objects.select_related(
                'customer__user',
                'inventory_size__inventory',
                'inventory_size__size',
                'staff'
            )
        )
        
        return render(request, 'saritasapp/rental_detail.html', {
            'rental': rental,
        })
        
    except Exception as e:
        logger.error(f"Error viewing rental {encrypted_id}: {str(e)}")
        messages.error(request, "Error loading rental details")
        return redirect('saritasapp:rental_approvals')

@staff_member_required
def view_customer(request, encrypted_id):
    """
    View customer details with rental history
    """
    try:
        # Get customer with proper error handling
        customer = get_decrypted_object_or_404(
            Customer,
            encrypted_id,
            queryset=Customer.objects.select_related('user', 'user__branch')
        )
        
        today = now().date()
        
        # Get rentals with proper related fields
        rentals = Rental.objects.filter(customer=customer).select_related(
            'inventory_size__inventory',
            'inventory_size__inventory__category',
            'inventory_size__inventory__item_type',
            'inventory_size__size'
        ).order_by('-rental_start')

        # Update overdue statuses
        overdue_count = Rental.objects.filter(
            customer=customer,
            status=Rental.RENTED,
            rental_end__lt=today
        ).update(status=Rental.OVERDUE)

        if overdue_count > 0:
            logger.info(f"Marked {overdue_count} rentals as overdue for customer {customer.id}")

        return render(request, 'saritasapp/view_customer.html', {
            'customer': customer,
            'rentals': rentals,
            'today': today,
        })

    except Http404:
        logger.warning(f"Customer not found with ID: {encrypted_id}")
        raise
    except Exception as e:
        logger.error(f"Error viewing customer {encrypted_id}: {str(e)}", exc_info=True)
        messages.error(request, "Error loading customer details")
        return redirect('saritasapp:customer_list')


@staff_member_required
def return_rental(request, encrypted_id):
    try:
        rental_id = decrypt_id(encrypted_id)
        rental = Rental.objects.select_related(
            'inventory_size__inventory',
            'customer__user'
        ).get(pk=rental_id)
    except (Rental.DoesNotExist, ValueError):
        messages.error(request, "Rental not found")
        return redirect('saritasapp:rental_tracker')

    # Check if rental can be returned
    if rental.status not in [Rental.RENTED, Rental.OVERDUE]:
        messages.error(request, f"Cannot return item with status: {rental.get_status_display()}")
        return redirect('saritasapp:rental_tracker')

    if request.method == 'POST':
        condition = request.POST.get('condition')
        notes = request.POST.get('notes', '')
        
        try:
            with transaction.atomic():
                rental.mark_as_returned(
                    condition=condition,
                    notes=notes,
                    processed_by=request.user
                )
                
                messages.success(request, f"Item {rental.inventory_size.inventory.name} has been returned successfully.")
                return redirect('saritasapp:rental_tracker')
                
        except Exception as e:
            messages.error(request, f"Error returning item: {str(e)}")
            logger.error(f"Error returning rental {rental_id}: {str(e)}")
            # Stay on the same page to show errors
            return redirect('saritasapp:return_rental', encrypted_id=encrypted_id)

    # GET request handling
    potential_fees = {
        'is_overdue': rental.is_overdue,
        'overdue_fee': rental.calculated_penalty if rental.is_overdue else 0,
        'poor_condition_fee': rental.inventory_size.inventory.deposit_price * Decimal('0.5'),
        'fair_condition_fee': rental.inventory_size.inventory.deposit_price * Decimal('0.2'),
        'deposit_amount': rental.inventory_size.inventory.deposit_price
    }

    context = {
        'rental': rental,
        'item': rental.inventory_size.inventory,
        'size': rental.inventory_size.size,
        'customer': rental.customer,
        'potential_fees': potential_fees
    }
    return render(request, 'saritasapp/return_rental.html', context)

# views.py
@staff_member_required
def customer_list(request):
    query = request.GET.get('q', '')
    status_filter = request.GET.get('status', 'all')
    page = request.GET.get('page', 1)

    # Base queryset - only customers (users with role='customer')
    customers = Customer.objects.filter(user__role='customer')

    # Annotate with active rental count
    customers = customers.annotate(
        active_rentals=Count(
            'rentals',
            filter=Q(rentals__status="Rented") & ~Q(rentals__status="Returned")
        )
    ).select_related('user').order_by('-created_at')

    # Apply search filter
    if query:
        customers = customers.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(phone__icontains=query)
        )

    # Apply status filter
    if status_filter == 'active':
        customers = customers.filter(active_rentals__gt=0)
    elif status_filter == 'past':
        customers = customers.filter(active_rentals=0)

    # Pagination
    paginator = Paginator(customers, 25)
    try:
        customers = paginator.page(page)
    except PageNotAnInteger:
        customers = paginator.page(1)
    except EmptyPage:
        customers = paginator.page(paginator.num_pages)

    return render(request, 'saritasapp/customer_list.html', {
        'customers': customers,
        'query': query,
        'status_filter': status_filter
    })

@staff_member_required
def manage_staff(request):
    staff_list = User.objects.filter(
        role='staff'
    ).select_related('staff_profile').order_by('last_name', 'first_name')
    
    context = {
        'staff_list': staff_list,
        'user': request.user
    }
    return render(request, 'saritasapp/manage_staff.html', context)

@staff_member_required
def edit_staff(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, role='staff')
    if request.method == 'POST':
        form = EditStaffForm(request.POST, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(request, 'Staff details updated successfully.')
            return redirect('saritasapp:manage_staff')
    else:
        form = EditStaffForm(instance=staff)
    return render(request, 'saritasapp/edit_staff.html', {'form': form, 'staff': staff})

@staff_member_required
def delete_staff(request, staff_id):
    staff = get_object_or_404(User, id=staff_id, role='staff')
    if request.method == 'POST':
        staff.delete()
        messages.success(request, 'Staff member deleted successfully.')
        return redirect('saritasapp:manage_staff')
    return render(request, 'saritasapp/confirm_staff_delete.html', {'staff': staff})



@staff_member_required
def made_to_order(request):
    return render(request, 'saritasapp/made_to_order.html')

from django.db import IntegrityError, transaction
# --- Staff Signup ---
@login_required
@user_passes_test(lambda u: u.is_superuser)
def staff_sign_up(request):
    if request.method == 'POST':
        form = StaffSignUpForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, "Staff account created successfully!")
                return redirect('saritasapp:dashboard')
            except IntegrityError as e:
                messages.error(request, f"Database error: {str(e)}")
            except Exception as e:
                messages.error(request, f"Error creating account: {str(e)}")
        else:
            # Show detailed form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        form = StaffSignUpForm()

    return render(request, 'saritasapp/signup.html', {'form': form})



# --- Admin Signup ---
@login_required
@user_passes_test(lambda u: u.is_superuser)
def admin_signup(request):
    if request.method == 'POST':
        form = AdminSignUpForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Admin account created successfully!")
            return redirect('saritasapp:dashboard')
    else:
        form = AdminSignUpForm()

    return render(request, 'saritasapp/admin_signup.html', {'form': form})


# --- Login View ---
def sign_in(request):
    # Redirect already authenticated users
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('saritasapp:dashboard')
        return redirect('customerapp:homepage')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            request.session['show_welcome_message'] = True
            request.session['welcome_username'] = user.get_full_name() or user.username
            
            # Handle next parameter if exists
            next_url = request.POST.get('next', '')
            if next_url:
                return redirect(next_url)
                
            # Role-based redirect
            if user.is_staff:
                return redirect('saritasapp:dashboard')
            return redirect('customerapp:homepage')
    else:
        form = LoginForm()

    return render(request, 'saritasapp/signin.html', {
        'form': form,
        'next': request.GET.get('next', '')
    })

# --- Dashboard View ---
@staff_member_required
def dashboard(request):
    return render(request, 'saritasapp/dashboard.html')


# --- Logout View ---
def logout_view(request):
    logout(request)
    return redirect('customerapp:homepage')


@staff_member_required
def receipt_view(request):
        try:
            receipt = Receipt.objects.latest('id')
            return redirect('saritasapp:receipt-update', encrypted_id=receipt.encrypted_id)
        except Receipt.DoesNotExist:
        # Handle case where no receipts exist
            return render(request, 'saritasapp/receipt.html', {'error': 'No receipts found'})

@staff_member_required
def receipt_detail(request, encrypted_id):
    receipt = get_decrypted_object_or_404(Receipt, encrypted_id)
    return render(request, 'saritasapp/receipt_detail.html', {'receipt': receipt})

#Receipt
@staff_member_required
def update_receipt(request, encrypted_id):
    receipt = get_decrypted_object_or_404(Receipt, encrypted_id)

    if request.method == "POST":
        try:
            receipt.amount = float(request.POST.get("amount", receipt.amount) or receipt.amount)
            receipt.down_payment = float(request.POST.get("down_payment", receipt.down_payment) or receipt.down_payment)
            receipt.customer_name = request.POST.get("customer_name", receipt.customer_name).strip()
            receipt.customer_number = request.POST.get("customer_number", receipt.customer_number).strip()
            receipt.payment_method = request.POST.get("payment_method", receipt.payment_method).strip()
            receipt.remarks = request.POST.get("remarks", receipt.remarks).strip()

            date_fields = {
                "payment_time": "%Y-%m-%dT%H:%M",
                "event_date": "%Y-%m-%d",
                "pickup_date": "%Y-%m-%d",
                "return_date": "%Y-%m-%d",
            }
            for field, format in date_fields.items():
                date_value = request.POST.get(field, "").strip()
                if date_value:  
                    try:
                        setattr(receipt, field, datetime.strptime(date_value, format))
                    except ValueError:
                        return render(request, "saritasapp/receipt.html", {
                            "receipt": receipt,
                            "error": f"Invalid format for {field}. Please use {format}."
                        })

            measurement_fields = [
                "shoulder", "bust", "front", "width", "waist", "hips",
                "arm_length", "bust_depth", "bust_distance", "length",
                "lower_circumference", "crotch"
            ]
            for field in measurement_fields:
                value = request.POST.get(field, "").strip()
                setattr(receipt, field, float(value) if value.replace('.', '', 1).isdigit() else getattr(receipt, field))
            
            receipt.save()
            return redirect("saritasapp:receipt-detail", encrypted_id=encrypt_id(receipt.id))

        except ValueError as e:
            return render(request, "saritasapp/receipt.html", {
                "receipt": receipt,
                "error": f"Invalid input: {str(e)}"
            })

    return render(request, "saritasapp/receipt.html", {"receipt": receipt})

@staff_member_required
def generate_receipt_pdf(request, encrypted_id):
    receipt = get_decrypted_object_or_404(Receipt, encrypted_id)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="receipt_{receipt.id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title psrt
    elements.append(Paragraph("<b>Official Receipt</b>", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Receipt detils
    details = [
         ["Receipt ID:", receipt.id],
        ["Name:", receipt.customer_name or "N/A"],  
        ["Contact:", receipt.customer_number or "N/A"],
        ["Amount:", f"₱{receipt.amount:,.2f}"],
        ["Down Payment:", f"₱{receipt.down_payment:,.2f}"],
        ["Payment Method:", receipt.payment_method or "N/A"],
        ["Event Date:", receipt.event_date.strftime("%Y-%m-%d") if receipt.event_date else "N/A"],
        ["Pickup Date:", receipt.pickup_date.strftime("%Y-%m-%d") if receipt.pickup_date else "N/A"],
        ["Return Date:", receipt.return_date.strftime("%Y-%m-%d") if receipt.return_date else "N/A"],
        ["Remarks:", receipt.remarks if receipt.remarks else "N/A"]
    ]

    table = Table(details, colWidths=[150, 300])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("BACKGROUND", (0, 1), (-1, -1), colors.beige),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(table)
    elements.append(Spacer(1, 12))

    # Measurements
    elements.append(Paragraph("<b>Measurements:</b>", styles["Heading2"]))
    measurement_data = [
        ["Shoulder:", receipt.shoulder or "N/A"],
        ["Bust:", receipt.bust or "N/A"],
        ["Front:", receipt.front or "N/A"],
        ["Width:", receipt.width or "N/A"],
        ["Waist:", receipt.waist or "N/A"],
        ["Hips:", receipt.hips or "N/A"],
        ["Arm Length:", receipt.arm_length or "N/A"],
        ["Bust Depth:", receipt.bust_depth or "N/A"],
        ["Bust Distance:", receipt.bust_distance or "N/A"],
        ["Length:", receipt.length or "N/A"],
        ["Lower Circumference:", receipt.lower_circumference or "N/A"],
        ["Crotch:", receipt.crotch or "N/A"]
    ]

    measurement_table = Table(measurement_data, colWidths=[150, 300])
    measurement_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(measurement_table)
    elements.append(Spacer(1, 12))

    
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("__________________________", styles["Normal"]))
    elements.append(Paragraph("Authorized Signature", styles["Italic"]))

    # Build PDF
    doc.build(elements)
    return response


@staff_member_required
def wardrobe_package_view(request, encrypted_id):
    package = get_decrypted_object_or_404(WardrobePackage, encrypted_id)

    inventory = {}
    items = Inventory.objects.filter(package=package)
    for item in items:
        if item.category not in inventory:
            inventory[item.category] = []
        inventory[item.category].append(item)

    total_price = package.base_price + package.refundable_deposit + sum(item.rental_price for item in items)

    context = {
        'package': package,
        'inventory': inventory,
        'total_price': total_price,
    }

    if request.method == 'POST':
        selected_items = request.POST.getlist('wardrobe_items')
        selected_item_prices = Inventory.objects.filter(id__in=selected_items).values_list('rental_price', flat=True)
        total_price = package.base_price + package.refundable_deposit + sum(selected_item_prices)
        context['total_price'] = total_price

    return render(request, 'saritasapp/wardrobe_package.html', context)


@staff_member_required
def wardrobe_package_list(request):
    packages = WardrobePackage.objects.filter(status='active')
    return render(request, 'saritasapp/wardrobe_package_list.html', {'packages': packages})

@staff_member_required
def wardrobe_package_view(request, encrypted_id):
    package = get_decrypted_object_or_404(WardrobePackage, encrypted_id)
    customers = Customer.objects.all()

    # Organizing inventory items by category
    items = Inventory.objects.filter(package=package)

    # Calculate total price including refundable deposit
    total_price = package.base_price + package.refundable_deposit + sum(item.rental_price for item in items)

    context = {
        'package': package,
        'customers': customers,
        'items': items,
        'total_price': total_price,
    }

    if request.method == 'POST':
        selected_items = request.POST.getlist('selected_items')
        customer_id = request.POST.get('customer_id')

        if not customer_id:
            context['error'] = "Please select a customer."
            return render(request, 'saritasapp/wardrobe_package.html', context)

        selected_item_prices = Inventory.objects.filter(id__in=selected_items).values_list('rental_price', flat=True)
        total_price = package.base_price + package.refundable_deposit + sum(selected_item_prices)

        context['total_price'] = total_price
        context['success'] = "Package selected successfully!"

    return render(request, 'saritasapp/wardrobe_package.html', context)

#made to order
from django.shortcuts import render, redirect, get_object_or_404
from .models import Receipt

@staff_member_required
def made_to_order_view(request):
    """Handles made-to-order page and saves measurements."""
    
    # Get the latest receipt or create a new one
    receipt = Receipt.objects.order_by('-id').first() or Receipt.objects.create()

    if request.method == "POST":
        # Update receipt with submitted measurements
        receipt.shoulder = request.POST.get("shoulder")
        receipt.bust = request.POST.get("bust")
        receipt.front = request.POST.get("front")
        receipt.width = request.POST.get("width")
        receipt.waist = request.POST.get("waist")
        receipt.hips = request.POST.get("hips")
        receipt.arm_length = request.POST.get("arm_length")
        receipt.bust_depth = request.POST.get("bust_depth")
        receipt.bust_distance = request.POST.get("bust_distance")
        receipt.length = request.POST.get("length")
        receipt.lower_circumference = request.POST.get("lower_circumference")
        receipt.crotch = request.POST.get("crotch")
        receipt.remarks = request.POST.get("remarks")
        receipt.save()

        # Redirect to receipt detail page
        return redirect("saritasapp:receipt-detail", receipt_id=receipt.id)

    return render(request, "saritasapp/made_to_order.html", {"receipt": receipt})

@staff_member_required
def receipt_detail(request, encrypted_id):
    """Display receipt details."""
    receipt = get_decrypted_object_or_404(Receipt, encrypted_id)
    return render(request, "saritasapp/receipt.html", {"receipt": receipt})

#calnder
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from .models import Event
from django.http import JsonResponse

@staff_member_required
def calendar_view(request):
    events = Event.objects.all()
    return render(request, "saritasapp/calendar.html", {"events": events})

@staff_member_required
def view_event(request, encrypted_id):
    event = get_decrypted_object_or_404(Event, encrypted_id)
    return render(request, "saritasapp/view_event.html", {"event": event})

@staff_member_required
def create_event(request):
    if request.method == "POST":
        title = request.POST.get("title")
        venue = request.POST.get("venue")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        notes = request.POST.get("notes")

        # Validate required fields
        if not title or not venue or not start_date:
            return render(request, "saritasapp/create_event.html", {"error": "All fields are required"})

        # Save event
        Event.objects.create(
            title=title,
            venue=venue,
            start_date=start_date,
            end_date=end_date,
            notes=notes
        )

        return redirect("saritasapp:calendar")  # Redirect after saving

    return render(request, "saritasapp/create_event.html")

@staff_member_required
def ongoing_events(request):
    events = Event.objects.filter(start_date__lte=now().date(), end_date__gte=now().date())
    return render(request, "saritasapp/ongoing_events.html", {"events": events})

@staff_member_required
def upcoming_events(request):
    events = Event.objects.filter(start_date__gt=now().date()) 
    return render(request, "saritasapp/upcoming_events.html", {"events": events})

@staff_member_required
def past_events(request):
    events = Event.objects.filter(end_date__lt=now().date())  
    return render(request, "saritasapp/past_events.html", {"events": events})

@staff_member_required
def get_events(request):
    events = Event.objects.all()
    events_data = [
        {
            "id": event.id,
            "title": event.title,
            "start": event.start_date.strftime("%Y-%m-%d"),  
            "end": event.end_date.strftime("%Y-%m-%d") if event.end_date else None, 
        }
        for event in events
    ]
    return JsonResponse(events_data, safe=False)



#profile


@staff_member_required
def staff_profile_view(request):
    """Handles profile updates"""
    user = request.user  # Get the logged-in user
    
    if request.method == "POST":
        form = EditProfileForm(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated successfully!")
            return redirect("saritasapp:profile")  # ✅ Correct app namespace
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = EditProfileForm(instance=user)

@staff_member_required
def sign_out(request):
    """Logs out the user and redirects to logout page"""
    if request.method == "POST" or request.method == "GET":  # ✅ Allow both GET & POST
        logout(request)
        return redirect("saritasapp:logout")  # ✅ Redirect to logout confirmation page
    
    return redirect("saritasapp:profile")  # If another method is used


@staff_member_required
def edit_event(request, encrypted_id):
    event = get_decrypted_object_or_404(Event, encrypted_id)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('saritasapp:view_event', encrypted_id=encrypt_id(event.id))
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EventForm(instance=event)

    return render(request, 'saritasapp/edit_event.html', {'form': form, 'event': event})

@staff_member_required
def delete_event(request, encrypted_id):
    event = get_decrypted_object_or_404(Event, encrypted_id)

    if request.method == 'POST':
        event.delete()
        messages.success(request, f"Event '{event.title}' has been successfully deleted.")
        return redirect('saritasapp:calendar')

    return render(request, 'saritasapp/confirm_delete_event.html', {'event': event})

# not final packages implementation
from django.shortcuts import render

from django.shortcuts import render, redirect
from django.http import JsonResponse
from .models import Venue  # Make sure Venue model is imported

@staff_member_required
def wedding_packages(request):
    if request.method == 'POST':
        custom_venues = {v.venue_id: v.base_price for v in Venue.objects.filter(is_custom=True, created_by=request.user)}

        venue_id = request.POST.get('venue')
        venue_price = 0
        venue_name = ""

        if venue_id and venue_id.startswith('custom_'):
            venue_price = custom_venues.get(venue_id, 0)
            venue_name = request.POST.get(f'venue_{venue_id}_name', 'Custom Venue')
        else:
            try:
                venue_obj = Venue.objects.get(venue_id=venue_id)
                venue_name = venue_obj.name
                venue_price = venue_obj.base_price
            except Venue.DoesNotExist:
                venue_name = "Unknown"
                venue_price = 0

        data = {
            'sizes': {
                'bride': request.POST.get('bride_size'),
                'groom': request.POST.get('groom_size')
            },
            'guests': int(request.POST.get('guests', 0)),
            'venue': {
                'id': venue_id,
                'name': venue_name,
                'price': venue_price
            },
            'services': request.POST.getlist('services'),
            'total_price': float(request.POST.get('total_price', 0))
        }

        request.session['wedding_customization'] = data
        return redirect('saritasapp:wedding_confirmation')

    return render(request, 'saritasapp/wedding_packages.html')


@staff_member_required
def wedding_confirmation(request):
    customization = request.session.get('wedding_customization', {})
    return render(request, 'saritasapp/wedding_confirmation.html', {
        'customization': customization
    })


@staff_member_required
def add_custom_venue(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')

        if name and price:
            from datetime import datetime
            venue_id = f'custom_{int(datetime.now().timestamp())}'

            Venue.objects.create(
                venue_id=venue_id,
                name=name,
                base_price=price,
                is_custom=True,
                created_by=request.user
            )
            return JsonResponse({'status': 'success', 'venue_id': venue_id})
        
        return JsonResponse({'status': 'invalid data'}, status=400)

    return JsonResponse({'status': 'error'}, status=400)    

from django.shortcuts import render, redirect

# Debut Packages View
@staff_member_required
def debut_packages(request):
    if request.method == 'POST':
        # Process debut customization
        request.session['debut_customization'] = {
            'sizes': {
                'debutant': request.POST.get('debutant_size'),
                'parent': request.POST.get('parent_size')
            },
            'guests': request.POST.get('guest_count'),
            'theme': request.POST.get('theme'),
            'services': request.POST.getlist('services')
        }
        return redirect('debut_confirmation')
    return render(request, 'saritasapp/debut_packages.html')

# Additional Services View
@staff_member_required
def additional_services(request):
    if request.method == 'POST':
        request.session['additional_services'] = {
            'services': request.POST.getlist('services'),
            'duration': request.POST.get('duration'),
            'requests': request.POST.get('special_requests')
        }
        return redirect('saritasapp:additional_confirmation')
    return render(request, 'saritasapp/additional_services.html')

# Debut Confirmation View
@staff_member_required
def debut_confirmation(request):
    customization = request.session.get('debut_customization', {})
    # Add price calculation logic if needed
    return render(request, 'saritasapp/debut_confirmation.html', {
        'customization': customization
    })

# Additional Services Confirmation View
@staff_member_required
def additional_confirmation(request):
    services = request.session.get('additional_services', {})
    return render(request, 'saritasapp/additional_confirmation.html', {
        'services': services
    })

#wardrobe packages view
class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class WardrobePackageListView(StaffRequiredMixin, ListView):
    model = WardrobePackage
    template_name = 'saritasapp/wardrobe_package_list.html'
    context_object_name = 'packages'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        valid_packages = []
        
        for package in context['packages']:
            if package.encrypted_id:  # Only include packages with valid encryption
                valid_packages.append(package)
            else:
                logger.error(f"Skipping package {package.id} - encryption failed")
        
        context['packages'] = valid_packages
        return context

class WardrobePackageCreateView(StaffRequiredMixin, CreateView):
    model = WardrobePackage
    form_class = WardrobePackageForm
    template_name = 'saritasapp/wardrobe_package_form.html'
    success_url = reverse_lazy('saritasapp:wardrobe_package_list')

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Package "{self.object.name}" created successfully!')
        return response

    
class WardrobePackageUpdateView(StaffRequiredMixin, UpdateView):
    model = WardrobePackage
    form_class = WardrobePackageForm
    template_name = 'saritasapp/wardrobe_package_form.html'
    success_url = reverse_lazy('saritasapp:wardrobe_package_list')

    def get_object(self, queryset=None):
        """Get the object using the decrypted ID from URL"""
        return get_decrypted_object_or_404(
            WardrobePackage,
            self.kwargs.get('encrypted_id'),
            queryset=queryset
        )

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Package "{self.object.name}" updated successfully!')
        return response

# ✅ This is the fixed function that determines which item types a package includes
def package_needs_this_type(package, item_type):
    # Example logic based on the package tier
    tier_rules = {
        'A': ['dress', 'tuxedo'],
        'B': ['dress', 'tuxedo', 'barong'],
        'C': ['dress', 'tuxedo', 'barong', 'gown', 'accessory'],
    }
    allowed_types = tier_rules.get(package.tier, [])
    return item_type in allowed_types



class WardrobePackageDetailView(StaffRequiredMixin, DetailView):
    model = WardrobePackage
    template_name = 'saritasapp/wardrobe_package_detail.html'
    context_object_name = 'package'
    pk_url_kwarg = 'encrypted_id'  # Use encrypted_id for primary key instead of default pk

    def get_object(self, queryset=None):
        """Override to handle encrypted ID decryption"""
        encrypted_id = self.kwargs.get('encrypted_id')
        try:
            package_id = decrypt_id(encrypted_id)  # Decrypt the ID
            return get_object_or_404(WardrobePackage, pk=package_id)  # Get the object using the decrypted ID
        except (ValueError, TypeError):
            raise Http404("Invalid package ID")  # Raise 404 if decryption fails

    def validate_package_completeness(self, package):
        """Check if package has all required item types based on its tier"""
        tier_requirements = {
            'A': ['bridal_gown', 'groom_tuxedo', 'maid_of_honor', 'bestman',
                'bridesmaid', 'groomsmen', 'flowergirl', 'bearer'],
            'B': ['bridal_gown', 'groom_tuxedo', 'maid_of_honor', 'bestman',
                'bridesmaid', 'groomsmen', 'flowergirl', 'bearer'],
            'C': ['bridal_gown', 'groom_tuxedo', 'maid_of_honor', 'bestman',
                'bridesmaid', 'groomsmen', 'flowergirl', 'bearer',
                'mother_gown', 'father_attire'],
            'custom': []
        }

        existing_types = set(
            package.package_items
            .select_related('inventory_item__item_type')
            .values_list('inventory_item__item_type__name', flat=True)
        )

        missing_types = [
            t for t in tier_requirements.get(package.tier, [])
            if t not in existing_types
        ]
        return missing_types

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = self.object
        
        # Package completeness check
        missing_required = self.validate_package_completeness(package)
        context.update({
            'missing_required': missing_required,
            'package_complete': not missing_required,
            'items_by_type': self._group_items_by_type(package),
            'item_types': ItemType.objects.all(),
            'encrypted_id': self.kwargs['encrypted_id']  # Pass encrypted_id to template
        })
        return context

    def _group_items_by_type(self, package):
        """Helper method to group package items by their type"""
        items_by_type = {}
        for item in package.package_items.select_related('inventory_item__item_type'):
            item_type = item.inventory_item.item_type.name
            items_by_type.setdefault(item_type, []).append(item)
        return items_by_type


class AddPackageItemView(StaffRequiredMixin, TemplateView):
    template_name = 'saritasapp/add_package_item.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        encrypted_id = self.kwargs['encrypted_id']
        package = get_decrypted_object_or_404(WardrobePackage, encrypted_id)
        
        item_types = []
        for item_type in ItemType.objects.all():
            items = Inventory.objects.filter(
                item_type=item_type,
                available=True,
                quantity__gt=0
            ).exclude(
                id__in=package.package_items.values_list('inventory_item_id', flat=True)
            )
            
            if items.exists():
                item_types.append({
                    'type': item_type,
                    'items': items
                })
        
        context.update({
            'package': package,
            'item_types': item_types,
            'existing_items': package.package_items.select_related('inventory_item')
        })
        return context
    


class SubmitBulkPackageItemsView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            encrypted_package_id = kwargs.get('encrypted_id')
            if not encrypted_package_id:
                raise Http404("Package ID not found in URL")
            
            try:
                package_id = decrypt_id(encrypted_package_id)
                package = WardrobePackage.objects.get(pk=package_id)
            except Exception as e:
                logger.error(f"Failed to decrypt package ID {encrypted_package_id}: {str(e)}")
                raise Http404("Invalid package ID")
            
            # Get all items from POST data
            post_data = request.POST
            selected_items = []
            
            # Collect all item data from the form
            for key in post_data:
                if key.startswith('item_') and key.endswith('_quantity'):
                    item_id = key.split('_')[1]
                    quantity = post_data.get(key)
                    label = post_data.get(f'item_{item_id}_label', '')
                    
                    if item_id and quantity:
                        selected_items.append({
                            'id': item_id,
                            'quantity': quantity,
                            'label': label
                        })
            
            if not selected_items:
                messages.error(request, "No items selected")
                return redirect('saritasapp:add_package_item', encrypted_id=encrypted_package_id)

            with transaction.atomic():
                selected_types = set()
                for item_data in selected_items:
                    try:
                        item = Inventory.objects.get(id=item_data['id'])
                        
                        # Check for duplicate types
                        if item.item_type in selected_types:
                            messages.error(request, 
                                f"Can only select one {item.item_type.get_name_display()} per package")
                            return redirect('saritasapp:add_package_item', 
                                         encrypted_id=encrypted_package_id)
                        
                        selected_types.add(item.item_type)
                        
                        # Create package item
                        WardrobePackageItem.objects.create(
                            package=package,
                            inventory_item=item,
                            quantity=int(item_data['quantity']),
                            label=item_data['label'],
                            is_required=True
                        )
                        
                    except Inventory.DoesNotExist:
                        messages.error(request, f"Item {item_data['id']} no longer available")
                        return redirect('saritasapp:add_package_item', 
                                     encrypted_id=encrypted_package_id)
                    except ValueError as e:
                        messages.error(request, f"Invalid quantity for item {item.id}")
                        return redirect('saritasapp:add_package_item', 
                                     encrypted_id=encrypted_package_id)
                
                messages.success(request, f"Added {len(selected_items)} items to package")
                return redirect('saritasapp:wardrobe_package_detail', 
                             encrypted_id=encrypted_package_id)
                
        except Exception as e:
            logger.error(f"Error in SubmitBulkPackageItemsView: {str(e)}", exc_info=True)
            messages.error(request, "Error processing your request")
            return redirect('saritasapp:wardrobe_package_list')

class AddPackageItemSubmitView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        encrypted_id = kwargs['encrypted_id']
        package = get_decrypted_object_or_404(WardrobePackage, encrypted_id)
        form = PackageItemForm(request.POST, package=package)
        
        if form.is_valid():
            try:
                item = Inventory.objects.get(
                    id=form.cleaned_data['inventory_item_id'],
                    available=True
                )
                
                WardrobePackageItem.objects.create(
                    package=package,
                    inventory_item=item,
                    quantity=form.cleaned_data['quantity'],
                    label=form.cleaned_data['label'],
                    is_required=True
                )
                messages.success(request, f"Added {item.name} to package")
            except Inventory.DoesNotExist:
                messages.error(request, "Selected item is no longer available")
        else:
            messages.error(request, "Error adding item to package")
        
        return redirect('saritasapp:add_package_item', encrypted_id=encrypt_id(package.pk))

class EditPackageItemView(StaffRequiredMixin, UserPassesTestMixin, UpdateView):
    model = WardrobePackageItem
    form_class = WardrobePackageItemForm
    template_name = 'saritasapp/edit_package_item.html'

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self, queryset=None):
        package_id = decrypt_id(self.kwargs.get('package_id'))
        item_id = decrypt_id(self.kwargs.get('item_id'))
        
        return get_object_or_404(
            WardrobePackageItem,
            pk=item_id,
            package_id=package_id
        )

    def get_success_url(self):
        return reverse('saritasapp:wardrobe_package_detail', 
                     kwargs={'encrypted_id': self.kwargs.get('package_id')})

class FilterInventoryItemsView(StaffRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        item_type_id = request.GET.get('item_type')
        encrypted_package_id = request.GET.get('package')
        
        existing_item_ids = []
        if encrypted_package_id:
            try:
                package_id = decrypt_id(encrypted_package_id)
                existing_item_ids = WardrobePackageItem.objects.filter(
                    package_id=package_id
                ).values_list('inventory_item_id', flat=True)
            except (ValueError, TypeError):
                pass
        
        items = Inventory.objects.filter(
            item_type_id=item_type_id,
            available=True
        ).exclude(id__in=existing_item_ids)
        
        return JsonResponse({
            'results': [{
                'id': item.id,
                'text': f"{item.name} ({item.size}) - ₱{item.rental_price}"
            } for item in items]
        })

class WardrobePackageDeleteView(StaffRequiredMixin, UserPassesTestMixin, DeleteView):
    model = WardrobePackage
    template_name = 'saritasapp/confirm_delete_package.html'
    pk_url_kwarg = 'encrypted_id'
    success_url = reverse_lazy('saritasapp:wardrobe_package_list')

    def test_func(self):
        return self.request.user.is_superuser

    def get_object(self, queryset=None):
        encrypted_id = self.kwargs.get('encrypted_id')
        return get_decrypted_object_or_404(WardrobePackage, encrypted_id)

    def delete(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                self.object = self.get_object()
                
                # First delete all related package items
                self.object.package_items.all().delete()
                
                # Then delete any related rentals
                WardrobePackageRental.objects.filter(package=self.object).delete()
                
                # Finally delete the package
                response = super().delete(request, *args, **kwargs)
                
                messages.success(request, f"Package '{self.object.name}' deleted successfully!")
                return response
                
        except Exception as e:
            messages.error(request, f"Error deleting package: {str(e)}")
            return redirect('saritasapp:wardrobe_package_detail', encrypted_id=self.kwargs['encrypted_id'])

# Rental Approval Views
@login_required
@user_passes_test(lambda u: u.is_staff)
def staff_rental_requests(request):
    logger.info(f"Staff user {request.user} accessing rental requests")
    pending_rentals = WardrobePackageRental.objects.filter(
        status=WardrobePackageRental.PENDING
    ).select_related(
        'customer__user', 'package'
    ).order_by('event_date')
    
    logger.info(f"Found {pending_rentals.count()} pending rentals")
    
    return render(request, 'staff/rental_requests.html', {
        'pending_rentals': pending_rentals
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def staff_manage_rental(request, encrypted_id):
    rental = get_decrypted_object_or_404(WardrobePackageRental, encrypted_id)
    
    if request.method == 'POST':
        form = StaffRentalApprovalForm(request.POST, instance=rental)
        if form.is_valid():
            rental = form.save(commit=False)
            rental.staff = request.user
            rental.save()
            
            messages.success(request, f"Rental updated to {rental.get_status_display()}!")
            return redirect('saritasapp:staff_rental_requests')
    else:
        form = StaffRentalApprovalForm(instance=rental)
    
    return render(request, 'staff/manage_rental.html', {
        'rental': rental,
        'form': form
    })

@staff_member_required
def process_return(request, encrypted_id):
    rental = get_decrypted_object_or_404(WardrobePackageRental, encrypted_id)
    
    if request.method == 'POST':
        form = PackageReturnForm(request.POST, instance=rental)
        if form.is_valid():
            try:
                rental = form.save(commit=False)
                rental.mark_as_returned(request.user)  # Use model method
                messages.success(request, "Package marked as returned!")
                return redirect('saritasapp:staff_dashboard')
            except ValidationError as e:
                messages.error(request, str(e))
    
    else:
        form = PackageReturnForm(instance=rental)
    
    return render(request, 'staff/process_return.html', {
        'form': form,
        'rental': rental
    })

@staff_member_required
def package_rental_approvals(request):
    """View for listing package rentals needing approval."""
    status_filter = request.GET.get('status', 'pending').lower()
    
    valid_statuses = [s[0] for s in WardrobePackageRental.STATUS_CHOICES]
    if status_filter not in valid_statuses:
        status_filter = 'pending'
    
    rentals = WardrobePackageRental.objects.filter(
        status=status_filter
    ).select_related(
        'customer__user', 'package'
    ).order_by('event_date')
    
    rental_list = []
    for rental in rentals:
        try:
            encrypted_id = encrypt_id(rental.id)
            rental_list.append((rental, encrypted_id))
        except Exception as e:
            logger.error(f"Error encrypting rental ID {rental.id}: {e}")
            continue
    
    return render(request, 'saritasapp/package_rental_approvals.html', {
        'rental_list': rental_list,
        'current_status': status_filter
    })

@staff_member_required
def update_package_rental_status(request, encrypted_id, action):
    try:
        rental = get_decrypted_object_or_404(WardrobePackageRental, encrypted_id)
        
        if action == 'approve':
            rental.approve(request.user)  # Use model method
            messages.success(request, "Rental approved successfully!")
            
        elif action == 'reject':
            if request.method == 'POST':
                reason = request.POST.get('notes', '')
                rental.reject(request.user, reason)  # Use model method
                messages.success(request, "Rental rejected successfully!")
            else:
                raise PermissionDenied
                
        elif action == 'complete':
            rental.mark_as_completed(request.user)  # Use model method
            messages.success(request, "Rental marked as completed!")
            
        return redirect('saritasapp:package_rental_approvals')
        
    except Exception as e:
        messages.error(request, f"Error processing request: {str(e)}")
        return redirect('saritasapp:package_rental_approvals')

def package_rental_detail(request, encrypted_id):
    rental = get_decrypted_object_or_404(
        WardrobePackageRental, 
        encrypted_id,
        queryset=WardrobePackageRental.objects.select_related('customer__user', 'package')
    )
    return render(request, 'customerapp/package_rental_detail.html', {
        'rental': rental,
        'encrypted_id': encrypted_id  # Pass the encrypted ID to template
    })

@staff_member_required
def staff_package_rental_detail(request, encrypted_id):
    rental = get_decrypted_object_or_404(WardrobePackageRental, encrypted_id)
    return render(request, 'saritasapp/staff_package_rental_detail.html', {
        'rental': rental,
        'rental_items': rental.package.package_items.all()
    })


from django.http import JsonResponse
from .models import Rental
from django.urls import reverse

def rental_events(request):
    rentals = Rental.objects.all()
    events = []

    for rental in rentals:
        # Add the rental period as a single event from start to end
        events.append({
            "id": rental.id,
            "title": f"Rental #{rental.id} - {rental.customer.user.get_full_name()}",
            "start": rental.rental_start.isoformat(),
            "end": (rental.rental_end + timedelta(days=1)).isoformat(),  # FullCalendar is exclusive of the end date
            "url": reverse('saritasapp:rental_detail', args=[rental.id]),
            "backgroundColor": "#4F6F52",  # optional styling
            "borderColor": "#9DB2BF",
        })

    return JsonResponse(events, safe=False)

def rental_events_api(request):
    rentals = Rental.objects.all()
    data = []
    for rental in rentals:
        data.append({
            "id": rental.id,
            "title": f"Rental: {rental.inventory.name}",
            "start": rental.rental_start.isoformat(),
            "end": (rental.rental_end + timedelta(days=1)).isoformat(),
            "isRental": True,
            "inventory_id": rental.inventory.encrypted_id  # ← this must match extendedProps.inventory_id
        })
    return JsonResponse(data, safe=False)

# saritasapp/views.py
# saritasapp/views.py
from django.db.models import Q, Sum
from django.shortcuts import render
from datetime import datetime, timedelta
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from io import BytesIO
import base64
from .models import Rental, Reservation

# Elegant color palette
COLOR_PALETTE = {
    'primary': '#4a6fa5',      # Navy blue
    'secondary': '#a78a7f',    # Muted brown
    'accent': '#c1666b',       # Dusty red
    'success': '#5b8c5a',      # Sage green
    'light': '#f8f9fa',        # Light background
    'dark': '#212529',         # Dark text
    'border': '#dee2e6',       # Light border
    'highlight': '#e9ecef'     # Highlight color
}

def financial_report(request):
    period = request.GET.get('period', 'weekly')
    start_date, end_date = get_date_range(period)
    
    # Rental data
    rentals = Rental.objects.filter(
        Q(created_at__date__gte=start_date) & 
        Q(created_at__date__lte=end_date) &
        Q(status__in=['Rented', 'Returned'])
    )
    
    rental_revenue = rentals.aggregate(
        Sum('inventory_size__inventory__rental_price')
    )['inventory_size__inventory__rental_price__sum'] or 0
    
    rental_deposits = rentals.aggregate(Sum('deposit'))['deposit__sum'] or 0
    penalty_total = rentals.aggregate(Sum('penalty_fee'))['penalty_fee__sum'] or 0
    damage_total = rentals.aggregate(Sum('damage_fee'))['damage_fee__sum'] or 0
    rental_fees = penalty_total + damage_total

    
    # Reservation data
    reservations = Reservation.objects.filter(
        Q(created_at__date__gte=start_date) & 
        Q(created_at__date__lte=end_date) &
        Q(status__in=['paid', 'fulfilled'])
    )
    
    reservation_revenue = reservations.aggregate(
        Sum('reservation_fee')
    )['reservation_fee__sum'] or 0
    
    # Combined financials
    financials = {
        'rentals': {
            'revenue': rental_revenue,
            'deposits': rental_deposits,
            'fees': rental_fees,
            'count': rentals.count()
        },
        'reservations': {
            'revenue': reservation_revenue,
            'count': reservations.count()
        },
        'total': {
            'revenue': rental_revenue + reservation_revenue,
            'transactions': rentals.count() + reservations.count()
        }
    }
    
    # Generate charts
    charts = {
        'rental_trend': generate_chart(rentals, 'rental_start', 'inventory_size__inventory__rental_price', 
                                      'Rental Revenue Trend', COLOR_PALETTE['primary'], period),
        'reservation_trend': generate_chart(reservations, 'created_at', 'reservation_fee', 
                                          'Reservation Revenue Trend', COLOR_PALETTE['secondary'], period),
        'rental_distribution': generate_pie_chart(rentals, 'inventory_size__inventory__category__name', 
                                                'inventory_size__inventory__rental_price', 
                                                'Rental Revenue Distribution', COLOR_PALETTE['primary']),
        'reservation_distribution': generate_pie_chart(reservations, 'inventory_size__inventory__category__name', 
                                                     'reservation_fee', 
                                                     'Reservation Revenue Distribution', COLOR_PALETTE['secondary']),
        'comparison': generate_comparison_chart(rentals, reservations, period)
    }
    
    has_data = rentals.exists() or reservations.exists()
    
    context = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'financials': financials,
        'charts': charts,
        'colors': COLOR_PALETTE,
        'has_data': has_data
    }
    return render(request, 'saritasapp/data_analysis.html', context)

def get_date_range(period):
    today = datetime.now().date()
    if period == 'weekly':
        start_date = today - timedelta(days=7)
    elif period == 'monthly':
        start_date = today - timedelta(days=30)
    elif period == 'yearly':
        start_date = today - timedelta(days=365)
    else:
        start_date = today - timedelta(days=7)
    return start_date, today

def generate_chart(queryset, date_field, value_field, title, color, period):
    try:
        df = pd.DataFrame.from_records(
            queryset.values(date_field).annotate(
                amount=Sum(value_field)
            )
        )
        if df.empty:
            return None
            
        df['date'] = pd.to_datetime(df[date_field])
        df = df[['date', 'amount']].set_index('date')
        
        if period == 'weekly':
            resampled = df.resample('W-MON').sum()
            title = f'Weekly {title}'
        elif period == 'monthly':
            resampled = df.resample('ME').sum()
            title = f'Monthly {title}'
        else:
            resampled = df.resample('YE').sum()
            title = f'Yearly {title}'

        plt.figure(figsize=(8, 4.5))
        ax = sns.lineplot(
            data=resampled, x=resampled.index, y='amount',
            color=color,
            linewidth=2.5,
            marker='o',
            markersize=8
        )
        
        # Style enhancements
        ax.set_title(title, color=COLOR_PALETTE['dark'], fontsize=13, pad=15)
        ax.set_xlabel('Date', color=COLOR_PALETTE['dark'], fontsize=11)
        ax.set_ylabel('Amount (₱)', color=COLOR_PALETTE['dark'], fontsize=11)
        ax.tick_params(colors=COLOR_PALETTE['dark'], labelsize=9)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_facecolor(COLOR_PALETTE['light'])
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', facecolor='white', dpi=100, bbox_inches='tight')
        plt.close()
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Chart Error ({title}): {str(e)}")
        return None

def generate_pie_chart(queryset, group_field, value_field, title, base_color):
    try:
        df = pd.DataFrame.from_records(
            queryset.values(group_field).annotate(
                total=Sum(value_field)
            )
        )
        if df.empty or df['total'].sum() == 0:
            return None
            
        df['total'] = pd.to_numeric(df['total'], errors='coerce').fillna(0)
        df = df[df['total'] > 0]
        
        if df.empty:
            return None

        # Generate a color palette based on the base color
        colors = sns.light_palette(base_color, n_colors=len(df)+2)[1:-1]
        
        plt.figure(figsize=(7, 7))
        ax = df.set_index(group_field)['total'].plot.pie(
            autopct=lambda p: f'{p:.1f}%\n(₱{p*sum(df["total"])/100:.2f}',
            startangle=90,
            colors=colors,
            wedgeprops={'edgecolor': COLOR_PALETTE['dark'], 'linewidth': 0.7},
            textprops={'color': COLOR_PALETTE['dark'], 'fontsize': 9}
        )
        ax.set_title(title, color=COLOR_PALETTE['dark'], fontsize=13, pad=20)
        ax.set_ylabel('')
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', facecolor='white', dpi=100, bbox_inches='tight')
        plt.close()
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Pie Chart Error ({title}): {str(e)}")
        return None

def generate_comparison_chart(rentals, reservations, period):
    try:
        # Rental data
        rental_df = pd.DataFrame.from_records(
            rentals.values('rental_start').annotate(
                rental_revenue=Sum('inventory_size__inventory__rental_price')
            )
        )
        if not rental_df.empty:
            rental_df['date'] = pd.to_datetime(rental_df['rental_start'])
            rental_df = rental_df.set_index('date')['rental_revenue']
            
            if period == 'weekly':
                rental_df = rental_df.resample('W-MON').sum()
            elif period == 'monthly':
                rental_df = rental_df.resample('ME').sum()
            else:
                rental_df = rental_df.resample('YE').sum()
        
        # Reservation data
        reservation_df = pd.DataFrame.from_records(
            reservations.values('created_at').annotate(
                reservation_revenue=Sum('reservation_fee')
            )
        )
        if not reservation_df.empty:
            reservation_df['date'] = pd.to_datetime(reservation_df['created_at'])
            reservation_df = reservation_df.set_index('date')['reservation_revenue']
            
            if period == 'weekly':
                reservation_df = reservation_df.resample('W-MON').sum()
            elif period == 'monthly':
                reservation_df = reservation_df.resample('ME').sum()
            else:
                reservation_df = reservation_df.resample('YE').sum()
        
        # Combine data
        df = pd.concat([
            rental_df.rename('Rentals'),
            reservation_df.rename('Reservations')
        ], axis=1).fillna(0)
        
        if df.empty:
            return None
            
        title = 'Rental vs Reservation Revenue'
        if period == 'weekly':
            title = 'Weekly ' + title
        elif period == 'monthly':
            title = 'Monthly ' + title
        else:
            title = 'Yearly ' + title

        plt.figure(figsize=(9, 5))
        ax = df.plot.bar(
            color=[COLOR_PALETTE['primary'], COLOR_PALETTE['secondary']],
            edgecolor=COLOR_PALETTE['dark'],
            width=0.8,
            alpha=0.9
        )
        
        # Style enhancements
        ax.set_title(title, color=COLOR_PALETTE['dark'], fontsize=13, pad=15)
        ax.set_xlabel('Date', color=COLOR_PALETTE['dark'], fontsize=11)
        ax.set_ylabel('Amount (₱)', color=COLOR_PALETTE['dark'], fontsize=11)
        ax.tick_params(colors=COLOR_PALETTE['dark'], labelsize=9)
        ax.grid(True, linestyle='--', alpha=0.3, axis='y')
        ax.set_facecolor(COLOR_PALETTE['light'])
        plt.xticks(rotation=45, ha='right')
        plt.legend(title='Transaction Type', fontsize=9)
        plt.tight_layout()
        
        buffer = BytesIO()
        plt.savefig(buffer, format='png', facecolor='white', dpi=100, bbox_inches='tight')
        plt.close()
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    except Exception as e:
        print(f"Comparison Chart Error: {str(e)}")
        return None