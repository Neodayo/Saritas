from django.shortcuts import render, redirect, get_object_or_404
from .models import Inventory, Category
from .forms import InventoryForm, CategoryForm

from django.shortcuts import render, redirect
from .models import Inventory, Category
from django.core.files.storage import default_storage

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
            return redirect('add_inventory')
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
            item.image = request.FILES['image']  # Save new image

        item.save()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/edit_inventory.html', {'item': item, 'categories': categories})

def delete_inventory(request, item_id):
    item = get_object_or_404(Inventory, id=item_id)
    
    if request.method == 'POST':
        item.delete()
        return redirect('saritasapp:inventory_list')

    return render(request, 'saritasapp/confirm_delete.html', {'item': item})