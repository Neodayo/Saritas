from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from saritasapp.models import Customer, User, Rental, Reservation
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

class CustomerRegistrationForm(UserCreationForm):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your username'
        })
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your email'
        })
    )
    first_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your first name'
        })
    )
    last_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your last name'
        })
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter your phone number'
        })
    )
    address = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter your address (optional)'
        }),
        required=False
    )
    image = forms.ImageField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'form-control-file',
            'accept': 'image/*'
        }),
        required=False
    )

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already registered.")
        return email

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if Customer.objects.filter(phone=phone).exists():
            raise ValidationError("This phone number is already registered.")
        return phone

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.role = 'customer'
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        
        if commit:
            user.save()
            Customer.objects.create(
                user=user,
                phone=self.cleaned_data['phone'],  # Direct access, no .get()
                address=self.cleaned_data.get("address", ""),
                image=self.cleaned_data.get("image")
            )
        return user

class RentalForm(forms.ModelForm):
    deposit_amount = forms.DecimalField(
        required=False,
        disabled=True,
        label="Deposit Amount",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'deposit-amount'
        })
    )
    
    total_cost = forms.DecimalField(
        required=False,
        disabled=True,
        label="Estimated Total",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'id': 'total-cost'
        })
    )

    class Meta:
        model = Rental
        fields = ['rental_start', 'rental_end', 'notes']
        widgets = {
            'rental_start': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': timezone.now().date().isoformat()
                },
                format='%Y-%m-%d'
            ),
            'rental_end': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': (timezone.now() + timedelta(days=1)).date().isoformat()
                },
                format='%Y-%m-%d'
            ),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requests or notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.inventory_item = kwargs.pop('inventory_item', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values for display-only fields
        if self.inventory_item:
            self.fields['deposit_amount'].initial = self.inventory_item.deposit_price or 0
            self.fields['total_cost'].initial = self.calculate_total_cost()
        
        # Set minimum end date based on start date via JavaScript
        self.fields['rental_start'].widget.attrs.update({
            'onchange': 'updateDatesAndCalculate()'
        })
        self.fields['rental_end'].widget.attrs.update({
            'onchange': 'updateDatesAndCalculate()'
        })

    def calculate_total_cost(self):
        if not self.inventory_item:
            return 0
        
        rental_days = 1  # Default if dates not set
        if self['rental_start'].value() and self['rental_end'].value():
            start = datetime.strptime(self['rental_start'].value(), '%Y-%m-%d').date()
            end = datetime.strptime(self['rental_end'].value(), '%Y-%m-%d').date()
            rental_days = (end - start).days + 1
        
        return (self.inventory_item.rental_price * rental_days) + (self.inventory_item.deposit_price or 0)

    def clean(self):
        cleaned_data = super().clean()
        rental_start = cleaned_data.get('rental_start')
        rental_end = cleaned_data.get('rental_end')

        if not all([rental_start, rental_end]):
            return cleaned_data

        # Date validation
        today = timezone.now().date()
        if rental_start < today:
            raise forms.ValidationError(
                "Rental start date cannot be in the past. Please choose a date today or later."
            )
        
        if rental_start > rental_end:
            raise forms.ValidationError(
                "Rental end date must be after the start date."
            )
        
        min_rental_days = 1  # Minimum rental period
        if (rental_end - rental_start).days < min_rental_days:
            raise forms.ValidationError(
                f"Minimum rental period is {min_rental_days} day(s)."
            )

        # Inventory availability check
        if self.inventory_item:
            # Check quantity
            if self.inventory_item.quantity <= 0:
                raise forms.ValidationError(
                    "This item is currently out of stock."
                )
            
            # Check for overlapping rentals
            overlapping = Rental.objects.filter(
                inventory=self.inventory_item,
                rental_start__lte=rental_end,
                rental_end__gte=rental_start,
                status__in=['Approved', 'Rented']  # Only check confirmed rentals
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if overlapping.exists():
                raise forms.ValidationError(
                    "This item is already booked during the selected period. "
                    "Please choose different dates."
                )

        return cleaned_data

    def save(self, commit=True):
        rental = super().save(commit=False)
        rental.inventory = self.inventory_item
        rental.customer = self.customer
        
        if commit:
            rental.save()
        
        return rental
    
class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['reservation_date', 'return_date', 'quantity']
        widgets = {
            'reservation_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': timezone.now().date().isoformat()
            }),
            'return_date': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1
            })
        }
    
    def __init__(self, *args, **kwargs):
        self.item = kwargs.pop('item', None)
        super().__init__(*args, **kwargs)
        
    def clean(self):
        cleaned_data = super().clean()
        
        if not self.item:
            raise ValidationError("No inventory item selected")
            
        # Date validation
        if cleaned_data.get('return_date') < cleaned_data.get('reservation_date'):
            raise ValidationError("Return date must be after reservation date")
            
        # Quantity validation
        quantity = cleaned_data.get('quantity', 1)
        if quantity > self.item.quantity:
            raise ValidationError(
                f"Only {self.item.quantity} available. You requested {quantity}."
            )
            
        return cleaned_data