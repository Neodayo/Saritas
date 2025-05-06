from decimal import Decimal
import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from saritasapp.models import Customer, InventorySize, PackageRentalItem, Size, User, Rental, Reservation, WardrobePackageRental
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
from django.utils.timezone import now, timedelta
from .models import HeroSection
from .models import EventSlide
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30)
    middle_initial = forms.CharField(max_length=1, required=False)  
    last_name = forms.CharField(max_length=30)
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea, required=False)
    image = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "middle_initial", "last_name", "email", "phone", "address", "image", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
        user.middle_initial = self.cleaned_data.get("middle_initial", "") 
        user.last_name = self.cleaned_data["last_name"]
        user.role = 'customer'

        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                phone=self.cleaned_data["phone"],
                address=self.cleaned_data.get("address"),
                image=self.cleaned_data.get("image")
            )
        return user

class UserUpdateForm(forms.ModelForm):
    middle_initial = forms.CharField(max_length=1, required=False)  
    
    class Meta:
        model = User
        fields = ['first_name', 'middle_initial', 'last_name', 'email'] 
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_initial': forms.TextInput(attrs={'class': 'form-control', 'style': 'width: 50px;'}),  
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
        }

class CustomerUpdateForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = ['phone', 'address', 'image']
        widgets = {
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
        }

class RentalForm(forms.ModelForm):
    size = forms.ModelChoiceField(
        queryset=InventorySize.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        label="Select Size",
        required=True
    )
    
    deposit = forms.DecimalField(
        disabled=True,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Rental
        fields = ['rental_start', 'rental_end', 'deposit', 'notes', 'size']
        widgets = {
            'rental_start': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'rental_end': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': (timezone.now() + timedelta(days=1)).date().isoformat()
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requests or notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.inventory = kwargs.pop('inventory', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)

        if self.inventory:
            # Set initial deposit value
            self.fields['deposit'].initial = self.inventory.deposit_price or 0
            
            # Only show sizes with available inventory
            self.fields['size'].queryset = InventorySize.objects.filter(
                inventory=self.inventory,
                quantity__gt=0
            ).select_related('size')
            
            # Format the size choices to show available quantities
            self.fields['size'].label_from_instance = lambda obj: (
                f"{obj.size.get_name_display()} (Available: {obj.quantity})"
            )

            # Set default dates
            self.fields['rental_start'].initial = timezone.now().date()
            self.fields['rental_end'].initial = (timezone.now() + timedelta(days=7)).date()

    def clean(self):
        cleaned_data = super().clean()
        
        if not self.inventory:
            raise ValidationError("Inventory item is required")
        
        size = cleaned_data.get('size')
        rental_start = cleaned_data.get('rental_start')
        rental_end = cleaned_data.get('rental_end')

        # Validate size availability
        if size:
            if size.quantity <= 0:
                raise ValidationError("This size is no longer available for rent")
            
            # Check if inventory size belongs to the selected inventory
            if size.inventory != self.inventory:
                raise ValidationError("Invalid size selection")

        # Validate rental dates
        if rental_start and rental_end:
            if rental_end <= rental_start:
                raise ValidationError("Return date must be after the rental start date")
            
            if rental_start < timezone.now().date():
                raise ValidationError("Start date cannot be in the past")

        # Set deposit if not already set
        if 'deposit' not in cleaned_data or not cleaned_data['deposit']:
            cleaned_data['deposit'] = self.inventory.deposit_price or 0

        return cleaned_data

    def save(self, commit=True):
        rental = super().save(commit=False)
        rental.customer = self.customer
        rental.inventory_size = self.cleaned_data['size']
        rental.deposit = self.cleaned_data['deposit']
        rental.status = Rental.PENDING
        
        if commit:
            rental.save()
        return rental

    def get_penalty_warning(self):
        """Calculate potential penalty for display in template"""
        rental_end = self.cleaned_data.get('rental_end')
        if rental_end and rental_end < timezone.now().date():
            overdue_days = (timezone.now().date() - rental_end).days
            return {
                'days': overdue_days,
                'amount': overdue_days * 100,  # 100php per day
                'message': f"Warning: This rental would be {overdue_days} days overdue (₱{overdue_days * 100} penalty)"
            }
        return None
    
class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['inventory_size']
        widgets = {
            'inventory_size': forms.RadioSelect(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.customer = kwargs.pop('customer', None)
        self.inventory = kwargs.pop('inventory', None)
        super().__init__(*args, **kwargs)

        if self.inventory:
            # Filter sizes with available quantity
            self.fields['inventory_size'].queryset = InventorySize.objects.filter(
                inventory=self.inventory,
                quantity__gt=0
            ).select_related('size')

            # Human-readable labels for radio buttons
            self.fields['inventory_size'].label_from_instance = lambda obj: (
                f"{obj.size.name} ({obj.quantity} available)"
            )

    def clean(self):
        cleaned_data = super().clean()
        inventory_size = cleaned_data.get("inventory_size")

        if not inventory_size:
            raise ValidationError(_("Please select a valid size."))

        return cleaned_data

    def save(self, commit=True):
        """
        Creates a reservation using validated data.
        Uses atomic transaction to lock inventory and prevent race conditions.
        """
        if not self.customer:
            raise ValueError(_("Customer must be provided to create a reservation."))

        inventory_size = self.cleaned_data["inventory_size"]

        try:
            with transaction.atomic():
                # Lock inventory row for update
                locked_inventory = InventorySize.objects.select_for_update().get(
                    pk=inventory_size.pk,
                    quantity__gt=0
                )

                # Create reservation with fixed ₱500 fee
                reservation = Reservation.objects.create(
                    customer=self.customer,
                    inventory_size=locked_inventory,
                    amount_paid=Decimal('500.00'),
                    status='paid'
                )

                # Decrease available quantity
                locked_inventory.quantity -= 1
                locked_inventory.save()

                return reservation
        except InventorySize.DoesNotExist:
            raise ValidationError(_("This item size is no longer available."))
    
class WardrobePackageRentalForm(forms.ModelForm):
    class Meta:
        model = WardrobePackageRental
        fields = ['event_date']  # Only event_date should be user-provided
        
        widgets = {
            'event_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': (timezone.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            })
        }

    def clean_event_date(self):
        event_date = self.cleaned_data.get('event_date')
        if event_date <= timezone.now().date():
            raise forms.ValidationError("Event date must be in the future.")
        return event_date

class PackageItemReturnForm(forms.ModelForm):
    class Meta:
        model = PackageRentalItem
        fields = ['returned', 'condition', 'notes']
        widgets = {
            'condition': forms.Select(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class HeroSectionForm(forms.ModelForm):
    class Meta:
        model = HeroSection
        fields = ['title', 'subtitle', 'background_image']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'subtitle': forms.TextInput(attrs={'class': 'form-control'}),
        }

class EventSlideForm(forms.ModelForm):
    class Meta:
        model = EventSlide
        fields = ['title', 'subtitle', 'image', 'order']
        widgets = {
            'order': forms.NumberInput(attrs={'min': 0})
        }

class RentalEditForm(forms.ModelForm):
    size = forms.ModelChoiceField(
        queryset=InventorySize.objects.none(),  # Will be set in __init__
        required=True,
        label="Select Size"
    )

    class Meta:
        model = Rental
        fields = ['rental_start', 'rental_end', 'size', 'notes']
        widgets = {
            'rental_start': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'rental_end': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-textarea'}),
        }

    def __init__(self, *args, **kwargs):
        rental = kwargs.pop('rental', None)
        super().__init__(*args, **kwargs)
        
        if rental:
            # Only show available sizes for the same inventory item
            self.fields['size'].queryset = InventorySize.objects.filter(
                inventory=rental.inventory_size.inventory,
                quantity__gt=0
            ).select_related('size')
            self.initial['size'] = rental.inventory_size

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('rental_start')
        end = cleaned_data.get('rental_end')
        new_size = cleaned_data.get('size')
        
        if start and end and end <= start:
            raise forms.ValidationError("End date must be after start date")
        
        if new_size and not self.instance.can_change_size(new_size):
            raise forms.ValidationError("Cannot change to this size")
        
        return cleaned_data