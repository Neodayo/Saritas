import datetime
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
        label="Deposit Amount",
        disabled=True,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    estimated_total = forms.DecimalField(
        label="Estimated Total",
        disabled=True,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
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
                }
            ),
            'rental_end': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': (timezone.now() + timedelta(days=1)).date().isoformat()
                }
            ),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Any special requests or notes...'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.inventory = kwargs.pop('inventory', None)
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        rental = super().save(commit=False)
        if self.inventory:
            rental.deposit = self.inventory.deposit_price or 0.00
        if commit:
            rental.save()
        return rental
    
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