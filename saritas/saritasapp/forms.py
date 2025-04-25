from datetime import timezone
import os
from pyexpat.errors import messages
from tkinter import Image
from django import forms
from django.urls import reverse_lazy
from .models import CustomizedWardrobePackage, Inventory, Category, ItemType, PackageCustomization, User, WardrobePackage, WardrobePackageItem, Branch, Event, Color, Size, Staff, WardrobePackageRental
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
    name = forms.CharField(
        label="Item Name",
        max_length=255,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'style': 'text-transform: capitalize;',
            'placeholder': 'Enter item name'
        })
    )
    quantity = forms.IntegerField(
        min_value=0,
        label="Quantity",
        required=True,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'oninput': "validity.valid||(value='');"
        })
    )
    rental_price = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Rental Price",
        required=True,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    reservation_price = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Reservation Price",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        required=False,
    )
    deposit_price = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Deposit Price",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        required=False,
    )
    purchase_price = forms.DecimalField(
        min_value=0,
        max_digits=10,
        decimal_places=2,
        label="Purchase Price",
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        required=False,
    )
    size = forms.ModelChoiceField(
        queryset=Size.objects.all().order_by('name'),
        required=True,
        label="Size",
        widget=forms.Select(attrs={'class': 'form-select select2'})
    )
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all().order_by('branch_name'),
        required=True,
        label="Branch",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    image = forms.ImageField(
        required=True, 
        label="Upload Image",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': 'image/*'})
    )
    item_type = forms.ModelChoiceField(
        queryset=ItemType.objects.all().order_by('name'),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select select2', 'data-placeholder': 'Select item type'}),
        label="Item Role Type",
        empty_label="Select item type"
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all().order_by('name'),
        required=True,
        label="Category",
        widget=forms.Select(attrs={'class': 'form-select select2', 'data-placeholder': 'Select category'})
    )
    color = forms.ModelChoiceField(
        queryset=Color.objects.all().order_by('name'),
        required=False,
        label="Color",
        widget=forms.Select(attrs={'class': 'form-select select2', 'data-placeholder': 'Select color'}),
    )
    available = forms.BooleanField(
        label="Available",
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = Inventory
        fields = [
            'name', 'branch', 'category', 'item_type', 'color', 'size', 'quantity',
            'rental_price', 'reservation_price', 'deposit_price', 'purchase_price',
            'available', 'image'
        ]

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Ensure item types exist in the database
        if not ItemType.objects.exists():
            ItemType.initialize_choices()
            self.fields['item_type'].queryset = ItemType.objects.all().order_by('name')

        # Handle branch field based on user type
        if self.user and hasattr(self.user, 'staff_profile'):
            # Staff users - auto-set to their branch
            self.fields['branch'].initial = self.user.staff_profile.branch
            self.fields['branch'].widget = forms.HiddenInput()
            self.fields['branch'].queryset = Branch.objects.filter(pk=self.user.staff_profile.branch.pk)
        elif self.user and self.user.is_superuser:
            # For admin users - show all branches
            self.fields['branch'].queryset = Branch.objects.all().order_by('branch_name')
            self.fields['branch'].widget.attrs.update({'class': 'form-select'})
        else:
            # For other users (shouldn't happen since view requires login)
            self.fields['branch'].widget = forms.HiddenInput()

        # Set required fields with asterisk
        for field in self.fields:
            if self.fields[field].required:
                self.fields[field].label = f"{self.fields[field].label} *"

        # If editing an existing item, make image not required
        if self.instance and self.instance.pk:
            self.fields['image'].required = False

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate deposit price is >= rental price
        deposit_price = cleaned_data.get("deposit_price")
        rental_price = cleaned_data.get("rental_price")

        # Validate item_type exists
        item_type = cleaned_data.get('item_type')
        if item_type and not ItemType.objects.filter(pk=item_type.pk).exists():
            self.add_error('item_type', 'Selected item type does not exist.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Format name properly
        instance.name = instance.name.title() if instance.name else ""
        
        # Set availability based on quantity
        instance.available = instance.quantity > 0
        
        # Set created_by if this is a new item
        if not instance.pk and hasattr(self.user, 'staff_profile'):
            instance.created_by = self.user

        if commit:
            instance.save()
            self.save_m2m()

            # Handle image separately to avoid issues with existing images
            if 'image' in self.changed_data:
                if self.cleaned_data['image']:
                    instance.image = self.cleaned_data['image']
                    instance.save()
                elif not self.cleaned_data['image'] and self.instance.image:
                    # Keep existing image if no new one was uploaded
                    instance.image = self.instance.image
                    instance.save()

        return instance

class ColorForm(forms.ModelForm):
    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Ivory, Champagne, Navy Blue',
            'style': 'text-transform: capitalize;',
            'autofocus': True
        }),
        help_text="Enter a descriptive color name"
    )

    class Meta:
        model = Color
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'})
        }

    def clean_name(self):
        name = self.cleaned_data.get('name').strip().title()
        if Color.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This color already exists.")
        return name


class SizeForm(forms.ModelForm):
    name = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., S, M, L, XL, XXL or Plus Sizes',
            'style': 'text-transform: capitalize;',
            'autofocus': True
        }),
        help_text="Enter a size designation"
    )

    class Meta:
        model = Size
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name').strip().upper()  # Convert to uppercase for sizes
        if Size.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This size already exists.")
        return name


class CategoryForm(forms.ModelForm):
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Wedding Gowns, Bridesmaid Dresses',
            'style': 'text-transform: capitalize;',
            'autofocus': True
        }),
        help_text="Enter a descriptive category name"
    )

    class Meta:
        model = Category
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name').strip().title()
        if Category.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This category already exists.")
        return name


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
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={'class': 'form-control','placeholder': 'Enter your username or email' })
    )
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={'class': 'form-control','placeholder': 'Password'})
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            # Try to authenticate with username first
            self.user_cache = authenticate(request=self.request,username=username,password=password)
            
            # If that fails, try with email
            if self.user_cache is None:
                from django.contrib.auth import get_user_model
                User = get_user_model()
                try:
                    user = User.objects.get(email=username)
                    self.user_cache = authenticate(request=self.request,username=user.username,password=password)
                except User.DoesNotExist:
                    pass
            
            if self.user_cache is None:
                raise ValidationError(
                    "Please enter a correct username/email and password."
                )
            
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data
    
class WardrobePackageForm(forms.ModelForm):
    class Meta:
        model = WardrobePackage
        fields = [
            'name', 'tier', 'description', 'base_price', 
            'deposit_price', 'discount', 'status', 
            'min_rental_days', 'includes_accessories'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter package name'
            }),
            'tier': forms.Select(attrs={
                'class': 'form-select',
                'data-placeholder': 'Select package tier'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Describe package contents...'
            }),
            'base_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'deposit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'discount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'status': forms.Select(attrs={
                'class': 'form-select'
            }),
            'min_rental_days': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'includes_accessories': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'includes_accessories': 'Includes accessories'
        }
        help_texts = {
            'tier': 'Predefined package tier or custom',
            'status': 'Fixed packages cannot be modified by customers'
        }

    def clean(self):
        cleaned_data = super().clean()
        tier = cleaned_data.get('tier')
        status = cleaned_data.get('status')
        
        if tier and tier != 'custom' and status == 'customizable':
            raise forms.ValidationError(
                "Predefined packages (A, B, C) must be fixed composition"
            )
        
        return cleaned_data


class WardrobePackageItemForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageItem
        fields = ['inventory_item', 'quantity', 'is_required', 'label', 'replacement_allowed']
        widgets = {
            'inventory_item': forms.Select(attrs={
                'class': 'form-select select2',
                'data-placeholder': 'Select inventory item'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1'
            }),
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional display name'
            }),
            'is_required': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'replacement_allowed': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }

    def __init__(self, *args, **kwargs):
        item_type = kwargs.pop('item_type', None)
        super().__init__(*args, **kwargs)
        
        # Filter available inventory items
        queryset = Inventory.objects.filter(available=True)
        if item_type:
            queryset = queryset.filter(item_type__name=item_type)
        self.fields['inventory_item'].queryset = queryset.order_by('name')
        
        # Disable is_required if replacement not allowed
        if self.instance.pk and not self.instance.replacement_allowed:
            self.fields['is_required'].initial = True
            self.fields['is_required'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        inventory_item = cleaned_data.get('inventory_item')
        quantity = cleaned_data.get('quantity', 1)
        is_required = cleaned_data.get('is_required', True)
        replacement_allowed = cleaned_data.get('replacement_allowed', True)

        if inventory_item and quantity > inventory_item.quantity:
            raise forms.ValidationError(
                f"Not enough stock. Only {inventory_item.quantity} available."
            )

        if not replacement_allowed and not is_required:
            raise forms.ValidationError(
                "Non-replaceable items must be required"
            )

        return cleaned_data

class PackageCustomizationForm(forms.ModelForm):
    class Meta:
        model = PackageCustomization
        fields = ['action', 'original_item', 'inventory_item', 'new_quantity', 'price_adjustment', 'notes']
        widgets = {
            'action': forms.RadioSelect(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Enter customization notes...'
            }),
        }

    def __init__(self, package=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if package:
            self.fields['original_item'].queryset = package.package_items.all()
            self.fields['inventory_item'].queryset = Inventory.objects.filter(available=True)

class CustomizePackageForm(forms.ModelForm):
    class Meta:
        model = CustomizedWardrobePackage
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Describe your customization requests...'
            }),
        }

class AddPackageItemForm(forms.ModelForm):
    item_type = forms.ModelChoiceField(
        queryset=ItemType.objects.all(),
        empty_label="Select item type",
        widget=forms.Select(attrs={
            'class': 'form-control',
            'hx-get': reverse_lazy('saritasapp:filter_inventory_items'),
            'hx-target': '#id_inventory_item',
            'hx-trigger': 'change'
        })
    )
    
    class Meta:
        model = WardrobePackageItem
        fields = ['item_type', 'inventory_item', 'quantity', 'label']
        widgets = {
            'inventory_item': forms.Select(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'label': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., "3 BRIDESMAIDS"'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        self.package = kwargs.pop('package', None)
        super().__init__(*args, **kwargs)
        
        # Filter inventory items based on what's already in package
        existing_item_ids = []
        if self.package:
            existing_item_ids = self.package.package_items.values_list(
                'inventory_item_id', flat=True)
        
        # Only show items not already in package
        self.fields['inventory_item'].queryset = Inventory.objects.none()
        
        if 'item_type' in self.data:
            try:
                item_type_id = int(self.data.get('item_type'))
                self.fields['inventory_item'].queryset = Inventory.objects.filter(
                    item_type_id=item_type_id,
                    available=True
                ).exclude(id__in=existing_item_ids)
            except (ValueError, TypeError):
                pass

class PackageItemForm(forms.Form):
    item_type = forms.ModelChoiceField(
        queryset=ItemType.objects.all(),
        widget=forms.HiddenInput()
    )
    inventory_item_id = forms.IntegerField(  # Changed from ModelChoiceField
        widget=forms.HiddenInput()
    )
    quantity = forms.IntegerField(
        min_value=1,
        initial=1,
        widget=forms.NumberInput(attrs={'class': 'form-control quantity-input'})
    )
    label = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Custom label (e.g. "3 BRIDESMAIDS")'
        })
    )

    def __init__(self, *args, **kwargs):
        self.package = kwargs.pop('package', None)
        super().__init__(*args, **kwargs)

class BulkPackageItemForm(forms.Form):
    items = forms.ModelMultipleChoiceField(
        queryset=Inventory.objects.none(),
        widget=forms.MultipleHiddenInput()
    )
    
    def __init__(self, *args, **kwargs):
        package = kwargs.pop('package', None)
        super().__init__(*args, **kwargs)
        
        if package:
            self.fields['items'].queryset = Inventory.objects.filter(
                available=True
            ).exclude(
                id__in=package.package_items.values_list('inventory_item_id', flat=True)
            )

# In saritasapp/forms.py
class StaffRentalApprovalForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageRental
        fields = ['status', 'staff', 'notes']  # Only include fields that exist
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'staff': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter any notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit staff choices to actual staff users
        self.fields['staff'].queryset = User.objects.filter(
            is_staff=True
        ).order_by('username')

class PackageReturnForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageRental
        fields = ['actual_return_date', 'status', 'notes']  # Only use existing fields
        widgets = {
            'actual_return_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={
                'class': 'form-control',
                'disabled': 'disabled'  # Auto-set to 'returned'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter condition notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].initial = 'returned'  # Auto-set status

    def clean(self):
        cleaned_data = super().clean()
        actual_return_date = cleaned_data.get('actual_return_date')
        
        if actual_return_date and actual_return_date < self.instance.event_date:
            raise forms.ValidationError(
                "Return date cannot be before the event date"
            )
        
        return cleaned_data