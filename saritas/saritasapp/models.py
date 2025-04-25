from datetime import timedelta
from decimal import Decimal
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator, URLValidator
from django.db import models, transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.urls import reverse
from django.utils import timezone
from django.conf import settings
from django.db.models.signals import post_migrate
import logging
from core.utils.encryption import encryption_service

logger = logging.getLogger(__name__)

# --- Branch ---
class Branch(models.Model):
    branch_name = models.CharField(max_length=255, unique=True)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.branch_name


# --- Custom User ---
class User(AbstractUser):
    ROLE_CHOICES = [
        ('staff', 'Staff'),
        ('customer', 'Customer'),
    ]

    email = models.EmailField(unique=True)
    branch = models.ForeignKey(Branch, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"

    @property
    def is_admin(self):
        return self.is_superuser

    @property
    def is_staff_user(self):
        return self.role == 'staff' or self.is_staff

    def save(self, *args, **kwargs):
        if self.role == 'staff':
            self.is_staff = True
        super().save(*args, **kwargs)


# --- Staff ---
class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    position = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} ({self.position})"


# --- Customer ---
class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="customers/", null=True, blank=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"

    @property
    def first_name(self):
        return self.user.first_name

    @property
    def last_name(self):
        return self.user.last_name

    @property
    def email(self):
        return self.user.email


# --- Inventory Support Models ---
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

class Size(models.Model):
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

class ItemType(models.Model):
    ITEM_TYPES = [
        ('bridal_gown', 'Bridal Gown'),
        ('groom_tuxedo', 'Groom\'s Tuxedo'),
        ('maid_of_honor', 'Maid of Honor'),
        ('bestman', 'Bestman'),
        ('bridesmaid', 'Bridesmaid'),
        ('groomsmen', 'Groomsmen'),
        ('flowergirl', 'Flowergirl'),
        ('bearer', 'Bearer'),
        ('mother_gown', 'Mother\'s Gown'),
        ('father_attire', 'Father\'s Suit'),
        ('other', 'Other'),
    ]
    
    name = models.CharField(
        max_length=50,
        choices=ITEM_TYPES,
        unique=True
    )
    
    @classmethod
    def initialize_choices(cls):
        for value, label in cls.ITEM_TYPES:
            cls.objects.get_or_create(name=value)

    def __str__(self):
        return self.get_name_display()
# --- Inventory ---
class Inventory(models.Model):
    name = models.CharField(max_length=255)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="inventory_items")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    item_type = models.ForeignKey(ItemType, on_delete=models.SET_NULL, null=True, blank=True)
    color = models.ForeignKey(Color, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_items")
    size = models.ForeignKey(Size, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_items")
    quantity = models.IntegerField(default=0)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    reservation_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    available = models.BooleanField(default=True)
    image = models.ImageField(upload_to="inventory/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        self.available = self.quantity > 0
        super().save(*args, **kwargs)

    def __str__(self):
        details = [self.name, f"Branch: {self.branch.branch_name}"]
        if self.color:
            details.append(f"Color: {self.color}")
        if self.size:
            details.append(f"Size: {self.size}")
        return " - ".join(details)

    def display_name(self):
        return f"{self.name} ({self.category.name}) - Size: {self.size}, Color: {self.color}"

    class Meta:
        verbose_name_plural = "Inventory"
        ordering = ['-created_at']



# --- Rental ---
class Rental(models.Model):
    PENDING = "Pending"
    APPROVED = "Approved"
    RENTED = "Rented"
    RETURNED = "Returned"
    OVERDUE = "Overdue"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"

    STATUS_CHOICES = [
        (PENDING, "Pending"),
        (APPROVED, "Approved"),
        (RENTED, "Rented"),
        (RETURNED, "Returned"),
        (OVERDUE, "Overdue"),
        (CANCELLED, "Cancelled"),
        (REJECTED, "Rejected"),
    ]

    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name="rentals")
    inventory = models.ForeignKey('Inventory', on_delete=models.CASCADE, related_name="rentals")
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_rentals"
    )
    rental_start = models.DateField(default=timezone.now)
    rental_end = models.DateField()
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True, null=True)
    inventory_decremented = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rental_start', 'rental_end']),
        ]

    def __str__(self):
        return f"Rental #{self.id} - {self.customer} - {self.inventory}"

    def clean(self):
        if not hasattr(self, 'inventory') or not self.inventory:
            raise ValidationError("Inventory item is required")
        
        if self.rental_end <= self.rental_start:
            raise ValidationError("Return date must be after the rental start date.")
        
        if not self.deposit and hasattr(self, 'inventory') and self.inventory:
            self.deposit = self.inventory.deposit_price or 0

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration_days(self):
        return (self.rental_end - self.rental_start).days

    @property
    def total_cost(self):
        return float(self.inventory.rental_price) + float(self.deposit)
    
    @property
    def encrypted_id(self):
        """Returns encrypted ID or None if encryption fails"""
        if not self.pk:
            return None
        try:
            return encrypt_id(self.pk)
        except Exception as e:
            logger.error(f"Failed to encrypt rental ID {self.pk}: {str(e)}")
            return None

    def get_encrypted_id(self):
        """Returns encrypted ID or raises exception if fails"""
        encrypted = self.encrypted_id
        if not encrypted:
            raise ValueError(f"Encryption failed for rental ID {self.pk}")
        return encrypted

    def approve(self, user):
        if self.status != self.PENDING:
            raise ValidationError("Only pending rentals can be approved.")

        with transaction.atomic():
            if not self.inventory_decremented:
                self.inventory.quantity -= 1
                self.inventory.save()
                self.inventory_decremented = True
            
            self.status = self.APPROVED
            self.staff = user
            self.save()

    def mark_as_rented(self, user):
        if self.status != self.APPROVED:
            raise ValidationError("Only approved rentals can be marked as rented.")
        
        self.status = self.RENTED
        self.staff = user
        self.save()

    def mark_as_returned(self):
        if self.status not in [self.RENTED, self.OVERDUE]:
            raise ValidationError("Only rented or overdue items can be returned.")

        with transaction.atomic():
            self.inventory.quantity += 1
            self.inventory.save()
            self.status = self.RETURNED
            self.save()

# --- Reservation ---
class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    item = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='reservations')
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='reservations')
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_reservations'
    )
    reservation_date = models.DateField(default=timezone.now)
    return_date = models.DateField()
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    reservation_price = models.DecimalField(
        max_digits=8, decimal_places=2,
        default=500.00,
        editable=False,
        validators=[MinValueValidator(500.00), MaxValueValidator(500.00)],
        help_text="Flat reservation fee of ₱500.00 per item"
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2, editable=False, default=0.00)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def clean(self):
        today = timezone.now().date()

        if self.reservation_date < today:
            raise ValidationError("Reservation date cannot be in the past.")

        if self.return_date <= self.reservation_date:
            raise ValidationError("Return date must be after the reservation date.")

        # Make sure item exists before checking its quantity
        if self.item and self.quantity > self.item.quantity:
            raise ValidationError(f"Only {self.item.quantity} items available for reservation.")

    def save(self, *args, **kwargs):
        self.total_price = self.quantity * self.reservation_price
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Reservation #{self.pk} by {self.customer.user.username} for '{self.item.name}'"

    
    # --- Fitting Schedule System ---
class FittingAppointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE,related_name='fitting_appointments')
    inventory_item = models.ForeignKey(Inventory,on_delete=models.CASCADE,related_name='fitting_appointments')
    branch = models.ForeignKey(Branch,on_delete=models.CASCADE,related_name='fitting_appointments')
    staff = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name='managed_fittings')
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(max_length=10,choices=STATUS_CHOICES,default='scheduled')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """Validate fitting schedule constraints"""
        # Ensure fitting is in the future
        if self.scheduled_start < timezone.now():
            raise ValidationError("Fitting time must be in the future")
            
        # Check item availability
        conflicting_rentals = self.inventory_item.rentals.filter(
            rental_start__lte=self.scheduled_end,
            rental_end__gte=self.scheduled_start,
            status='Rented'
        ).exists()
        
        if conflicting_rentals:
            raise ValidationError("Item is rented during this time slot")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Fitting #{self.id} - {self.get_status_display()}"
    
# --- Notification System ---
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('rental_approved', 'Rental Approved'),
        ('rental_rejected', 'Rental Rejected'),
        ('rental_completed', 'Rental Completed'),
        ('reservation_approved', 'Reservation Approved'),
        ('reservation_rejected', 'Reservation Rejected'),
        ('reservation_completed', 'Reservation Completed'),
        ('payment_required', 'Payment Required'),
        ('payment_received', 'Payment Received'),
        ('rental_reminder', 'Rental Reminder'),
        ('return_reminder', 'Return Reminder'),
        ('system_alert', 'System Alert'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    rental = models.ForeignKey('Rental', on_delete=models.CASCADE, null=True, blank=True)
    reservation = models.ForeignKey('Reservation', on_delete=models.CASCADE, null=True, blank=True)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    is_email_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    url = models.URLField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'

    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.user.username}"

    def save(self, *args, **kwargs):
        if not self.url:
            try:
                if self.rental:
                    self.url = reverse('customerapp:rental_detail', args=[self.rental.id])
                elif self.reservation:
                    self.url = reverse('customerapp:reservation_detail', args=[self.reservation.id])
            except:
                self.url = None
        super().save(*args, **kwargs)

    def clean(self):
        if self.url:
            validator = URLValidator()
            try:
                validator(self.url)
            except ValidationError:
                raise ValidationError({'url': 'Enter a valid URL'})

    def mark_as_read(self):
        self.is_read = True
        self.save()

    @classmethod
    def get_unread_count(cls, user):
        return cls.objects.filter(user=user, is_read=False).count()

    @classmethod
    def mark_all_as_read(cls, user):
        return cls.objects.filter(user=user, is_read=False).update(is_read=True)
    
from django.db import models
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError

class WardrobePackage(models.Model):
    PACKAGE_TIERS = [
        ("A", "Package A"),
        ("B", "Package B"),
        ("C", "Package C"),
    ]

    STATUS_CHOICES = [
        ("fixed", "Fixed Composition"),
        ("customizable", "Customizable"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    tier = models.CharField(
        max_length=10, 
        choices=PACKAGE_TIERS, 
        blank=True, 
        null=True,
        help_text="Predefined package tier (A, B, C)"
    )
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)]
    )
    deposit_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=10000.00,
        validators=[MinValueValidator(0)],
        help_text="Refundable deposit amount"
    )
    discount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0)]
    )
    status = models.CharField(
        max_length=15, 
        choices=STATUS_CHOICES, 
        default="fixed",
        help_text="Fixed packages cannot be modified by customers"
    )
    min_rental_days = models.PositiveIntegerField(
        default=1,
        help_text="Minimum rental period for this package"
    )
    includes_accessories = models.BooleanField(
        default=False,
        help_text="Does this package include free accessories?"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['tier', 'base_price']
        verbose_name_plural = "Wardrobe Packages"

    def clean(self):
        if self.tier and self.tier != 'custom' and self.status == 'customizable':
            raise ValidationError("Predefined packages (A, B, C) must be fixed composition")
            
    def final_price(self):
        """Calculate price after discounts"""
        return max(self.base_price - self.discount, 0)

    def total_price(self):
        """Total upfront payment required"""
        return self.final_price() + self.deposit_price

    def get_required_items(self):
        """Returns required items that cannot be removed during customization"""
        if self.status == 'fixed':
            return self.package_items.all()
        return self.package_items.filter(is_required=True)

    def __str__(self):
        display_name = f"{self.get_tier_display()}" if self.tier else "Custom Package"
        return f"{display_name} - ₱{self.base_price:,.2f}"


class WardrobePackageItem(models.Model):
    package = models.ForeignKey(
        WardrobePackage,
        on_delete=models.CASCADE,
        related_name="package_items"
    )
    inventory_item = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        limit_choices_to={'available': True}
    )
    quantity = models.PositiveIntegerField(default=1)
    is_required = models.BooleanField(
        default=True,
        help_text="Whether this item is mandatory for the package"
    )
    label = models.CharField(
        max_length=255,
        blank=True,
        help_text="Display label (e.g., 'Barong/Vest')"
    )
    replacement_allowed = models.BooleanField(
        default=True,
        help_text="Can this item be replaced in customizations?"
    )

    class Meta:
        unique_together = ('package', 'inventory_item')
        ordering = ['package', '-is_required']

    def clean(self):
        if self.quantity > self.inventory_item.quantity:
            raise ValidationError(
                f"Not enough stock for {self.inventory_item.name}. Available: {self.inventory_item.quantity}"
            )
        if not self.replacement_allowed and not self.is_required:
            raise ValidationError("Non-replaceable items must be required")

    def display_name(self):
        return self.label or f"{self.inventory_item.category.name} x{self.quantity}"

    def __str__(self):
        return f"{self.package.name}: {self.display_name()}"


class CustomizedWardrobePackage(models.Model):
    CUSTOMIZATION_STATUS = [
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name='custom_packages'
    )
    base_package = models.ForeignKey(
        WardrobePackage,
        on_delete=models.CASCADE,
        limit_choices_to={'status__in': ['fixed', 'customizable']}
    )
    status = models.CharField(
        max_length=20,
        choices=CUSTOMIZATION_STATUS,
        default='draft'
    )
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    customization_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_price = models.DecimalField(max_digits=10, decimal_places=2)
    notes = models.TextField(blank=True)
    staff_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def save(self, *args, **kwargs):
        if not self.pk:  # New instance
            self.base_price = self.base_package.final_price()
            self.deposit_price = self.base_package.deposit_price
        
        self.total_price = self.base_price + self.deposit_price + self.customization_fee
        super().save(*args, **kwargs)

    def get_changes(self):
        """Returns a summary of customizations made"""
        changes = []
        for item in self.modifications.all():
            changes.append(str(item))
        return changes

    def __str__(self):
        return f"Custom {self.base_package.name} for {self.customer} ({self.get_status_display()})"


class PackageCustomization(models.Model):
    ACTION_CHOICES = [
        ('add', 'Add Item'),
        ('remove', 'Remove Item'),
        ('replace', 'Replace Item'),
        ('quantity', 'Adjust Quantity')
    ]

    customized_package = models.ForeignKey(
        CustomizedWardrobePackage,
        on_delete=models.CASCADE,
        related_name='modifications'
    )
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    original_item = models.ForeignKey(
        WardrobePackageItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    inventory_item = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    new_quantity = models.PositiveIntegerField(null=True, blank=True)
    price_adjustment = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = "Package Customization"
        verbose_name_plural = "Package Customizations"

    def clean(self):
        # Validate based on action type
        if self.action in ['replace', 'remove', 'quantity'] and not self.original_item:
            raise ValidationError("Original item is required for this action")
        if self.action in ['add', 'replace'] and not self.inventory_item:
            raise ValidationError("Inventory item is required for this action")
        if self.action == 'quantity' and not self.new_quantity:
            raise ValidationError("New quantity is required for quantity adjustments")

    def __str__(self):
        action_map = {
            'add': f"Added {self.inventory_item}",
            'remove': f"Removed {self.original_item}",
            'replace': f"Replaced {self.original_item} with {self.inventory_item}",
            'quantity': f"Changed quantity of {self.original_item} to {self.new_quantity}"
        }
        return action_map.get(self.action, "Customization")


class OrderWardrobePackage(models.Model):
    order = models.ForeignKey(
        "CustomerOrder",
        on_delete=models.CASCADE,
        related_name='wardrobe_packages'
    )
    package = models.ForeignKey(
        WardrobePackage,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    customized_package = models.ForeignKey(
        CustomizedWardrobePackage,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    quantity = models.PositiveIntegerField(default=1)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()

    class Meta:
        verbose_name = "Ordered Wardrobe Package"
        verbose_name_plural = "Ordered Wardrobe Packages"

    @property
    def is_custom(self):
        return self.customized_package is not None

    def get_package_name(self):
        if self.customized_package:
            return f"Custom {self.customized_package.base_package.name}"
        return self.package.name

    def __str__(self):
        return f"{self.get_package_name()} for Order #{self.order.id}"

class ExternalService(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    provider_name = models.CharField(max_length=255)  # Name of the service provider
    provider_phone = models.CharField(max_length=20)  # Phone number of the service provider
    provider_email = models.EmailField()             # Email of the service provider
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} (Provider: {self.provider_name})"
    
class Service(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.name} - ₱{self.price}"
    
class EventPackage(models.Model):
    name = models.CharField(max_length=255)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()

    def __str__(self):
        return self.name

class PackageItem(models.Model):
    package = models.ForeignKey(EventPackage, on_delete=models.CASCADE, related_name="items")
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )
    external_service = models.ForeignKey(
        ExternalService,
        on_delete=models.CASCADE,
        null=True,
        blank=True
    )

    def clean(self):
        """Ensure that either 'service' or 'external_service' is selected, but not both."""
        if not self.service and not self.external_service:
            raise ValidationError("Either 'service' or 'external_service' must be selected.")
        if self.service and self.external_service:
            raise ValidationError("Only one of 'service' or 'external_service' can be selected.")

    def __str__(self):
        if self.service:
            return f"Internal Service: {self.service.name}"
        elif self.external_service:
            return f"External Service: {self.external_service.name} (Provider: {self.external_service.provider_name})"

class SelectedPackageItem(models.Model):
    order = models.ForeignKey("CustomerOrder", related_name="selected_items", on_delete=models.CASCADE)
    item = models.ForeignKey(PackageItem, on_delete=models.CASCADE)
    selected = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order.id} - Item {self.item} - {'Selected' if self.selected else 'Not Selected'}"


class CustomerOrder(models.Model):
    ORDER_STATUS_CHOICES = (
        ("Pending", "Pending"),
        ("Confirmed", "Confirmed"),
        ("Completed", "Completed"),
        ("Cancelled", "Cancelled"),
    )
    customer = models.ForeignKey(
        Customer,
        on_delete=models.CASCADE,
        related_name="orders"
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="handled_orders"
    )
    package = models.ForeignKey(
        EventPackage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders"
    )
    wardrobe_package = models.ForeignKey(
        WardrobePackage,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders"
    )
    total_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True
    )
    status = models.CharField(
        max_length=10,
        choices=ORDER_STATUS_CHOICES,
        default="Pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_total_price(self):
        """
        Calculate the total price of the order by summing up:
        1. The base price of the wardrobe package.
        2. The prices of selected items.
        3. The deposit price.
        """
        # Base price of the wardrobe package
        wardrobe_total = self.wardrobe_package.final_price() if self.wardrobe_package else 0

        # Add prices of selected wardrobe package items
        wardrobe_total += sum(
            item.selected_quantity * item.wardrobe_package_item.inventory_item.rental_price
            for item in self.selected_wardrobe_items.all()
        )

        # Include deposit price
        deposit_price = self.wardrobe_package.deposit_price if self.wardrobe_package else 0

        self.total_price = wardrobe_total + deposit_price
        self.save(update_fields=["total_price"])

    def create_package_rental(self, package, customized_package=None, rental_start=None, rental_end=None):
        """
        Helper method to create a package rental from an order
        """
        rental = WardrobePackageRental.objects.create(
            customer=self.customer,
            order=self,
            package=package,
            customized_package=customized_package,
            rental_start=rental_start,
            rental_end=rental_end
        )
        
        # Add inventory items to the rental
        if customized_package:
            # Handle customized package items
            pass
        else:
            # Handle standard package items
            for item in package.package_items.all():
                PackageRentalItem.objects.create(
                    package_rental=rental,
                    inventory_item=item.inventory_item,
                    quantity=item.quantity,
                    rental_price=item.inventory_item.rental_price
                )
        
        return rental
    
class WardrobePackageRental(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('returned', 'Returned'),  # Added returned status
    ]

    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    package = models.ForeignKey(WardrobePackage, on_delete=models.PROTECT)
    event_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Date fields
    pickup_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)  # Added this field
    
    # Staff fields
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_rentals'
    )
    notes = models.TextField(blank=True, null=True)
    
    def approve(self, staff_user):
        """Approve the package rental and handle inventory"""
        if self.status != 'pending':
            raise ValidationError("Only pending rentals can be approved")
        
        with transaction.atomic():
            # Check inventory for all items in the package
            for package_item in self.package.package_items.all():
                item = package_item.inventory_item
                if item.quantity < package_item.quantity:
                    raise ValidationError(
                        f"Not enough stock for {item.name}. "
                        f"Available: {item.quantity}, Needed: {package_item.quantity}"
                    )
            
            # Update inventory if all checks pass
            for package_item in self.package.package_items.all():
                item = package_item.inventory_item
                item.quantity -= package_item.quantity
                item.save()

            self.status = 'approved'
            self.staff = staff_user
            self.save()

    def reject(self, staff_user, reason=""):
        """Reject the package rental with optional reason"""
        if self.status != 'pending':
            raise ValidationError("Only pending rentals can be rejected")
            
        self.status = 'rejected'
        self.staff = staff_user
        self.notes = reason or "Rental rejected by staff"
        self.save()

    def mark_as_completed(self, staff_user):
        """Mark rental as completed after event"""
        if self.status != 'approved':
            raise ValidationError("Only approved rentals can be completed")
            
        self.status = 'completed'
        self.staff = staff_user
        self.save()

    def mark_as_returned(self, staff_user, actual_return_date=None):
        """Mark items as returned and update inventory"""
        if self.status not in ['approved', 'completed']:
            raise ValidationError("Only approved/completed rentals can be returned")
        
        with transaction.atomic():
            # Return items to inventory
            for package_item in self.package.package_items.all():
                item = package_item.inventory_item
                item.quantity += package_item.quantity
                item.save()

            self.status = 'returned'
            self.staff = staff_user
            self.actual_return_date = actual_return_date or timezone.now().date()
            self.save()

    @property
    def is_overdue(self):
        """Check if the package is overdue for return"""
        if self.status in ['returned', 'rejected']:
            return False
        return self.return_date and self.return_date < timezone.now().date()

    def get_status_badge(self):
        """Return Bootstrap badge class for current status"""
        status_classes = {
            'pending': 'bg-warning',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'completed': 'bg-info',
            'returned': 'bg-secondary',
        }
        return status_classes.get(self.status, 'bg-secondary')

    def clean(self):
        """Validate the rental dates"""
        if self.event_date and self.event_date < timezone.now().date():
            raise ValidationError("Event date cannot be in the past")
            
        if self.return_date and self.pickup_date and self.return_date <= self.pickup_date:
            raise ValidationError("Return date must be after pickup date")
        
        super().clean()

    def save(self, *args, **kwargs):
        """Override save to include validation and auto-set dates"""
        self.full_clean()
        
        # Auto-set pickup and return dates if not set
        if self.event_date and not self.pickup_date:
            self.pickup_date = self.event_date - timedelta(days=1)
            self.return_date = self.event_date + timedelta(days=1)
            
        super().save(*args, **kwargs)
    
class PackageRentalItem(models.Model):
    CONDITION_CHOICES = [
        ('excellent', 'Excellent - No visible wear'),
        ('good', 'Good - Minor wear'),
        ('fair', 'Fair - Some wear but functional'),
        ('poor', 'Poor - Significant wear/damage'),
        ('damaged', 'Damaged - Needs repair'),
    ]

    package_rental = models.ForeignKey(WardrobePackageRental, on_delete=models.CASCADE, related_name='rented_items')
    inventory_item = models.ForeignKey(Inventory, on_delete=models.PROTECT, related_name='package_rentals')
    quantity = models.PositiveIntegerField(default=1)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Return information
    returned = models.BooleanField(default=False)
    returned_date = models.DateField(null=True, blank=True)
    condition = models.CharField(max_length=20, choices=CONDITION_CHOICES, blank=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        unique_together = ('package_rental', 'inventory_item')
        verbose_name = 'Rented Package Item'
        verbose_name_plural = 'Rented Package Items'

    def __str__(self):
        return f"{self.inventory_item.name} (x{self.quantity}) in Package Rental #{self.package_rental_id}"

    def save(self, *args, **kwargs):
        if not self.pk and not self.rental_price:
            self.rental_price = self.inventory_item.rental_price
        super().save(*args, **kwargs)
    
# --- Calendar/Event Model ---
class Event(models.Model):
    title = models.CharField(max_length=200)
    venue = models.CharField(max_length=255)
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title

# --- Receipt Model ---
class Receipt(models.Model):
    customer_name = models.CharField(max_length=255)
    customer_number = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True)
    down_payment = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, blank=True, null=True)

    # Measurements
    shoulder = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    bust = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    front = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    width = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    waist = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    hips = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    arm_length = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    bust_depth = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    bust_distance = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    length = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    lower_circumference = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)
    crotch = models.DecimalField(max_digits=5, decimal_places=2, default=0.00, blank=True, null=True)

    payment_time = models.DateTimeField(null=True, blank=True)
    event_date = models.DateField(null=True, blank=True)
    pickup_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(
        max_length=50,
        choices=[('Cash', 'Cash'), ('Credit Card', 'Credit Card'), ('Bank Transfer', 'Bank Transfer')]
    )
    remarks = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Receipt for {self.customer_name}"

#packages wedding packages

class Venue(models.Model):
    name = models.CharField(max_length=255)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_custom = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)