from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from saritasapp.models import Customer, User, Rental, Reservation
from django.db import transaction

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
    class Meta:
        model = Rental
        fields = ['inventory', 'rental_start', 'rental_end']
        widgets = {
            'rental_start': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'placeholder': 'Select start date'
            }),
            'rental_end': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'placeholder': 'Select end date'
            }),
        }
        labels = {
            'rental_start': 'Rental Start Date',
            'rental_end': 'Rental End Date',
        }

    def clean(self):
        cleaned_data = super().clean()
        rental_start = cleaned_data.get('rental_start')
        rental_end = cleaned_data.get('rental_end')

        if rental_start and rental_end:
            if rental_start > rental_end:
                raise forms.ValidationError("Rental end date must be after the start date.")

        return cleaned_data

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['reservation_date', 'return_date', 'quantity']
        widgets = {
            'reservation_date': forms.DateInput(attrs={'type': 'date'}),
            'return_date': forms.DateInput(attrs={'type': 'date'}),
        }