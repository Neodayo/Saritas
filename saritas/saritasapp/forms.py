from django import forms
from .models import Inventory, Category

class InventoryForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1, label="Quantity")
    rental_price = forms.DecimalField(min_value=0, max_digits=10, decimal_places=2, label="Rental Price")
    purchase_price = forms.DecimalField(
        min_value=0, max_digits=10, decimal_places=2, required=False, label="Purchase Price"
    )
    image = forms.ImageField(required=False, label="Upload Image")

    class Meta:
        model = Inventory
        fields = ['name', 'category', 'color', 'quantity', 'rental_price', 'purchase_price', 'available', 'image']
        labels = {
            'name': 'Item Name',
            'category': 'Category',
            'color': 'Color',
            'available': 'Available for Rent?',
        }

class CategoryForm(forms.ModelForm):
    name = forms.CharField(max_length=255, label="Category Name")

    class Meta:
        model = Category
        fields = ['name']
