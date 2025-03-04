from django.shortcuts import render, redirect, get_object_or_404
from .forms import InventoryForm, CategoryForm, RentalForm, CustomerForm, WardrobePackageForm, WardrobePackageItemForm
from .models import Customer, Inventory, Category, Rental, User, WardrobePackage, WardrobePackageItem, CustomerOrder, SelectedPackageItem, Event
from django.utils.timezone import now
from django.db.models import F, Q  ,Count , Sum
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
from django.contrib.auth import login, authenticate, logout #new
from .forms import SignupForm, LoginForm #new
from django.contrib.auth.decorators import login_required #new
from django.http import JsonResponse #new
# for calendar
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.timezone import now
from .models import Event
from django.http import JsonResponse
from datetime import date
import calendar

@login_required
def dashboard(request):
    return render(request, 'dashboard.html')

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
    customer_orders = CustomerOrder.objects.filter(customer=customer)

    return render(request, 'saritasapp/view_customer.html', {
        'customer': customer,
        'rentals': rentals,
        "customer_orders": customer_orders,
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
def calendar_view(request, year=None, month=None):
    if year is None or month is None:
        today = date.today()
        year, month = today.year, today.month

    # Generate the month calendar
    cal = calendar.HTMLCalendar().formatmonth(year, month)

    # Fix: Use `start__year` and `start__month` instead of `date`
    events = Event.objects.filter(start__year=year, start__month=month)

    context = {
        "calendar": cal,
        "events": events,
        "year": year,
        "month": month,
    }
    return render(request, "saritasapp/calendar.html", context)

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
    events = Event.objects.all().values("id", "title", "start", "end")
    event_list = list(events)

    return JsonResponse(event_list, safe=False)

def wardrobe_package_list(request):
    packages = WardrobePackage.objects.filter(status="active")  # Show only active packages
    return render(request, "saritasapp/wardrobe_package_list.html", {"packages": packages})

def wardrobe_package_detail(request, package_id):
    """Displays details of a specific wardrobe package and allows item selection."""
    package = get_object_or_404(WardrobePackage, id=package_id)
    items = WardrobePackageItem.objects.filter(package=package)

    total_price = package.base_price + sum(item.inventory_item.rental_price * item.quantity for item in items)

    return render(
        request,
        "saritasapp/wardrobe_package_detail.html",
        {"package": package, "items": items, "total_price": total_price},
    )

def select_wardrobe_package(request, package_id):
    """Assigns a selected Wardrobe Package to an existing customer and creates an order."""
    package = get_object_or_404(WardrobePackage, id=package_id)

    if request.method == "POST":
        customer_email = request.POST.get("customer_email")  # Get email from form
        user = request.user  # Get the logged-in user (sales clerk)

        # Find the customer by email
        try:
            customer = Customer.objects.get(email=customer_email)
        except Customer.DoesNotExist:
            messages.error(request, "Customer not found! Please check the email and try again.")
            return redirect("saritasapp:wardrobe_package_detail", package_id=package.id)

        # Create a new order for the customer
        order = CustomerOrder.objects.create(
            customer=customer,
            user=user,  # Sales clerk processing the order
            package=package,
            total_price=package.final_price(),  # Using the discounted price if any
            status="Pending"
        )

        messages.success(request, f"Package '{package.name}' added to {customer.first_name}'s orders!")
        return redirect("saritasapp:customer_orders", customer_id=customer.id)  # Redirect to customer's order page

    return redirect("saritasapp:wardrobe_package_detail", package_id=package.id)

def wardrobe_package_detail(request, package_id):
    package = get_object_or_404(WardrobePackage, id=package_id)
    items = WardrobePackageItem.objects.filter(package=package)
    customers = Customer.objects.all()  # Fetch all existing customers

    # Calculate total price
    total_price = package.base_price

    if request.method == "POST":
        customer_id = request.POST.get("customer_id")
        selected_item_ids = request.POST.getlist("selected_items")

        if not customer_id:
            messages.error(request, "Please select a customer.")
            return redirect("saritasapp:wardrobe_package_detail", package_id=package.id)

        customer = get_object_or_404(Customer, id=customer_id)
        user = request.user if request.user.is_authenticated else None  # Get logged-in user

        # Create a new order
        order = CustomerOrder.objects.create(
            customer=customer,
            user=user,
            package=package,
            total_price=package.base_price,  # Initial price
            status="Pending",
        )

        # Add selected items to the order
        for item_id in selected_item_ids:
            item = get_object_or_404(WardrobePackageItem, id=item_id)
            SelectedPackageItem.objects.create(order=order, item=item.inventory_item, selected=True)

        # Recalculate the total price
        order.calculate_total_price()

        messages.success(request, "Package successfully added to customer's orders.")
        return redirect("saritasapp:customer_orders", customer_id=customer.id)  # Redirect to customer's orders page

    return render(request, "saritasapp/wardrobe_package_detail.html", {
        "package": package,
        "items": items,
        "customers": customers,
        "total_price": total_price,
    })

def customer_orders(request, customer_id):
    customer = get_object_or_404(Customer, id=customer_id)
    orders = CustomerOrder.objects.filter(customer=customer)

    return render(request, "saritasapp/customer_orders.html", {
        "customer": customer,
        "orders": orders,
    })
def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully!")
            return redirect("saritasapp:dashboard")  # Change to your main page
    else:
        form = SignupForm()
    return render(request, "saritasapp/signup.html", {"form": form})

# Login View
def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            email = form.cleaned_data["username"]
            password = form.cleaned_data["password"]
            user = authenticate(request, username=email, password=password)
            if user:
                login(request, user)
                messages.success(request, "Logged in successfully!")
                return redirect("saritasapp:dashboard")  # Change to your main page
        messages.error(request, "Invalid email or password.")
    else:
        form = LoginForm()
    return render(request, "saritasapp/login.html", {"form": form})

# Logout View
def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect("saritasapp:login")