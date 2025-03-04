from django import forms
from .models import Inventory, Category, User, Rental, Customer, WardrobePackage, WardrobePackageItem, Branch
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
User = get_user_model()


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
        fields = ["customer", "inventory", "rental_start", "rental_end", "status"]
        widgets = {
            "rental_start": forms.DateInput(attrs={"type": "date"}),
            "rental_end": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        rental_start = cleaned_data.get("rental_start")
        rental_end = cleaned_data.get("rental_end")
        inventory = cleaned_data.get("inventory")

        if rental_end and rental_start and rental_end < rental_start:
            raise forms.ValidationError("Return date must be after the rental start date.")

        if inventory and inventory.quantity <= 0:
            raise forms.ValidationError(f"{inventory.name} is out of stock.")
        
        return cleaned_data

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ["first_name", "last_name", "email", "phone", "address", "image"]
        widgets = {
            "first_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "First Name"}),
            "last_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Last Name"}),
            "email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email"}),
            "phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Phone"}),
            "address": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Address (Optional)"}),
        }

class WardrobePackageForm(forms.ModelForm):
    class Meta:
        model = WardrobePackage
        fields = ["name", "tier"]

class WardrobePackageItemForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageItem
        fields = ["package", "inventory_item", "quantity"]

class SignupForm(UserCreationForm):
    name = forms.CharField(max_length=255, required=True)
    email = forms.EmailField(required=True)
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), required=False)  # Allow None
    
    class Meta:
        model = User  # ✅ Make sure this is using the correct User model
        fields = ["name", "username", "email", "branch", "password1", "password2"]
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.name = self.cleaned_data["name"]
        user.email = self.cleaned_data["email"]
        user.branch = self.cleaned_data["branch"]
        if commit:
            user.save()
        return user

# Login Form
class LoginForm(AuthenticationForm):
    username = forms.EmailField(label="Email", required=True)
