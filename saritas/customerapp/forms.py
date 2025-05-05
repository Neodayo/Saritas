import logging
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from saritasapp.models import Customer, InventorySize, PackageRentalItem, Size, User, Rental, Reservation, WardrobePackageRental
from django.db import transaction
from django.utils import timezone
from datetime import timedelta
from django.utils.timezone import now, timedelta
from .models import HeroSection
from .models import EventSlide

logger = logging.getLogger(__name__)

class CustomerRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=30)
    last_name = forms.CharField(max_length=30)
    phone = forms.CharField(max_length=15)
    address = forms.CharField(widget=forms.Textarea, required=False)
    image = forms.ImageField(required=False)

    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email", "phone", "address", "image", "password1", "password2")

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data["first_name"]
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
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
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
        fields = ['reservation_date', 'return_date', 'quantity', 'notes']
        widgets = {
            'reservation_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': timezone.now().date().isoformat()
                }
            ),
            'return_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': (timezone.now() + timedelta(days=1)).date().isoformat()
                }
            ),
            'quantity': forms.NumberInput(
                attrs={
                    'class': 'form-control',
                    'min': 1
                }
            ),
            'notes': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 3,
                    'placeholder': 'Any special requests...'
                }
            )
        }

    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.item:
            self.instance.item = self.item  # 🔥 This sets the item early so model.clean() doesn't fail

        # Dynamic min date for return date based on reservation date
        if 'reservation_date' in self.initial:
            res_date = self.initial['reservation_date']
            if isinstance(res_date, str):
                self.fields['return_date'].widget.attrs['min'] = res_date
            elif hasattr(res_date, 'isoformat'):
                self.fields['return_date'].widget.attrs['min'] = res_date.isoformat()


    def clean(self):
        cleaned_data = super().clean()

        if not self.item:
            raise ValidationError("No inventory item selected for reservation.")

        reservation_date = cleaned_data.get('reservation_date')
        return_date = cleaned_data.get('return_date')
        quantity = cleaned_data.get('quantity', 1)

        # Date checks
        if reservation_date and return_date:
            if return_date < reservation_date:
                raise ValidationError("Return date must be after the reservation date.")

            max_duration = 30
            if (return_date - reservation_date).days > max_duration:
                raise ValidationError(f"Maximum reservation duration is {max_duration} days.")

        # Quantity checks
        if quantity is not None:
            if quantity <= 0:
                raise ValidationError("Quantity must be at least 1.")

            if self.item and quantity > self.item.quantity:
                raise ValidationError(
                    f"Only {self.item.quantity} unit(s) available. You requested {quantity}."
                )

        return cleaned_data
    
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