from django import forms
from .models import Inventory, Category, User, WardrobePackage, WardrobePackageItem, Branch, Event, Color, Size, Staff
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
    deposit_price = forms.DecimalField(
        min_value=0, 
        max_digits=10, 
        decimal_places=2, 
        required=False, 
        label="Deposit Price",
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
    branch = forms.ModelChoiceField(
        queryset=Branch.objects.all(),
        required=True,
        label="Branch",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    image = forms.ImageField(
        required=True, 
        label="Upload Image",
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Inventory
        fields = ['name', 'branch', 'category', 'color', 'size', 'quantity',
                 'rental_price', 'reservation_price', 'deposit_price', 'purchase_price',
                 'available', 'image']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'color': forms.Select(attrs={'class': 'form-select'}),
            'available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial branch for staff users
        if self.user and hasattr(self.user, 'staff_profile'):
            self.fields['branch'].initial = self.user.staff_profile.branch
            # Make it read-only for staff
            self.fields['branch'].disabled = True
        
        # Set required fields
        self.fields['category'].required = True
        self.fields['color'].required = True

    def clean(self):
        cleaned_data = super().clean()
        required_fields = ['name', 'branch', 'category', 'color', 'quantity', 'rental_price']
        for field in required_fields:
            if not cleaned_data.get(field):
                self.add_error(field, f"{field.replace('_', ' ').title()} is required.")
        
        # Ensure staff users can't modify their branch
        if hasattr(self.user, 'staff_profile'):
            cleaned_data['branch'] = self.user.staff_profile.branch
            
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            raise ValidationError("Image field must not be empty.")
        return image

    def clean(self):
        cleaned_data = super().clean()
        required_fields = ['name', 'category', 'color', 'quantity', 'rental_price']
        for field in required_fields:
            if not cleaned_data.get(field):
                self.add_error(field, f"{field.replace('_', ' ').title()} is required.")
        
        # For staff users, ensure branch is set
        if hasattr(self.user, 'staff_profile') and not cleaned_data.get('branch'):
            cleaned_data['branch'] = self.user.staff_profile.branch
            
        return cleaned_data

    def clean_image(self):
        image = self.cleaned_data.get('image')
        if not image:
            raise ValidationError("Image field must not be empty.")
        return image

    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Auto-assign branch for staff users if not set
        if not instance.branch and hasattr(self.user, 'staff_profile'):
            instance.branch = self.user.staff_profile.branch
            
        if commit:
            instance.save()
            self.save_m2m()
            
        return instance

class ColorForm(forms.ModelForm):
    name = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Ivory, Champagne, Navy Blue',
            'autofocus': True
        }),
        help_text="Enter a descriptive color name"
    )

    class Meta:
        model = Color
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name').strip()
        if Color.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This color already exists.")
        return name

class SizeForm(forms.ModelForm):
    name = forms.CharField(
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., S, M, L, XL, XXL or Plus Sizes',
            'autofocus': True
        }),
        help_text="Enter a size designation"
    )

    class Meta:
        model = Size
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name').strip()
        if Size.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This size already exists.")
        return name

class CategoryForm(forms.ModelForm):
    name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Wedding Gowns, Bridesmaid Dresses',
            'autofocus': True
        }),
        help_text="Enter a descriptive category name"
    )

    class Meta:
        model = Category
        fields = ['name']

    def clean_name(self):
        name = self.cleaned_data.get('name').strip()
        if Category.objects.filter(name__iexact=name).exists():
            raise forms.ValidationError("This category already exists.")
        return name




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