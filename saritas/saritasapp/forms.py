from django import forms
from .models import Inventory, Category, User, Rental, Customer, WardrobePackage, WardrobePackageItem, Branch, Event
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
User = get_user_model()

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'venue', 'start_date', 'end_date', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:  # Only when creating a new rental
            self.fields['status'].initial = 'Renting'
            self.fields['status'].widget = forms.HiddenInput()  # Hide the field on creation

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

class SignUpForm(UserCreationForm):
    name = forms.CharField(
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Full Name'})
    )
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email Address'})
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )
    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Confirm Password'})
    )

    class Meta:
        model = User
        fields = ['username', 'name', 'email', 'branch', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'}),
        }


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username", widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={'class': 'form-control'}))


#profile
from django import forms
from .models import User, Branch

class EditProfileForm(forms.ModelForm):
    branch = forms.ModelChoiceField(queryset=Branch.objects.all(), required=True)

    class Meta:
        model = User
        fields = ["name", "email", "branch"]