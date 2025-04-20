# Standard library imports
from calendar import month_name
from datetime import date, datetime, timedelta

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
from django.db.models.functions import ExtractMonth, ExtractWeek, ExtractYear, TruncMonth
from django.http import HttpResponse, JsonResponse
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
    AddPackageItemForm, AdminSignUpForm, BulkPackageItemForm, CategoryForm, ColorForm, EditProfileForm, EventForm,
    InventoryForm, LoginForm, PackageItemForm, PackageReturnForm, SizeForm, StaffRentalApprovalForm, StaffSignUpForm,
    WardrobePackageForm, WardrobePackageItemForm,
    PackageCustomizationForm, CustomizePackageForm
)
from .models import (
    Branch, Category, Color, Customer, Event, Inventory, ItemType, Notification, PackageCustomization,
    Receipt, Rental, Reservation, Size, User, Venue,
    WardrobePackage, CustomizedWardrobePackage, WardrobePackageItem, WardrobePackageRental
)
from .utils import send_notification
from customerapp.tasks import notify_staff_about_rental_request


 # Make sure Venue model is imported

@login_required
def add_inventory(request):
    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                inventory_item = form.save(commit=False)
                
                # Additional checks for empty fields (redundant but safe)
                required_fields = ['name', 'branch', 'category', 'quantity', 'rental_price']
                for field in required_fields:
                    if not form.cleaned_data.get(field):
                        messages.error(request, f"{field.replace('_', ' ').title()} is required!")
                        return render(request, 'saritasapp/add_inventory.html', {
                            'form': form,
                            'categories': Category.objects.all(),
                            'colors': Color.objects.all(),
                            'sizes': Size.objects.all()
                        })
                
                # Set additional fields
                if hasattr(request.user, 'staff_profile'):
                    inventory_item.created_by = request.user
                    inventory_item.branch = request.user.staff_profile.branch
                
                inventory_item.save()
                messages.success(request, f"Successfully added {inventory_item.name}!")
                return redirect('saritasapp:inventory_list')
                
            except IntegrityError:
                messages.error(request, "This item already exists!")
            except Exception as e:
                messages.error(request, f"Error: {str(e)}")
        else:
            messages.error(request, "Please fill all required fields!")
    else:
        form = InventoryForm(user=request.user)
    
    return render(request, 'saritasapp/add_inventory.html', {
        'form': form,
        'categories': Category.objects.all(),
        'colors': Color.objects.all(),
        'sizes': Size.objects.all()
    })
@login_required
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

@login_required
def add_color(request):
    if request.method == 'POST':
        form = ColorForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('saritasapp:add_inventory')
    else:
        form = ColorForm()
    return render(request, 'saritasapp/add_color.html', {'form': form})

@login_required
def add_size(request):
    if request.method == 'POST':
        form = SizeForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('saritasapp:add_inventory')
    else:
        form = SizeForm()
    return render(request, 'saritasapp/add_size.html', {'form': form})

@login_required
def view_item(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    return render(request, 'saritasapp/view_item.html', {'item': item})

@login_required
def edit_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)

    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES, instance=item, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Inventory item updated successfully!')
            return redirect('saritasapp:inventory_list')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = InventoryForm(instance=item, user=request.user)

    return render(request, 'saritasapp/edit_inventory.html', {
        'form': form,
        'categories': Category.objects.all(),
        'colors': Color.objects.all(),
        'sizes': Size.objects.all(),
        'item': item
        # Removed item_types from context since we're using predefined choices
    })

@login_required
def delete_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    
    if request.method == 'POST':
        item.delete()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/confirm_delete.html', {'item': item})

@login_required
def inventory_view(request):
    categories = Category.objects.all()
    colors = Color.objects.all()
    sizes = Size.objects.all()

    selected_category = request.GET.get('category', '')
    selected_color = request.GET.get('color', '')
    selected_size = request.GET.get('size', '')
    sort = request.GET.get('sort', '')

    inventory_items = Inventory.objects.all()

    if selected_category:
        inventory_items = inventory_items.filter(category_id=selected_category)
    if selected_color:
        inventory_items = inventory_items.filter(color_id=selected_color)
    if selected_size:
        inventory_items = inventory_items.filter(size_id=selected_size)

    if sort == 'name_asc':
        inventory_items = inventory_items.order_by('name')
    elif sort == 'name_desc':
        inventory_items = inventory_items.order_by('-name')
    elif sort == 'price_asc':
        inventory_items = inventory_items.order_by('purchase_price')
    elif sort == 'price_desc':
        inventory_items = inventory_items.order_by('-purchase_price')

    return render(request, 'saritasapp/inventory.html', {
        'categories': categories,
        'colors': colors,
        'sizes': sizes,
        'inventory_items': inventory_items,
        'selected_category': selected_category,
        'selected_color': selected_color,
        'selected_size': selected_size,
        'sort': sort
    })

from django.shortcuts import render
from django.db import transaction
from django.utils import timezone
from .models import Rental
import logging

# Create a logger instance
logger = logging.getLogger(__name__)

@login_required
def rental_tracker(request):
    # Extract filter values from GET parameters
    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    today = timezone.now().date()

    # Apply filters to rental query
    rentals = Rental.objects.all()

    if status_filter:
        rentals = rentals.filter(status=status_filter)

    # Handle date filters if provided
    if start_date:
        rentals = rentals.filter(rental_start__gte=start_date)
    if end_date:
        rentals = rentals.filter(rental_end__lte=end_date)

    with transaction.atomic():
        # Only mark as overdue if the rental's item quantity was properly decremented
        overdue_rentals = Rental.objects.filter(
            rental_end__lt=today,
            status="Renting"
        )

        for rental in overdue_rentals:
            # Verify the item was actually checked out (inventory decremented)
            if not rental.inventory_was_decremented:
                logger.warning(f"Overdue rental {rental.id} never had inventory decremented.")
                continue
                
            rental.status = "Overdue"
            rental.save()

        # Only mark as "Renting" if the quantity was decremented during approval
        approved_rentals = Rental.objects.filter(
            rental_start__lte=today,
            rental_end__gte=today,
            status="Approved"
        )

        for rental in approved_rentals:
            rental.status = "Renting"
            rental.save()

    # Render the rental tracker page with filtered rentals
    return render(request, 'saritasapp/rental_tracker.html', {
        'rentals': rentals
    })



@staff_member_required
@login_required
def rental_approvals(request):
    pending_rentals = Rental.objects.filter(status='Pending').select_related(
        'customer__user', 'inventory').order_by('-created_at')

    stats = {
        'pending': pending_rentals.count(),
        'approved': Rental.objects.filter(status='Approved').count(),
        'rejected': Rental.objects.filter(status='Rejected').count(),
    }

    return render(request, 'saritasapp/rental_approvals.html', {
        'pending_rentals': pending_rentals,
        'stats': stats,
    })

@staff_member_required
@login_required
def approve_or_reject_rental(request, rental_id, action):
    rental = get_object_or_404(Rental, pk=rental_id)

    try:
        if action == 'approve':
            # This now includes the quantity decrement
            rental.approve(request.user)
            action_message = 'approved'
        elif action == 'reject':
            reason = request.POST.get('rejection_reason', '')
            rental.reject(request.user, reason)
            action_message = 'rejected'
        else:
            return redirect('saritasapp:rental_approvals')
    except ValidationError as e:
        messages.error(request, str(e))
        return redirect('saritasapp:rental_approvals')
    except Exception as e:
        logger.error(f"Error processing rental {action}: {str(e)}")
        messages.error(request, "An error occurred processing this request")
        return redirect('saritasapp:rental_approvals')

    # Notifications
    Notification.objects.create(
        user=rental.customer.user,
        notification_type=f'rental_{action_message}',
        rental=rental,
        message=f"Your rental for {rental.inventory.name} has been {action_message}!", 
        is_read=False
    )

    messages.success(request, f"Rental successfully {action_message}!")
    return redirect('saritasapp:rental_approvals')


@staff_member_required
def view_reservations(request):
    status = request.GET.get('status', 'all')
    
    reservations = Reservation.objects.select_related(
        'item',
        'customer__user',
        'approved_by'
    ).order_by('-created_at')
    
    if status != 'all':
        reservations = reservations.filter(status=status)
    
    context = {
        'reservations': reservations,
        'status': status,
        'status_choices': Reservation.STATUS_CHOICES,
    }
    return render(request, 'saritasapp/view_reservation.html', context)


@staff_member_required
def update_reservation(request, pk, action):
    reservation = get_object_or_404(Reservation, pk=pk)

    if request.method == 'POST':
        if action == 'approve':
            reservation.status = 'approved'
            reservation.approved_by = request.user
            Notification.objects.create(
                user=reservation.customer.user,
                notification_type='reservation_approved',
                reservation=reservation,
                message=f"Your reservation for '{reservation.item.name}' has been approved."
            )
        elif action == 'reject':
            reservation.status = 'rejected'
            reservation.approved_by = request.user
            Notification.objects.create(
                user=reservation.customer.user,
                notification_type='reservation_rejected',
                reservation=reservation,
                message=f"Your reservation for '{reservation.item.name}' has been rejected."
            )
        elif action == 'complete':
            reservation.status = 'completed'
            Notification.objects.create(
                user=reservation.customer.user,
                notification_type='reservation_completed',
                reservation=reservation,
                message=f"Your reservation for '{reservation.item.name}' has been marked as completed."
            )
        reservation.save()

    return redirect('saritasapp:view_reservations')


@staff_member_required
@login_required
def approve_rental(request, rental_id, action):
    rental = get_object_or_404(Rental, id=rental_id, status='Pending')

    try:
        with transaction.atomic():
            if action == 'approve':
                # Check inventory availability
                if rental.inventory.quantity <= 0:
                    messages.error(request, f'Cannot approve - {rental.inventory.name} is out of stock!')
                    return redirect('saritasapp:rental_approvals')

                # Approve the rental
                rental.status = 'Approved'
                rental.approved_by = request.user
                rental.approved_at = timezone.now()

                # Reduce inventory
                rental.inventory.quantity -= 1
                rental.inventory.save()

                # Send approval notification
                send_notification(
                    user=rental.customer.user,
                    notification_type='rental_approved',
                    rental=rental,
                    message=f"Your rental request for {rental.inventory.name} has been approved!"
                )

                messages.success(request, f'Rental #{rental_id} approved successfully!')

            elif action == 'reject':
                rental.status = 'Rejected'
                rental.approved_by = request.user
                rental.rejection_reason = request.POST.get('rejection_reason', '')

                # Send rejection notification
                send_notification(
                    user=rental.customer.user,
                    notification_type='rental_rejected',
                    rental=rental,
                    message=f"Your rental request for {rental.inventory.name} has been rejected. Reason: {rental.rejection_reason}"
                )

                messages.warning(request, f'Rental #{rental_id} has been rejected.')

            rental.save()

    except Exception as e:
        messages.error(request, f'Error processing request: {str(e)}')

    return redirect('saritasapp:rental_approvals')

@staff_member_required
@login_required
def rental_detail(request, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)
    
    # Get last rental excluding current one
    last_rental = None
    if rental.customer:
        last_rental = rental.customer.rentals.exclude(id=rental.id).order_by('-created_at').first()
    
    return render(request, 'saritasapp/rental_detail.html', {
        'rental': rental,
        'last_rental': last_rental
    })

@login_required
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

@login_required
def view_customer(request, customer_id):
    customer = get_object_or_404(Customer.objects.select_related('user'), id=customer_id)
    
    # Automatically update overdue rentals
    today = now().date()
    rentals = Rental.objects.filter(customer=customer)
    rentals.filter(status="Renting", rental_end__lt=today).update(status="Overdue")

    return render(request, 'saritasapp/view_customer.html', {
        'customer': customer,
        'rentals': rentals,
    })

@login_required
def return_rental(request, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)
    
    if request.method == 'POST':
        if rental.status in ['Renting', 'Overdue']:
            rental.mark_as_returned()
            messages.success(
                request,
                f"{rental.inventory.name} has been returned. "
                f"Deposit of ₱{rental.deposit} will be refunded."
            )
            return redirect('saritasapp:view_customer', rental.customer.id)
        else:
            messages.warning(request, "This item cannot be returned.")
            return redirect('saritasapp:view_customer', rental.customer.id)
    
    # For GET requests, show confirmation page
    return render(request, 'saritasapp/confirm_return.html', {
        'rental': rental,
        'rental_cost': rental.inventory.rental_price * rental.duration_days,
        'deposit': rental.deposit
    })

# views.py
@login_required
def manage_staff(request):
    # Get all staff users with their related staff profiles
    staff_list = User.objects.filter(
        role='staff'
    ).select_related('staff_profile').order_by('last_name', 'first_name')
    
    context = {
        'staff_list': staff_list,
        'user': request.user
    }
    return render(request, 'saritasapp/manage_staff.html', context)

#data_analysis


@login_required
def data_analysis(request):
    # Total rentals and customers
    total_rentals = Rental.objects.count()
    total_customers = Customer.objects.count()

    # Most rented items
    most_rented_items = (
        Inventory.objects.annotate(rental_count=Count('rental'))
        .order_by('-rental_count')[:5]
    )

    # Get the last 5 weeks dynamically
    today = datetime.today()
    last_5_weeks = [(today - timedelta(weeks=i)).isocalendar()[1] for i in range(5)]
    
    # Weekly rentals & income (last 5 weeks)
    weekly_rentals = (
        Rental.objects.annotate(week=ExtractWeek('rental_start'))
        .filter(week__in=last_5_weeks)
        .values('week')
        .annotate(
            count=Count('id'),
            income=Sum('inventory__rental_price')
        )
        .order_by('week')
    )

    # Monthly rentals & income (full 12 months)
    month_names = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    
    monthly_rentals = {month: {'count': 0, 'income': 0} for month in month_names}
    monthly_data = (
        Rental.objects.annotate(month=ExtractMonth('rental_start'))
        .values('month')
        .annotate(
            count=Count('id'),
            income=Sum('inventory__rental_price')
        )
    )

    for entry in monthly_data:
        month_index = entry['month'] - 1
        month_name = month_names[month_index]
        monthly_rentals[month_name] = {
            'count': entry['count'],
            'income': entry['income'] or 0,
        }

    monthly_rentals_list = [{'month': key, **value} for key, value in monthly_rentals.items()]

    # Yearly rentals & income (all available years)
    yearly_rentals = (
        Rental.objects.annotate(year=ExtractYear('rental_start'))
        .values('year')
        .annotate(
            count=Count('id'),
            income=Sum('inventory__rental_price')
        )
        .order_by('year')
    )

    # Function to determine max digits dynamically
    def get_max_digits(data, key):
        max_value = max((entry[key] or 0) for entry in data) if data else 0
        max_digits = len(str(max_value)) + 1  # One extra digit
        return max_digits

    # Apply max digits formatting
    max_digits_weekly = get_max_digits(weekly_rentals, 'count')
    max_digits_monthly = get_max_digits(monthly_rentals_list, 'count')
    max_digits_yearly = get_max_digits(yearly_rentals, 'count')

    # Function to create bar charts with dynamic X-axis scaling
    def create_chart(x_values, y_values, title, color, y_label):
        max_digits = len(str(max(y_values) if y_values else 0)) + 1
        y_max = 10 ** max_digits  # Round up based on max digits

        fig = go.Figure()
        fig.add_trace(go.Bar(x=x_values, y=y_values, name=title, marker_color=color))

        fig.update_layout(
            title=title,
            xaxis_title="Time Period",
            yaxis_title=y_label,
            yaxis=dict(range=[0, y_max])
        )
        return fig.to_html(full_html=False)

    # Income charts
    weekly_income_chart = create_chart(
        [entry['week'] for entry in weekly_rentals],
        [entry['income'] for entry in weekly_rentals],
        "Weekly Income", 'green', "Income (₱)"
    )
    monthly_income_chart = create_chart(
        [entry['month'] for entry in monthly_rentals_list],
        [entry['income'] for entry in monthly_rentals_list],
        "Monthly Income", 'blue', "Income (₱)"
    )
    yearly_income_chart = create_chart(
        [entry['year'] for entry in yearly_rentals],
        [entry['income'] for entry in yearly_rentals],
        "Yearly Income", 'red', "Income (₱)"
    )

    # Rental count charts
    weekly_rental_chart = create_chart(
        [entry['week'] for entry in weekly_rentals],
        [entry['count'] for entry in weekly_rentals],
        "Weekly Rentals", 'orange', "Number of Rentals"
    )
    monthly_rental_chart = create_chart(
        [entry['month'] for entry in monthly_rentals_list],
        [entry['count'] for entry in monthly_rentals_list],
        "Monthly Rentals", 'purple', "Number of Rentals"
    )
    yearly_rental_chart = create_chart(
        [entry['year'] for entry in yearly_rentals],
        [entry['count'] for entry in yearly_rentals],
        "Yearly Rentals", 'brown', "Number of Rentals"
    )

    context = {
        'total_rentals': total_rentals,
        'total_customers': total_customers,
        'most_rented_items': most_rented_items,
        'weekly_income_chart': weekly_income_chart,
        'monthly_income_chart': monthly_income_chart,
        'yearly_income_chart': yearly_income_chart,
        'weekly_rental_chart': weekly_rental_chart,
        'monthly_rental_chart': monthly_rental_chart,
        'yearly_rental_chart': yearly_rental_chart,
    }

    return render(request, 'saritasapp/data_analysis.html', context)


#calnder
@login_required
def calendar_view(request):
    return render(request, "saritasapp/calendar.html")

@login_required
def ongoing_events(request):
    events = Event.objects.filter(start_date__lte=now().date(), end_date__gte=now().date())
    return render(request, "saritasapp/ongoing_events.html", {"events": events})

@login_required
def upcoming_events(request):
    events = Event.objects.filter(start_date__gt=now().date())
    return render(request, "saritasapp/upcoming_events.html", {"events": events})

@login_required
def past_events(request):
    events = Event.objects.filter(end_date__lt=now().date())
    return render(request, "saritasapp/past_events.html", {"events": events})

@login_required
def create_event(request):
    if request.method == "POST":
        title = request.POST.get("title")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        notes = request.POST.get("notes")
        Event.objects.create(title=title, start_date=start_date, end_date=end_date, notes=notes)
        return redirect("calendar")
    return render(request, "saritasapp/create_event.html")

@login_required
def view_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, "saritasapp/view_event.html", {"event": event})

@login_required
def get_events(request):
    events = Event.objects.all()
    events_data = [
        {
            "id": event.id,
            "title": event.title,
            "start": event.start_date.strftime("%Y-%m-%d"),
            "end": event.end_date.strftime("%Y-%m-%d"),
        }
        for event in events
    ]
    return JsonResponse(events_data, safe=False)



@login_required
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
@login_required
def dashboard(request):
    return render(request, 'saritasapp/dashboard.html')


# --- Logout View ---
@login_required
def logout_view(request):
    logout(request)
    return redirect('customerapp:homepage')


@login_required
def receipt_view(request):
    return render(request, 'saritasapp/receipt.html')


#Receipt
@login_required
def update_receipt(request, receipt_id):
    """Update receipt details and ensure new fields are saved properly."""
    receipt = get_object_or_404(Receipt, id=receipt_id)

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

            return redirect("saritasapp:receipt-detail", receipt_id=receipt.id)

        except ValueError as e:
            return render(request, "saritasapp/receipt.html", {
                "receipt": receipt,
                "error": f"Invalid input: {str(e)}"
            })

    return render(request, "saritasapp/receipt.html", {"receipt": receipt})

@login_required
def generate_receipt_pdf(request, receipt_id):
    """Generate and download a PDF receipt with all details."""
    receipt = get_object_or_404(Receipt, id=receipt_id)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="receipt_{receipt_id}.pdf"'

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


@login_required
def wardrobe_package_view(request, package_id):
    package = get_object_or_404(WardrobePackage, id=package_id)

    # Organizing inventory by category for better display
    inventory = {}
    items = Inventory.objects.filter(package=package)
    for item in items:
        if item.category not in inventory:
            inventory[item.category] = []
        inventory[item.category].append(item)

    # Calculate total price including refundable deposit
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

@login_required
def wardrobe_package_list(request):
    packages = WardrobePackage.objects.filter(status='active')  # Only show active packages
    return render(request, 'saritasapp/wardrobe_package_list.html', {'packages': packages})

@login_required
def wardrobe_package_view(request, package_id):
    package = get_object_or_404(WardrobePackage, id=package_id)
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

        # You can optionally save the selected package to the customer's record here
        # For example:
        # CustomerPackage.objects.create(customer_id=customer_id, package=package, total_price=total_price)

        context['total_price'] = total_price
        context['success'] = "Package selected successfully!"

    return render(request, 'saritasapp/wardrobe_package.html', context)

#made to order
from django.shortcuts import render, redirect, get_object_or_404
from .models import Receipt

@login_required
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

@login_required
def receipt_detail(request, receipt_id):
    """Display receipt details."""
    receipt = get_object_or_404(Receipt, id=receipt_id) 
    return render(request, "saritasapp/receipt.html", {"receipt": receipt})

#calnder
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from .models import Event
from django.http import JsonResponse

@login_required
def calendar_view(request):
    events = Event.objects.all()
    return render(request, "saritasapp/calendar.html", {"events": events})

@login_required
def view_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, "saritasapp/view_event.html", {"event": event})

@login_required
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

@login_required
def ongoing_events(request):
    events = Event.objects.filter(start_date__lte=now().date(), end_date__gte=now().date())
    return render(request, "saritasapp/ongoing_events.html", {"events": events})

@login_required
def upcoming_events(request):
    events = Event.objects.filter(start_date__gt=now().date()) 
    return render(request, "saritasapp/upcoming_events.html", {"events": events})

@login_required
def past_events(request):
    events = Event.objects.filter(end_date__lt=now().date())  
    return render(request, "saritasapp/past_events.html", {"events": events})

@login_required
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


@login_required
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

@login_required
def sign_out(request):
    """Logs out the user and redirects to logout page"""
    if request.method == "POST" or request.method == "GET":  # ✅ Allow both GET & POST
        logout(request)
        return redirect("saritasapp:logout")  # ✅ Redirect to logout confirmation page
    
    return redirect("saritasapp:profile")  # If another method is used

@login_required

def edit_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event)
        if form.is_valid():
            form.save()
            messages.success(request, 'Event updated successfully.')
            return redirect('saritasapp:view_event', event_id=event.id)
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = EventForm(instance=event)

    return render(request, 'saritasapp/edit_event.html', {'form': form, 'event': event})

def delete_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)

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

def wedding_packages(request):
    if request.method == 'POST':
        # Handle custom venues from DB if needed (or from session)
        custom_venues = {v.venue_id: v.base_price for v in Venue.objects.filter(is_custom=True, created_by=request.user)}

        # Get selected venue
        venue_id = request.POST.get('venue')
        venue_price = 0
        venue_name = ""

        if venue_id and venue_id.startswith('custom_'):
            venue_price = custom_venues.get(venue_id, 0)
            venue_name = request.POST.get(f'venue_{venue_id}_name', 'Custom Venue')
        else:
            # Handle predefined venues from the DB
            try:
                venue_obj = Venue.objects.get(venue_id=venue_id)
                venue_name = venue_obj.name
                venue_price = venue_obj.base_price
            except Venue.DoesNotExist:
                venue_name = "Unknown"
                venue_price = 0

        # Collect other data
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

        # Save to session
        request.session['wedding_customization'] = data
        return redirect('wedding_confirmation')

    return render(request, 'saritasapp/wedding_packages.html')


def wedding_confirmation(request):
    customization = request.session.get('wedding_customization', {})
    return render(request, 'saritasapp/wedding_confirmation.html', {
        'customization': customization
    })


def add_custom_venue(request):
    if request.method == 'POST':
        name = request.POST.get('name')
        price = request.POST.get('price')

        if name and price:
            # Generate a unique venue ID using a prefix and timestamp
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
def additional_services(request):
    if request.method == 'POST':
        request.session['additional_services'] = {
            'services': request.POST.getlist('services'),
            'duration': request.POST.get('duration'),
            'requests': request.POST.get('special_requests')
        }
        return redirect('additional_services')
    return render(request, 'saritasapp/additional_services.html')

# Debut Confirmation View
def debut_confirmation(request):
    customization = request.session.get('debut_customization', {})
    # Add price calculation logic if needed
    return render(request, 'saritasapp/debut_confirmation.html', {
        'customization': customization
    })

# Additional Services Confirmation View
def additional_confirmation(request):
    services = request.session.get('additional_services', {})
    # Add price calculation logic if needed
    return render(request, 'saritasapp/additional_services.html', {
        'services': services
    })

#wardrobe packages view
class WardrobePackageForm(forms.ModelForm):
    class Meta:
        model = WardrobePackage
        fields = [
            'name', 'tier', 'description', 'base_price', 'deposit_price',
            'discount', 'status', 'min_rental_days', 'includes_accessories'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class WardrobePackageItemForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageItem
        fields = ['inventory_item', 'quantity']

    def __init__(self, *args, item_type=None, **kwargs):
        super().__init__(*args, **kwargs)
        if item_type:
            self.fields['inventory_item'].queryset = Inventory.objects.filter(
                available=True,
                item_type=item_type
            ).order_by('name')

    def clean(self):
        cleaned_data = super().clean()
        inventory_item = cleaned_data.get('inventory_item')
        quantity = cleaned_data.get('quantity')

        if inventory_item and quantity:
            if quantity > inventory_item.quantity:
                raise ValidationError(
                    f"Only {inventory_item.quantity} available in stock"
                )
        return cleaned_data


class PackageCustomizationForm(forms.ModelForm):
    class Meta:
        model = PackageCustomization
        fields = ['action', 'original_item', 'inventory_item', 'new_quantity', 'price_adjustment', 'notes']
        widgets = {
            'action': forms.RadioSelect(),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, package=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if package:
            self.fields['original_item'].queryset = package.package_items.all()
            self.fields['inventory_item'].queryset = Inventory.objects.filter(available=True)


class CustomizePackageForm(forms.ModelForm):
    class Meta:
        model = CustomizedWardrobePackage
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describe your customization requests...'
            }),
        }


class StaffRequiredMixin(LoginRequiredMixin, UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff


class WardrobePackageListView(StaffRequiredMixin, ListView):
    model = WardrobePackage
    template_name = 'saritasapp/wardrobe_package_list.html'
    context_object_name = 'packages'


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

    def validate_package_completeness(self, package):
        """Check if package has all required item types based on its tier"""
        # Define required item types for each package tier
        tier_requirements = {
            'A': ['bridal_gown', 'groom_tuxedo'],
            'B': ['bridal_gown', 'groom_tuxedo', 'maid_honor', 'bestman'],
            'C': ['bridal_gown', 'groom_tuxedo', 'maid_honor', 'bestman',
                 'mother_gown', 'father_attire'],
            'custom': []  # Custom packages have no required items
        }

        # Get item types already in the package
        existing_types = set(
            package.package_items
            .select_related('inventory_item__item_type')
            .values_list('inventory_item__item_type__name', flat=True)
        )

        # Check for missing required types
        missing_types = []
        for required_type in tier_requirements.get(package.tier, []):
            if required_type not in existing_types:
                missing_types.append(required_type)

        return missing_types

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = self.object
        
        # Package completeness check
        missing_required = self.validate_package_completeness(package)
        context['missing_required'] = missing_required
        context['package_complete'] = not missing_required
        
        # Group items by type for better display
        items_by_type = {}
        for item in package.package_items.select_related('inventory_item__item_type').all():
            item_type = item.inventory_item.item_type.name
            if item_type not in items_by_type:
                items_by_type[item_type] = []
            items_by_type[item_type].append(item)
        
        context['items_by_type'] = items_by_type
        
        # Add item types for add item form
        context['item_types'] = ItemType.objects.all()
        
        return context


class AddPackageItemView(StaffRequiredMixin, TemplateView):
    template_name = 'saritasapp/add_package_item.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        package = get_object_or_404(WardrobePackage, pk=self.kwargs['package_id'])
        
        # Get all item types with their available items
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
        package = get_object_or_404(WardrobePackage, pk=kwargs['package_id'])
        selected_items = request.POST.get('selected_items', '').split(',')
        
        if not selected_items or selected_items[0] == '':
            messages.error(request, "No items selected")
            return redirect('saritasapp:add_package_item', package_id=package.pk)
        
        try:
            with transaction.atomic():
                # Validate only one item per type is selected
                selected_types = set()
                for item_id in selected_items:
                    item = Inventory.objects.get(id=item_id)
                    if item.item_type in selected_types:
                        messages.error(request, f"Can only select one {item.item_type.get_name_display()} per package")
                        return redirect('saritasapp:add_package_item', package_id=package.pk)
                    selected_types.add(item.item_type)
                
                # Create package items
                for item_id in selected_items:
                    quantity = int(request.POST.get(f'quantity_{item_id}', 1))
                    label = request.POST.get(f'label_{item_id}', '')
                    
                    item = Inventory.objects.get(
                        id=item_id,
                        available=True,
                        quantity__gte=quantity
                    )
                    
                    WardrobePackageItem.objects.create(
                        package=package,
                        inventory_item=item,
                        quantity=quantity,
                        label=label,
                        is_required=True
                    )
                
                messages.success(request, f"Added {len(selected_items)} items to package")
                return redirect('saritasapp:wardrobe_package_detail', pk=package.pk)
                
        except Inventory.DoesNotExist:
            messages.error(request, "One or more items are no longer available")
        except Exception as e:
            messages.error(request, f"Error adding items: {str(e)}")
        
        return redirect('saritasapp:add_package_item', package_id=package.pk)

class AddPackageItemSubmitView(StaffRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        package = get_object_or_404(WardrobePackage, pk=kwargs['package_id'])
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
        
        return redirect('saritasapp:add_package_item', package_id=package.pk)

class EditPackageItemView(StaffRequiredMixin, UpdateView):
    model = WardrobePackageItem
    form_class = WardrobePackageItemForm
    template_name = 'saritasapp/edit_package_item.html'
    
    def get_success_url(self):
        return reverse('saritasapp:wardrobe_package_detail', kwargs={'pk': self.object.package.pk})
    
class FilterInventoryItemsView(StaffRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        item_type_id = request.GET.get('item_type')
        package_id = request.GET.get('package')
        
        # Get items already in package
        existing_item_ids = []
        if package_id:
            existing_item_ids = WardrobePackageItem.objects.filter(
                package_id=package_id
            ).values_list('inventory_item_id', flat=True)
        
        # Filter available items by type
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

# Staff-only view to see pending rentals
@login_required
@user_passes_test(lambda u: u.is_staff)
def staff_rental_requests(request):
    pending_rentals = WardrobePackageRental.objects.filter(status='pending').order_by('event_date')
    return render(request, 'staff/rental_requests.html', {
        'pending_rentals': pending_rentals
    })

# Staff approval/rejection
@login_required
@user_passes_test(lambda u: u.is_staff)
def staff_manage_rental(request, rental_id):
    rental = get_object_or_404(WardrobePackageRental, pk=rental_id)
    
    if request.method == 'POST':
        form = StaffRentalApprovalForm(request.POST, instance=rental)
        if form.is_valid():
            rental = form.save(commit=False)
            rental.staff = request.user  # Assign staff member handling this
            rental.save()
            
            messages.success(request, f"Rental #{rental.id} updated to {rental.get_status_display()}!")
            return redirect('staff_rental_requests')
    else:
        form = StaffRentalApprovalForm(instance=rental)
    
    return render(request, 'staff/manage_rental.html', {
        'rental': rental,
        'form': form
    })

@login_required
@user_passes_test(lambda u: u.is_staff)
def process_return(request, rental_id):
    rental = get_object_or_404(WardrobePackageRental, pk=rental_id)
    
    if request.method == 'POST':
        form = PackageReturnForm(request.POST, instance=rental)
        if form.is_valid():
            rental = form.save(commit=False)
            rental.status = 'returned'
            rental.staff = request.user  # Assign staff member processing return
            rental.save()
            
            messages.success(request, f"Package #{rental.id} marked as returned!")
            return redirect('staff_dashboard')
    else:
        form = PackageReturnForm(instance=rental)
    
    return render(request, 'staff/process_return.html', {
        'form': form,
        'rental': rental
    })

@staff_member_required
def package_rental_approvals(request):
    status_filter = request.GET.get('status', 'pending')
    
    rentals = WardrobePackageRental.objects.select_related(
        'customer__user', 'package'
    ).order_by('-created_at')

    if status_filter != 'all':
        rentals = rentals.filter(status=status_filter)

    stats = {
        'pending': WardrobePackageRental.objects.filter(status='pending').count(),
        'approved': WardrobePackageRental.objects.filter(status='approved').count(),
        'rejected': WardrobePackageRental.objects.filter(status='rejected').count(),
        'completed': WardrobePackageRental.objects.filter(status='completed').count(),
        'returned': WardrobePackageRental.objects.filter(status='returned').count(),
    }

    return render(request, 'saritasapp/package_rental_approvals.html', {
        'rentals': rentals,
        'stats': stats,
        'status_filter': status_filter,
    })

@staff_member_required
def update_package_rental_status(request, rental_id, action):
    rental = get_object_or_404(WardrobePackageRental, pk=rental_id)
    
    try:
        with transaction.atomic():
            if action == 'approve':
                rental.approve(request.user)
                action_message = 'approved'
            elif action == 'reject':
                reason = request.POST.get('notes', '')
                rental.reject(request.user, reason)
                action_message = 'rejected'
            elif action == 'complete':
                rental.mark_as_completed(request.user)
                action_message = 'completed'
            elif action == 'return':
                return_date = request.POST.get('actual_return_date')
                notes = request.POST.get('notes', '')
                
                if return_date:
                    return_date = timezone.datetime.strptime(return_date, '%Y-%m-%d').date()
                
                rental.mark_as_returned(
                    request.user,
                    actual_return_date=return_date
                )
                if notes:
                    rental.notes = notes
                    rental.save()
                action_message = 'returned'
            else:
                messages.error(request, "Invalid action")
                return redirect('saritasapp:package_rental_approvals')

            # Create notification
            Notification.objects.create(
                user=rental.customer.user,
                notification_type=f'package_rental_{action_message}',
                message=f"Your package rental for {rental.package.name} has been {action_message}!",
                is_read=False
            )

            messages.success(request, f"Package rental successfully {action_message}!")
    except ValidationError as e:
        messages.error(request, str(e))
    except Exception as e:
        logger.error(f"Error updating package rental status: {str(e)}")
        messages.error(request, "An error occurred while updating the rental status")

    return redirect('saritasapp:package_rental_approvals')