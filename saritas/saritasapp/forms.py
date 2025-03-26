from django import forms
from .models import Inventory, Category, User, Rental, WardrobePackage, WardrobePackageItem, Branch, Event, Color, Size, Staff
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model, authenticate
from django.core.exceptions import ValidationError
from django.db import transaction
User = get_user_model()

class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['title', 'venue', 'start_date', 'end_date', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'venue': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class InventoryForm(forms.ModelForm):
    quantity = forms.IntegerField(
        min_value=1, 
        label="Quantity", 
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    rental_price = forms.DecimalField(
        min_value=0, 
        max_digits=10, 
        decimal_places=2, 
        label="Rental Price",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    reservation_price = forms.DecimalField(
        min_value=0, 
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        label="Reservation Price",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    purchase_price = forms.DecimalField(
        min_value=0, 
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        label="Purchase Price",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    size = forms.ModelChoiceField(
        queryset=Size.objects.all(), 
        required=False, 
        label="Size",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    image = forms.ImageField(
        required=True, 
        label="Upload Image",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Inventory
        fields = [
            'name', 'category', 'color', 'size', 'quantity', 
            'rental_price', 'reservation_price', 'purchase_price', 
            'available', 'image'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'color': forms.Select(attrs={'class': 'form-select'}),
            'available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        required_fields = ['name', 'category', 'color', 'quantity', 'rental_price']
        for field in required_fields:
            if not cleaned_data.get(field):
                self.add_error(field, f"{field.replace('_', ' ').title()} is required.")
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            raise ValidationError("Image field must not be empty.")
        return image




class ColorForm(forms.ModelForm):
    class Meta:
        model = Color
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter color name'
            })
        }

class SizeForm(forms.ModelForm):
    class Meta:
        model = Size
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter size name'
            })
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
            "customer": forms.Select(attrs={'class': 'form-select'}),
            "inventory": forms.Select(attrs={'class': 'form-select'}),
            "rental_start": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "rental_end": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "status": forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['status'].initial = 'Rented'
            self.fields['status'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()


class WardrobePackageForm(forms.ModelForm):
    class Meta:
        model = WardrobePackage
        fields = ["name", "tier"]

class WardrobePackageItemForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageItem
        fields = ["package", "inventory_item", "quantity"]

class StaffSignUpForm(UserCreationForm):
    # Staff-specific fields (not part of User model)
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    position = forms.CharField(
        label="Position",
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = User
        # Only include User model fields
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'staff'
        
        if commit:
            user.save()
            # Create Staff with form-specific fields
            Staff.objects.create(
                user=user,
                branch=self.cleaned_data['branch'],
                position=self.cleaned_data['position']
            )
        return user




class AdminSignUpForm(UserCreationForm):
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        user.is_superuser = True
        user.is_staff = True
        if commit:
            user.save()
        return user

class EditProfileForm(forms.ModelForm):
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'branch']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Username", widget=forms.TextInput(attrs={'class': 'form-control'}))
    password = forms.CharField(label="Password", widget=forms.PasswordInput(attrs={'class': 'form-control'}))