from django.shortcuts import render, redirect, get_object_or_404
from .forms import InventoryForm, CategoryForm, RentalForm, CustomerForm
from .models import Customer, Inventory, Category, Rental, User
from django.utils.timezone import now
from django.db.models import F, Q  ,Count , Sum#new
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages
from datetime import date
from calendar import month_name#new
from django.db.models.functions import TruncMonth#new
from django.utils.timezone import now #new
from datetime import timedelta #new
from .models import Rental, Customer, Inventory #new
from django.db.models.functions import ExtractWeek, ExtractMonth, ExtractYear #new
# for calendar
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from .models import Event
from django.http import JsonResponse
from datetime import date

def add_inventory(request):
    categories = Category.objects.all()

    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES)
        if form.is_valid():
            inventory_item = form.save(commit=False)
            inventory_item.purchase_price = float(request.POST.get('purchase_price', '0') or 0)  # Ensure numerical conversion
            inventory_item.available = 'available' in request.POST  # Proper boolean handling
            inventory_item.save()
            return redirect('saritasapp:inventory_list')
    else:
        form = InventoryForm()

    return render(request, 'saritasapp/add_inventory.html', {'form': form, 'categories': categories})

def inventory_list(request):
    categories = Category.objects.all()
    selected_category = request.GET.get('category', '')

    if selected_category:
        inventory_items = Inventory.objects.filter(category_id=selected_category)
    else:
        inventory_items = Inventory.objects.all()

    return render(request, 'saritasapp/inventory.html', {
        'categories': categories,
        'inventory_items': inventory_items,
        'selected_category': selected_category,
    })


def add_category(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('saritasapp:add_inventory')
    else:
        form = CategoryForm()
    
    return render(request, 'saritasapp/add_category.html', {'form': form})

def view_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    return render(request, 'saritasapp/view_inventory.html', {'item': item})

def edit_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    categories = Category.objects.all()

    if request.method == 'POST':
        form = InventoryForm(request.POST, request.FILES, instance=item)
        if form.is_valid():
            item = form.save(commit=False)
            item.purchase_price = float(request.POST.get('purchase_price', '0') or 0)  # Ensure numerical conversion
            item.available = 'available' in request.POST  # Proper boolean handling
            item.save()
            return redirect('saritasapp:inventory_list')
    else:
        form = InventoryForm(instance=item)

    return render(request, 'saritasapp/edit_inventory.html', {
        'form': form,
        'categories': categories,
        'item': item  # ✅ Pass the item to the template
    })

def delete_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    
    if request.method == 'POST':
        item.delete()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/confirm_delete.html', {'item': item})

def inventory_view(request):
    categories = Category.objects.all()
    selected_category = request.GET.get('category', '')

    inventory_items = Inventory.objects.filter(category_id=selected_category) if selected_category else Inventory.objects.all()

    return render(request, 'saritasapp/inventory.html', {
        'categories': categories,
        'inventory_items': inventory_items,
        'selected_category': selected_category
    })

def rent_item(request, inventory_id):
    inventory_item = get_object_or_404(Inventory, id=inventory_id)
    customers = Customer.objects.all()
    
    if request.method == "POST":
        customer_id = request.POST.get("customer")
        rental_start = request.POST.get("rental_start")
        rental_end = request.POST.get("rental_end")

        customer = get_object_or_404(Customer, id=customer_id)

        # Ensure there are available items to rent
        if inventory_item.quantity > 0:
            rental = Rental.objects.create(
                customer=customer,
                inventory=inventory_item,
                rental_start=rental_start,
                rental_end=rental_end,
                status="Rented",
                deposit=inventory_item.rental_price * 2  # Example deposit logic
            )

            # Reduce inventory quantity
            inventory_item.quantity -= 1
            inventory_item.save()

            messages.success(request, f"{inventory_item.name} has been rented to {customer.first_name}.")
            return redirect("saritasapp:view_customer", customer_id=customer.id)
        else:
            messages.error(request, "This item is out of stock.")

    context = {
        "inventory_item": inventory_item,
        "customers": customers,
        "today": date.today(),
    }
    return render(request, "saritasapp/rent_item.html", context)

def add_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, "Customer added successfully!")
            return redirect("saritasapp:customer_list")  # Change to appropriate redirect
        else:
            messages.error(request, "There was an error adding the customer.")
    else:
        form = CustomerForm()

    return render(request, "saritasapp/add_customer.html", {"form": form})

def customer_list(request):
    query = request.GET.get('q', '')  # Get search query
    status_filter = request.GET.get('status', 'all')  # Get status filter

    customers = Customer.objects.all()

    # Apply search filter
    if query:
        customers = customers.filter(first_name__icontains=query) | customers.filter(last_name__icontains=query)

    # Apply rental status filter
    if status_filter == 'renting':
        customers = customers.filter(rental__status="Rented").distinct()
    elif status_filter == 'returned':
        customers = customers.filter(rental__status="Returned").distinct()

    return render(request, 'saritasapp/customer_list.html', {'customers': customers, 'filter_status': status_filter})

def view_customer(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    rentals = Rental.objects.filter(customer=customer)

    return render(request, 'saritasapp/view_customer.html', {
        'customer': customer,
        'rentals': rentals,
    })
def return_rental(request, rental_id):
    rental = get_object_or_404(Rental, id=rental_id)

    if rental.status == 'Rented':
        inventory_item = rental.inventory
        inventory_item.quantity += 1  # Use 'quantity' instead of 'stock_quantity'
        inventory_item.save()

        rental.status = 'Returned'
        rental.save()

        messages.success(request, f"Rental for {inventory_item.name} has been marked as returned.")
    else:
        messages.warning(request, "This rental is already returned.")

    return redirect('saritasapp:view_customer', customer_id=rental.customer.id)


#data_analysis
def data_analysis(request):
    # Total rentals and customers
    total_rentals = Rental.objects.count()
    total_customers = Customer.objects.count()

    # Most rented items
    most_rented_items = Inventory.objects.annotate(rental_count=Count('rental')).order_by('-rental_count')[:5]

    # Weekly rentals & income
    weekly_rentals = (
        Rental.objects.annotate(week=ExtractWeek('rental_start'))
        .values('week')
        .annotate(count=Count('id'), income=Sum('inventory__rental_price'))
        .order_by('week')
    )

    # Monthly rentals & income
    monthly_rentals = (
        Rental.objects.annotate(month=ExtractMonth('rental_start'))
        .values('month')
        .annotate(count=Count('id'), income=Sum('inventory__rental_price'))
        .order_by('month')
    )

    # Yearly rentals & income
    yearly_rentals = (
        Rental.objects.annotate(year=ExtractYear('rental_start'))
        .values('year')
        .annotate(count=Count('id'), income=Sum('inventory__rental_price'))
        .order_by('year')
    )

    context = {
        'total_rentals': total_rentals,
        'total_customers': total_customers,
        'most_rented_items': most_rented_items,
        'weekly_rentals': weekly_rentals,
        'monthly_rentals': monthly_rentals,
        'yearly_rentals': yearly_rentals,
    }
    return render(request, 'saritasapp/data_analysis.html', context)


#calnder
def calendar_view(request):
    return render(request, "saritasapp/calendar.html")

def ongoing_events(request):
    events = Event.objects.filter(start_date__lte=now().date(), end_date__gte=now().date())
    return render(request, "saritasapp/ongoing_events.html", {"events": events})

def upcoming_events(request):
    events = Event.objects.filter(start_date__gt=now().date())
    return render(request, "saritasapp/upcoming_events.html", {"events": events})

def past_events(request):
    events = Event.objects.filter(end_date__lt=now().date())
    return render(request, "saritasapp/past_events.html", {"events": events})

def create_event(request):
    if request.method == "POST":
        title = request.POST.get("title")
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        notes = request.POST.get("notes")
        Event.objects.create(title=title, start_date=start_date, end_date=end_date, notes=notes)
        return redirect("calendar")
    return render(request, "saritasapp/create_event.html")

def view_event(request, event_id):
    event = get_object_or_404(Event, id=event_id)
    return render(request, "saritasapp/view_event.html", {"event": event})

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

#Default Homepage Views
def homepage(request):
    return render(request, 'saritasapp/base.html')

def individual(request):
    return render(request, 'saritasapp/individual.html')


def sign_up(request):
    return render(request, 'saritasapp/signup.html')

def sign_in(request):
    return render(request, 'saritasapp/signin.html')

#all views
def profile_view(request):
    return render(request, 'saritasapp/profile.html')

def receipt_view(request):
    return render(request, 'saritasapp/receipt.html')

def notification_view(request):
    return render(request, 'saritasapp/notification.html')

def rental_tracker_view(request):

    return render(request, 'saritasapp/rental_tracker.html')


 #receipt
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Receipt
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Spacer, Paragraph
from reportlab.lib.styles import getSampleStyleSheet

def receipt_detail(request, receipt_id):
    """Display receipt details."""
    receipt = get_object_or_404(Receipt, id=receipt_id)
    return render(request, "saritasapp/receipt.html", {"receipt": receipt})

def update_receipt(request, receipt_id):
    """Update receipt details."""
    receipt = get_object_or_404(Receipt, id=receipt_id)

    if request.method == "POST":
        try:
            # Ensure decimal fields have valid values (default to 0 if empty)
            amount_str = request.POST.get("amount", "").strip()
            down_payment_str = request.POST.get("down_payment", "").strip()

            receipt.amount = float(amount_str) if amount_str else 0.00
            receipt.down_payment = float(down_payment_str) if down_payment_str else 0.00

            # Text fields
            receipt.customer_name = request.POST.get("customer_name", "").strip()
            receipt.customer_number = request.POST.get("customer_number", "").strip()
            receipt.payment_method = request.POST.get("payment_method", "").strip()
            receipt.remarks = request.POST.get("remarks", "").strip()

            # Convert DateTime fields
            payment_time_str = request.POST.get("payment_time")
            if payment_time_str:
                try:
                    receipt.payment_time = datetime.strptime(payment_time_str, "%Y-%m-%dT%H:%M")
                except ValueError:
                    return render(request, "saritasapp/receipt.html", {
                        "receipt": receipt,
                        "error": "Invalid payment time format. Please use YYYY-MM-DD HH:MM."
                    })

            # Convert Date fields
            date_fields = ["event_date", "pickup_date", "return_date"]
            for field in date_fields:
                date_str = request.POST.get(field)
                if date_str:
                    try:
                        setattr(receipt, field, datetime.strptime(date_str, "%Y-%m-%d").date())
                    except ValueError:
                        return render(request, "saritasapp/receipt.html", {
                            "receipt": receipt,
                            "error": f"Invalid format for {field}. Please use YYYY-MM-DD."
                        })

            # Measurements (Ensure empty values are handled correctly)
            measurement_fields = [
                "shoulder", "bust", "front", "width", "waist", "hips",
                "arm_length", "bust_depth", "bust_distance", "length",
                "lower_circumference", "crotch"
            ]
            for field in measurement_fields:
                setattr(receipt, field, request.POST.get(field, "").strip())

            # Save updated receipt
            receipt.save()
            return redirect("saritasapp:receipt-detail", receipt_id=receipt.id)

        except ValueError as e:
            return render(request, "saritasapp/receipt.html", {
                "receipt": receipt,
                "error": f"Invalid input: {str(e)}"
            })

    return render(request, "saritasapp/receipt.html", {"receipt": receipt})


def generate_receipt_pdf(request, receipt_id):
    """Generate a professional-looking PDF receipt."""
    receipt = get_object_or_404(Receipt, id=receipt_id)

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="receipt_{receipt_id}.pdf"'

    doc = SimpleDocTemplate(response, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()

    # Title
    elements.append(Paragraph("<b>Official Receipt</b>", styles["Title"]))
    elements.append(Spacer(1, 12))

    # Receipt details
    details = [
        ["Receipt ID:", receipt.id],
        ["Name:", receipt.customer_name],
        ["Contact:", receipt.customer_number],
        ["Amount:", f"₱{receipt.amount:,.2f}"],
        ["Down Payment:", f"₱{receipt.down_payment:,.2f}"],
        ["Payment Method:", receipt.payment_method],
        ["Event Date:", receipt.event_date.strftime("%Y-%m-%d")],
        ["Pickup Date:", receipt.pickup_date.strftime("%Y-%m-%d")],
        ["Return Date:", receipt.return_date.strftime("%Y-%m-%d")],
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
        ["Shoulder:", receipt.shoulder],
        ["Bust:", receipt.bust],
        ["Front:", receipt.front],
        ["Width:", receipt.width],
        ["Waist:", receipt.waist],
        ["Hips:", receipt.hips],
        ["Arm Length:", receipt.arm_length],
        ["Bust Depth:", receipt.bust_depth],
        ["Bust Distance:", receipt.bust_distance],
        ["Length:", receipt.length],
        ["Lower Circumference:", receipt.lower_circumference],
        ["Crotch:", receipt.crotch]
    ]

    measurement_table = Table(measurement_data, colWidths=[150, 300])
    measurement_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("GRID", (0, 0), (-1, -1), 1, colors.black)
    ]))

    elements.append(measurement_table)
    elements.append(Spacer(1, 12))

    # Signature Section
    elements.append(Spacer(1, 24))
    elements.append(Paragraph("__________________________", styles["Normal"]))
    elements.append(Paragraph("Authorized Signature", styles["Italic"]))

    # Build PDF
    doc.build(elements)
    return response
