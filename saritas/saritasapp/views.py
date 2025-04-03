# Standard library imports
from datetime import date, datetime, timedelta
from calendar import month_name

# Django core imports
from django.shortcuts import render, redirect, get_object_or_404, HttpResponse
from django.http import JsonResponse
from django.db.models import F, Q, Count, Sum
from django.db import transaction
from django.db.models.functions import TruncMonth, ExtractWeek, ExtractMonth, ExtractYear
from django.core.exceptions import ValidationError, PermissionDenied
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.admin.views.decorators import staff_member_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

# ReportLab imports (for PDF generation)
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

# Local imports
from .forms import (
    InventoryForm, CategoryForm, EventForm, ColorForm, SizeForm,
    StaffSignUpForm, AdminSignUpForm, LoginForm
)
from .models import (
    Customer, Inventory, Category, Rental, Reservation, User, WardrobePackage,
    Receipt, Color, Size, Staff, Event
)



@login_required
def add_inventory(request):
    categories = Category.objects.all()
    sizes = Size.objects.all() 
    colors = Color.objects.all()

    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES)
        if form.is_valid():
            inventory_item = form.save(commit=False)

            # Ensure reservation_price is set properly (if blank, default to zero)
            if inventory_item.reservation_price is None:
                inventory_item.reservation_price = 0.00

            inventory_item.save()
            return redirect('saritasapp:inventory_list')
        else:
            # Display error messages in the template if form is invalid
            return render(request, 'saritasapp/add_inventory.html', {
                'form': form,
                'categories': categories,
                'sizes': sizes,
                'colors': colors,
            })
    else:
        form = InventoryForm()

    return render(request, 'saritasapp/add_inventory.html', {
        'form': form,
        'categories': categories,
        'colors': colors,
        'sizes': sizes
    })



@login_required
def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('saritasapp:add_inventory')
    else:
        form = CategoryForm()
    
    return render(request, 'saritasapp/add_category.html', {'form': form})

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
    categories = Category.objects.all()
    colors = Color.objects.all()
    sizes = Size.objects.all()

    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            item = form.save(commit=False)
            item.purchase_price = float(request.POST.get('purchase_price', '0') or 0) 
            item.available = 'available' in request.POST  
            item.save()
            return redirect('saritasapp:inventory_list')
    else:
        form = InventoryForm(instance=item)

    return render(request, 'saritasapp/edit_inventory.html', {
        'form': form,
        'categories': categories,
        'colors': colors,
        'sizes': sizes,
        'item': item 
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
    
    if rental.status in ['Renting', 'Overdue']:
        rental.status = 'Returned'
        
        rental.inventory.quantity += 1  
        rental.inventory.save()  
        
        rental.save() 
        messages.success(request, f"{rental.inventory.name} has been marked as 'Returned'.")
    else:
        messages.warning(request, "This item has already been returned.")
    
    return redirect('saritasapp:view_customer', rental.customer.id)

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
from django.shortcuts import render
from django.db.models import Count, Sum
from django.contrib.auth.decorators import login_required
from django.db.models.functions import ExtractWeek, ExtractMonth, ExtractYear
import plotly.graph_objects as go
from datetime import datetime, timedelta
from .models import Rental, Customer, Inventory

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
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, "Successfully logged in!")

            # Redirect users based on role
            if user.is_superuser:
                return redirect('saritasapp:dashboard')  # Redirect to Django admin panel
            elif user.is_staff_user:
                return redirect('saritasapp:dashboard')  # Redirect staff to staff dashboard
            else:
                return redirect('customerapp:dashboard')  # Redirect customers to their dashboard
                
        else:
            messages.error(request, "Invalid username or password.")
    else:
        form = LoginForm()

    return render(request, 'saritasapp/signin.html', {'form': form})


# --- Dashboard View ---
@login_required
def dashboard(request):
    return render(request, 'saritasapp/dashboard.html')


# --- Logout View ---
@login_required
def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('saritasapp:sign_in')


@login_required
def receipt_view(request):
    return render(request, 'saritasapp/receipt.html')

@login_required
def notification_view(request):
    return render(request, 'saritasapp/notification.html')

@login_required
def reservation_view(request):

    return render(request, 'saritasapp/reservation.html')

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

@login_required
def rental_tracker(request):
    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    today = timezone.now().date()

    # Automatically update statuses
    with transaction.atomic():
        # Mark overdue rentals
        Rental.objects.filter(
            rental_end__lt=today,
            status="Renting"
        ).update(status="Overdue")
        
        # Mark newly active rentals (Approved → Renting when start date arrives)
        Rental.objects.filter(
            rental_start__lte=today,
            rental_end__gte=today,
            status="Approved"
        ).update(status="Renting")

    # Base query with optimized joins
    rentals = Rental.objects.select_related(
        'customer__user',
        'inventory__category'
    ).order_by('-rental_start')

    # Apply filters
    if status_filter:
        rentals = rentals.filter(status=status_filter)
        
    if start_date:
        rentals = rentals.filter(rental_start__gte=start_date)
        
    if end_date:
        rentals = rentals.filter(rental_end__lte=end_date)

    # Pagination
    page = request.GET.get('page', 1)
    paginator = Paginator(rentals, 25)  # Show 25 rentals per page
    
    try:
        rentals = paginator.page(page)
    except PageNotAnInteger:
        rentals = paginator.page(1)
    except EmptyPage:
        rentals = paginator.page(paginator.num_pages)

    # Get counts for all statuses
    status_counts = Rental.objects.aggregate(
        pending=Count('pk', filter=Q(status='Pending')),
        active=Count('pk', filter=Q(status='Renting')),
        returned=Count('pk', filter=Q(status='Returned')),
        overdue=Count('pk', filter=Q(status='Overdue'))
    )

    return render(request, 'saritasapp/rental_tracker.html', {
        'rentals': rentals,
        'today': today,
        'active_count': status_counts['active'],
        'returned_count': status_counts['returned'],
        'overdue_count': status_counts['overdue'],
        'pending_count': status_counts['pending'],
        'filter_status': status_filter,
        'filter_start_date': start_date,
        'filter_end_date': end_date,
    })

@staff_member_required
@login_required
def rental_approvals(request):
    # Get all pending rental requests with related data
    pending_rentals = Rental.objects.filter(
        status='Pending'
    ).select_related(
        'customer__user',
        'inventory'
    ).order_by('-created_at')  # Newest requests first
    
    # Counts for the dashboard
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
@login_required
def update_reservation(request, reservation_id, action):
    reservation = get_object_or_404(Reservation, id=reservation_id)
    
    try:
        if action == 'approve':
            reservation.approve(request.user)
            messages.success(request, f"Reservation #{reservation_id} approved successfully.")
        elif action == 'reject':
            reservation.reject(request.user, request.POST.get('reason', ''))
            messages.success(request, f"Reservation #{reservation_id} rejected.")
        elif action == 'complete':
            reservation.status = 'completed'
            reservation.save()
            
            # Return items to inventory
            reservation.item.quantity += reservation.quantity
            reservation.item.save()
            
            messages.success(request, f"Reservation #{reservation_id} marked as completed.")
        else:
            messages.error(request, "Invalid action requested.")
    except ValidationError as e:
        messages.error(request, str(e))
    
    return redirect('customerapp:view_reservations')


@staff_member_required
@login_required
def approve_rental(request, rental_id):
    rental = get_object_or_404(Rental, id=rental_id, status='Pending')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'approve':
            # Check inventory availability
            if rental.inventory.quantity <= 0:
                messages.error(request, 'Cannot approve - item is out of stock!')
                return redirect('saritasapp:rental_approvals')
            
            # Approve the rental
            rental.status = 'Approved'
            rental.approved_by = request.user
            rental.approved_at = timezone.now()
            
            # Reduce inventory
            rental.inventory.quantity -= 1
            rental.inventory.save()
            
            messages.success(request, f'Rental #{rental.id} approved successfully!')
            
        elif action == 'reject':
            rental.status = 'Rejected'
            rental.rejection_reason = request.POST.get('rejection_reason', '')
            messages.warning(request, f'Rental #{rental.id} has been rejected.')
        
        rental.save()
        return redirect('saritasapp:rental_approvals')
    
    # For GET requests, show approval form
    return render(request, 'saritasapp/approve_rental.html', {
        'rental': rental,
    })

@staff_member_required
@login_required
def approve_rental(request, rental_id, action):
    rental = get_object_or_404(Rental, id=rental_id, status='Pending')
    
    if action == 'approve':
        # Check inventory availability
        if rental.inventory.quantity <= 0:
            messages.error(request, 'Cannot approve - item is out of stock!')
            return redirect('saritasapp:rental_approvals')
        
        # Approve the rental
        rental.status = 'Approved'
        rental.approved_by = request.user
        rental.approved_at = timezone.now()
        
        # Reduce inventory
        rental.inventory.quantity -= 1
        rental.inventory.save()
        
        messages.success(request, f'Rental #{rental_id} approved successfully!')
    elif action == 'reject':
        rental.status = 'Rejected'
        messages.success(request, f'Rental #{rental_id} has been rejected.')
    
    rental.save()
    return redirect('saritasapp:rental_approvals')

#profile
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib import messages
from .models import User
from .forms import EditProfileForm

@login_required
def profile_view(request):
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

    return render(request, "saritasapp/profile.html", {"form": form, "user": user})

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

def packages(request):
    return render(request, 'saritasapp/package.html')

