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