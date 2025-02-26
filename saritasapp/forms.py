from django import forms
from .models import Inventory, Category, User, Rental, Customer
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

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

class RentalForm(forms.ModelForm):
    class Meta:
        model = Rental
        fields = ["customer", "inventory", "rental_start", "rental_end"]

    def clean(self):
        cleaned_data = super().clean()
        rental_start = cleaned_data.get("rental_start")
        rental_end = cleaned_data.get("rental_end")

        if rental_start and rental_end and rental_end <= rental_start:
            raise forms.ValidationError("Return date must be after the rental start date.")

        return cleaned_data

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
            'phone': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Phone'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Address', 'rows': 3}),
        }
