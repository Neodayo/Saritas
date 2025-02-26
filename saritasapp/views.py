from django.shortcuts import render, redirect, get_object_or_404
from .forms import InventoryForm, CategoryForm, RentalForm, CustomerForm
from .models import Customer, Inventory, Category, Rental, User, Customer
from django.core.files.storage import default_storage
from datetime import datetime
from django.utils.timezone import now
from django.db.models import F
from django.db import transaction
from django.core.exceptions import ValidationError
from django.contrib import messages


def add_inventory(request):
    categories = Category.objects.all()

    if request.method == 'POST':
        name = request.POST['name']
        category = get_object_or_404(Category, id=request.POST['category'])
        color = request.POST.get('color', '')
        quantity = request.POST['quantity']
        rental_price = request.POST['rental_price']
        purchase_price = request.POST.get('purchase_price', 0)
        available = request.POST.get('available', False) == 'on'
        image = request.FILES.get('image')
        inventory_item = Inventory(
            name=name,
            category=category,
            color=color,
            quantity=quantity,
            rental_price=rental_price,
            purchase_price=purchase_price,
            available=available,
            image=image
        )
        inventory_item.save()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/add_inventory.html', {'categories': categories})


def inventory_list(request):
    inventory_items = Inventory.objects.all()
    return render(request, 'saritasapp/inventory.html', {'inventory_items': inventory_items})

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
        item.name = request.POST['name']
        item.category = get_object_or_404(Category, id=request.POST['category'])
        item.quantity = request.POST['quantity']
        item.rental_price = request.POST['rental_price']
        item.purchase_price = request.POST.get('purchase_price', 0)
        item.available = request.POST.get('available', False) == 'on'

        if 'image' in request.FILES:
            item.image = request.FILES['image'] 
        item.save()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/edit_inventory.html', {'item': item, 'categories': categories})

def delete_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    
    if request.method == 'POST':
        item.delete()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/confirm_delete.html', {'item': item})

def inventory_view(request):
    categories = Category.objects.all()
    selected_category = request.GET.get('category', '')

    if selected_category:
        inventory_items = Inventory.objects.filter(category_id=selected_category)
    else:
        inventory_items = Inventory.objects.all()

    context = {
        'categories': categories,
        'inventory_items': inventory_items,
        'selected_category': selected_category
    }
    return render(request, 'saritasapp/inventory.html', context)

from .forms import RentalForm

def rent_item(request):
    customers = Customer.objects.all()
    inventory_items = Inventory.objects.filter(quantity__gt=0)  # Show only available items

    if request.method == "POST":
        form = RentalForm(request.POST)
        if form.is_valid():
            rental = form.save(commit=False)

            # Ensure selected inventory item is available
            if rental.inventory.quantity <= 0:
                messages.error(request, f"{rental.inventory.name} is out of stock.")
                return redirect("saritasapp:rental")

            # Decrease inventory quantity
            rental.inventory.quantity -= 1
            rental.inventory.save(update_fields=["quantity"])

            rental.status = "Rented"
            rental.save()
            messages.success(request, "Rental confirmed successfully!")
            return redirect("saritasapp:rental")

        else:
            messages.error(request, "There was an error with your submission.")
    
    else:
        form = RentalForm()

    context = {
        "form": form,
        "customers": customers,
        "inventory_items": inventory_items,
        "today": now().date(),
    }
    return render(request, "saritasapp/rental.html", context)

def create_customer(request):
    if request.method == "POST":
        form = CustomerForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('customer_list')  # Redirect to customer list view after saving
    else:
        form = CustomerForm()

    return render(request, 'saritasapp/create_customer.html', {'form': form})