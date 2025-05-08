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
from core.utils.encryption import encrypt_id, encryption_service

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
    
    @property
    def encrypted_id(self):
        """Returns encrypted ID for URLs"""
        if not self.pk:
            return None
        try:
            return encrypt_id(self.pk)
        except Exception as e:
            logger.error(f"Failed to encrypt customer ID {self.pk}: {str(e)}")
            return None

    def get_absolute_url(self):
        """Use this in templates instead of building URLs manually"""
        if not self.encrypted_id:
            raise ValueError("Cannot generate URL - encryption failed")
        return reverse('view_customer', kwargs={'encrypted_id': self.encrypted_id})

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
    
    @property
    def encrypted_id(self):
        """Returns encrypted ID for URLs"""
        if not self.pk:
            return None
        try:
            return encrypt_id(self.pk)
        except Exception as e:
            logger.error(f"Failed to encrypt customer ID {self.pk}: {str(e)}")
            return None

    def get_absolute_url(self):
        """Use this in templates instead of building URLs manually"""
        if not self.encrypted_id:
            raise ValueError("Cannot generate URL - encryption failed")
        return reverse('view_customer', kwargs={'encrypted_id': self.encrypted_id})


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
    COMMON_SIZES = [
        ('XS', 'Extra Small'),
        ('S', 'Small'),
        ('M', 'Medium'),
        ('L', 'Large'),
        ('XL', 'Extra Large'),
        ('XXL', 'Double Extra Large'),
        ('XXXL', 'Triple Extra Large'),
        ('PS', 'Plus Size'),
        ('KS', 'Kid Size'),
        ('OS', 'One Size'),
    ]
    
    name = models.CharField(max_length=10, unique=True, choices=COMMON_SIZES)
    description = models.CharField(max_length=50, blank=True)

    def __str__(self):
        return self.get_name_display()
    
class Style(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return self.name

class Material(models.Model):   
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name
    
class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    
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
    

    def __str__(self):
        return self.get_name_display() 
    
    class Meta:
        ordering = ['name']

# --- Inventory Model ---
class Inventory(models.Model):
    # Basic Information
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    
    # Relationships
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, related_name="inventory_items")
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    item_type = models.ForeignKey(ItemType, on_delete=models.SET_NULL, null=True, blank=True)
    color = models.ForeignKey(Color, null=True, blank=True, on_delete=models.SET_NULL)
    style = models.ForeignKey(Style, null=True, blank=True, on_delete=models.SET_NULL)
    material = models.ForeignKey(Material, null=True, blank=True, on_delete=models.SET_NULL)
    tags = models.ManyToManyField(Tag, blank=True)
    
    # Inventory Management
    available = models.BooleanField(default=True)
    
    # Pricing Information
    rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    reservation_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Media
    image = models.ImageField(upload_to="inventory/", null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # First save the inventory to get a PK
        super().save(*args, **kwargs)
        # Then update availability based on sizes
        self.available = self.sizes.filter(quantity__gt=0).exists()
        super().save(update_fields=['available'])
        

    @property
    def calculated_quantity(self):
        return self.sizes.aggregate(total=models.Sum('quantity'))['total'] or 0

    def __str__(self):
        return f"{self.name} - {self.branch.branch_name}"
    
    @property
    def encrypted_id(self):
        """Returns encrypted ID for URLs with fallback to plain ID"""
        if not self.pk:
            return str(self.pk)  # Shouldn't happen for saved objects
        try:
            from core.utils.encryption import encrypt_id
            encrypted = encrypt_id(self.pk)
            if not encrypted or encrypted == str(self.pk):
                raise ValueError("Encryption returned invalid value")
            return encrypted
        except Exception as e:
            logger.warning(f"Encryption failed for item {self.pk}: {str(e)}")
            return str(self.pk) 

    class Meta:
        verbose_name_plural = "Inventory"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['category']),
            models.Index(fields=['available']),
            models.Index(fields=['item_type']),
            models.Index(fields=['branch']),
        ]

# --- Inventory Size Model ---
class InventorySize(models.Model):
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='sizes')
    size = models.ForeignKey(Size, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = ('inventory', 'size')
        verbose_name = 'Inventory Size'
        verbose_name_plural = 'Inventory Sizes'
        ordering = ['size__name']
    
    def __str__(self):
        return f"{self.inventory.name} - {self.size.name} (Qty: {self.quantity})"
    
    def clean(self):
        if self.quantity < 0:
            raise ValidationError("Quantity cannot be negative")
    
    def save(self, *args, **kwargs):
        if not self.inventory_id:  # Ensure inventory has been saved
            raise ValidationError("Inventory must be saved before adding sizes")
        super().save(*args, **kwargs)
        self.inventory.save()

# --- Rental Model (Corrected) ---
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

    CONDITION_EXCELLENT = "excellent"
    CONDITION_GOOD = "good"
    CONDITION_FAIR = "fair"
    CONDITION_POOR = "poor"

    CONDITION_CHOICES = [
        (CONDITION_EXCELLENT, "Excellent - No issues"),
        (CONDITION_GOOD, "Good - Minor wear"),
        (CONDITION_FAIR, "Fair - Needs cleaning/repair"),
        (CONDITION_POOR, "Poor - Significant damage"),
    ]

    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name="rentals")
    inventory_size = models.ForeignKey('InventorySize', on_delete=models.PROTECT, related_name="rentals")
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
    rejection_reason = models.TextField(blank=True, null=True)
    returned_date = models.DateField(null=True, blank=True)
    penalty_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # New fields for return processing
    return_condition = models.CharField(
        max_length=10,
        choices=CONDITION_CHOICES,
        null=True,
        blank=True
    )
    return_notes = models.TextField(blank=True, null=True)
    damage_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_returns"
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['rental_start', 'rental_end']),
            models.Index(fields=['returned_date']),
            models.Index(fields=['return_condition']),
        ]
        verbose_name = "Rental"
        verbose_name_plural = "Rentals"

    def __str__(self):
        return f"Rental #{self.id} - {self.customer} - {self.inventory_size.inventory.name} ({self.inventory_size.size})"

    def clean(self):
        if self.rental_end <= self.rental_start:
            raise ValidationError("Return date must be after the rental start date.")
        
        if not self.deposit:
            self.deposit = self.inventory_size.inventory.deposit_price or 0
        
        if self.status in [self.APPROVED, self.RENTED] and self.inventory_size.quantity <= 0:
            raise ValidationError("This size is no longer available for rent")

    @property
    def duration_days(self):
        return (self.rental_end - self.rental_start).days

    @property
    def total_cost(self):
        """Calculate total cost including any penalties and damage fees"""
        base_cost = float(self.inventory_size.inventory.rental_price) + float(self.deposit)
        return base_cost + float(self.penalty_fee) + float(self.damage_fee)

    @property
    def is_overdue(self):
        """Check if rental is currently overdue"""
        return self.status == self.OVERDUE or (
            self.status == self.RENTED and timezone.now().date() > self.rental_end
        )

    @property
    def days_overdue(self):
        """Calculate number of days overdue (0 if not overdue)"""
        if self.is_overdue:
            return (timezone.now().date() - self.rental_end).days
        return 0

    @property
    def calculated_penalty(self):
        """Calculate current penalty amount (100php per day per item)"""
        return self.days_overdue * 100

    @property
    def calculated_damage_fee(self, condition=None):
        """Calculate potential damage fee based on condition"""
        condition = condition or self.return_condition
        deposit = float(self.inventory_size.inventory.deposit_price)
        
        if condition == self.CONDITION_POOR:
            return deposit * 0.5  # 50% of deposit
        elif condition == self.CONDITION_FAIR:
            return deposit * 0.2  # 20% of deposit
        return 0

    def approve(self, user):
        if self.status != self.PENDING:
            raise ValidationError("Only pending rentals can be approved.")

        with transaction.atomic():
            if self.inventory_size.quantity <= 0:
                raise ValidationError("This size is no longer available for rent")
            
            self.inventory_size.quantity -= 1
            self.inventory_size.save()
            
            # Automatically set to Rented status when approved
            self.status = self.RENTED
            self.staff = user
            self.save()
            
    def reject(self, user, reason=""):
        if self.status != self.PENDING:
            raise ValidationError("Only pending rentals can be rejected")
        
        if not reason:
            raise ValidationError("Rejection reason is required")
            
        self.status = self.REJECTED
        self.staff = user
        self.rejection_reason = reason
        self.save()
        
    def mark_as_rented(self, user):
        if self.status != self.APPROVED:
            raise ValidationError("Only approved rentals can be marked as rented.")
        
        self.status = self.RENTED
        self.staff = user
        self.save()

    def is_rentable(self):
        """Check if rental can be marked as rented"""
        return (
            self.status == self.APPROVED and
            self.inventory_size.quantity > 0 and
            self.rental_start <= timezone.now().date()
        )

    def mark_as_returned(self, condition=None, notes=None, processed_by=None):
        """Mark rental as returned with proper error handling"""
        allowed_statuses = [self.RENTED, self.OVERDUE]
        if self.status not in allowed_statuses:
            raise ValidationError(
                f"Only rentals with status {allowed_statuses} can be returned. "
                f"Current status: {self.status}"
            )

        with transaction.atomic():
            # Save return details
            self.return_condition = condition
            self.return_notes = notes
            self.processed_by = processed_by
            
            # Calculate fees - ensure these are properties, not methods
            if condition:
                self.damage_fee = Decimal(str(self.calculated_damage_fee))  # Note: no parentheses
            
            if self.is_overdue:  # Note: property access, not method call
                self.penalty_fee = Decimal(str(self.calculated_penalty))  # Note: no parentheses
            
            # Return item to inventory
            self.inventory_size.quantity += 1
            self.inventory_size.save()
            
            # Update status and timestamps
            self.status = self.RETURNED
            self.returned_date = timezone.now().date()
            self.save()

    def mark_as_overdue(self):
        """Mark rental as overdue if not already returned"""
        if self.status in [self.RENTED] and timezone.now().date() > self.rental_end:
            self.status = self.OVERDUE
            self.save()

    @property
    def encrypted_id(self):
        """Returns encrypted ID for URLs"""
        if not self.pk:
            return None
        try:
            from core.utils.encryption import encrypt_id
            return encrypt_id(self.pk)
        except Exception as e:
            logger.error(f"Failed to encrypt rental ID {self.pk}: {str(e)}")
            return None

    def get_absolute_url(self):
        """Use this in templates for rental detail links"""
        if not self.encrypted_id:
            raise ValueError("Cannot generate URL - encryption failed")
        return reverse('saritasapp:rental_detail', kwargs={'encrypted_id': self.encrypted_id})

    def get_return_summary(self):
        """Generate a summary of return fees and conditions"""
        return {
            'condition': self.get_return_condition_display(),
            'damage_fee': self.damage_fee,
            'penalty_fee': self.penalty_fee,
            'total_fees': self.damage_fee + self.penalty_fee,
            'return_date': self.returned_date,
            'processed_by': self.processed_by.get_full_name() if self.processed_by else None
        }

# --- Reservation ---
class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Payment'),
        ('paid', 'Paid - Awaiting Pickup'),
        ('fulfilled', 'Fulfilled (Converted to Rental)'),
        ('expired', 'Expired (No Show)'),
        ('cancelled', 'Cancelled'),
    ]

    # Core Fields
    inventory_size = models.ForeignKey(
        'InventorySize',
        on_delete=models.PROTECT,
        related_name='reservations'
    )
    customer = models.ForeignKey(
        'Customer',
        on_delete=models.CASCADE,
        related_name='reservations'
    )
    staff = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_reservations'
    )
    
    # Timing
    reservation_date = models.DateTimeField(auto_now_add=True)
    pickup_deadline = models.DateTimeField()
    pickup_time = models.DateTimeField(null=True, blank=True)
    
    # Financials
    reservation_fee = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=500.00,
        validators=[MinValueValidator(500.00)],
        help_text="Minimum ₱500 reservation fee"
    )
    amount_paid = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00
    )
    
    # Status Tracking
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    payment_reference = models.CharField(max_length=100, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['reservation_date']
        indexes = [
            models.Index(fields=['status', 'pickup_deadline']),
            models.Index(fields=['inventory_size', 'status']),
        ]

    def __str__(self):
        return f"Reservation #{self.id} - {self.customer}"

    def clean(self):
        super().clean()
        
        # Ensure pickup deadline is in the future
        if self.pickup_deadline and self.pickup_deadline <= timezone.now():
            raise ValidationError("Pickup deadline must be in the future")
            
        # Validate payment meets minimum
        if self.amount_paid < 500 and self.status != 'pending':
            raise ValidationError("Minimum reservation fee is ₱500")

    def save(self, *args, **kwargs):
        # Auto-set pickup deadline if not specified (24 hours from now)
        if not self.pickup_deadline:
            self.pickup_deadline = timezone.now() + timedelta(hours=24)
            
        # Auto-update status based on payment
        if self.amount_paid >= 500 and self.status == 'pending':
            self.status = 'paid'
            
        super().save(*args, **kwargs)

    # === Core Business Methods ===

    @classmethod
    def create_reservation(cls, customer, inventory_size, amount_paid=500.00):
        """First-come-first-serve reservation with locking"""
        try:
            with transaction.atomic():
                # Lock inventory row
                item = InventorySize.objects.select_for_update().get(
                    pk=inventory_size.pk,
                    quantity__gt=0
                )
                
                # Create reservation
                reservation = cls.objects.create(
                    customer=customer,
                    inventory_size=item,
                    amount_paid=max(Decimal('500.00'), Decimal(str(amount_paid))),
                    status='paid' if amount_paid >= 500 else 'pending'
                )
                
                # Reduce available quantity
                item.quantity -= 1
                item.save()
                
                return reservation
                
        except InventorySize.DoesNotExist:
            raise ValidationError("This item size is no longer available")

    def convert_to_rental(self, staff_user):
        """Convert reservation to a rental upon pickup"""
        if self.status != 'paid':
            raise ValidationError("Only paid reservations can be converted")
            
        if timezone.now() > self.pickup_deadline:
            self.mark_as_expired()
            raise ValidationError("Pickup deadline has passed")

        with transaction.atomic():
            # Create the rental
            rental = Rental.objects.create(
                customer=self.customer,
                inventory_size=self.inventory_size,
                staff=staff_user,
                rental_start=timezone.now().date(),
                rental_end=timezone.now().date() + timedelta(days=7),  # Default 7-day rental
                deposit=self.inventory_size.inventory.deposit_price or 0,
                status=Rental.RENTED
            )
            
            # Update reservation status
            self.status = 'fulfilled'
            self.pickup_time = timezone.now()
            self.staff = staff_user
            self.save()
            
            return rental

    def mark_as_expired(self):
        """Handle no-show scenarios"""
        if self.status not in ['paid', 'pending']:
            return
            
        with transaction.atomic():
            # Return inventory
            self.inventory_size.quantity += 1
            self.inventory_size.save()
            
            # Update status (forfeit payment)
            self.status = 'expired'
            self.save()
            
            # TODO: Send notification to customer
            # notification.send(...)

    def cancel_reservation(self, refund_amount=0.00):
        """Cancel with partial refund"""
        if self.status != 'paid':
            raise ValidationError("Only paid reservations can be cancelled")
            
        if refund_amount > self.amount_paid:
            raise ValidationError("Refund cannot exceed amount paid")

        with transaction.atomic():
            # Return inventory
            self.inventory_size.quantity += 1
            self.inventory_size.save()
            
            # Update status
            self.status = 'cancelled'
            self.amount_paid -= Decimal(str(refund_amount))
            self.save()
            
            # Process refund
            # payment_service.process_refund(...)

    # === Utility Methods ===

    @property
    def is_active(self):
        return self.status in ['paid'] and timezone.now() <= self.pickup_deadline

    @property
    def time_remaining(self):
        if self.is_active:
            return self.pickup_deadline - timezone.now()
        return timedelta(0)

    @property
    def encrypted_id(self):
        """For secure URL generation"""
        return encrypt_id(self.pk) if self.pk else None

    def get_absolute_url(self):
        return reverse('reservation_detail', kwargs={'encrypted_id': self.encrypted_id})
        
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

    @property
    def encrypted_id(self):
        """Returns encrypted ID for URLs"""
        if not self.pk:
            logger.error(f"No PK found for package {self}")
            return None
        try:
            from core.utils.encryption import encrypt_id
            return encrypt_id(self.pk)
        except Exception as e:
            logger.error(f"Failed to encrypt package ID {self.pk}: {str(e)}")
            return None

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

    @property
    def encrypted_id(self):
        if not self.pk:
            return None
        try:
            return encrypt_id(self.pk)
        except Exception as e:
            logger.error(f"Failed to encrypt package item ID {self.pk}: {str(e)}")
            return None

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
    
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from saritasapp.models import Notification

class WardrobePackageRental(models.Model):
    PENDING = 'pending'
    APPROVED = 'approved'
    REJECTED = 'rejected'
    COMPLETED = 'completed'
    RETURNED = 'returned'
    OVERDUE = 'overdue'
    CANCELLED = 'cancelled'

    STATUS_CHOICES = [
        (PENDING, 'Pending'),
        (APPROVED, 'Approved'),
        (REJECTED, 'Rejected'),
        (COMPLETED, 'Completed'),
        (RETURNED, 'Returned'),
        (OVERDUE, 'Overdue'),
        (CANCELLED, 'Cancelled'),
    ]

    customer = models.ForeignKey('Customer', on_delete=models.CASCADE)
    package = models.ForeignKey('WardrobePackage', on_delete=models.CASCADE)  
    event_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Date fields
    pickup_date = models.DateField(null=True, blank=True)
    return_date = models.DateField(null=True, blank=True)
    actual_return_date = models.DateField(null=True, blank=True)
    
    # Staff fields
    staff = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='handled_rentals'
    )
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Wardrobe Package Rental'
        verbose_name_plural = 'Wardrobe Package Rentals'

    def __str__(self):
        return f"Package Rental #{self.id} - {self.get_status_display()}"

    @property
    def encrypted_id(self):
        """Returns encrypted ID for URLs"""
        return encrypt_id(self.pk)

    def get_absolute_url(self):
        return reverse('customerapp:package_rental_detail', args=[self.encrypted_id])

    def approve(self, user):
        """Approve the package rental"""
        if self.status != self.PENDING:
            raise ValidationError("Only pending rentals can be approved.")
        
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

            self.status = self.APPROVED
            self.staff = user
            self.save()
            
            # Send notification
            Notification.objects.create(
                user=self.customer.user,
                notification_type='rental_approved',
                message=f"Your rental request for package '{self.package.name}' has been approved!",
                url=reverse('customerapp:package_rental_detail', args=[self.encrypted_id])
            )

    def reject(self, user, reason=""):
        """Reject the package rental"""
        if self.status != self.PENDING:
            raise ValidationError("Only pending rentals can be rejected")
            
        if not reason:
            raise ValidationError("Rejection reason is required")
            
        self.status = self.REJECTED
        self.staff = user
        self.rejection_reason = reason
        self.save()
        
        # Send notification
        Notification.objects.create(
            user=self.customer.user,
            notification_type='rental_rejected',
            message=f"Your rental request for package '{self.package.name}' was rejected. Reason: {reason}",
            url=reverse('customerapp:package_rental_detail', args=[self.encrypted_id])
        )

    def mark_as_completed(self, user):
        """Mark rental as completed after event"""
        if self.status != self.APPROVED:
            raise ValidationError("Only approved rentals can be completed")
            
        self.status = self.COMPLETED
        self.staff = user
        self.save()

    def mark_as_returned(self, user, actual_return_date=None):
        """Mark items as returned and update inventory"""
        if self.status not in [self.APPROVED, self.COMPLETED]:
            raise ValidationError("Only approved/completed rentals can be returned")
        
        with transaction.atomic():
            # Return items to inventory
            for package_item in self.package.package_items.all():
                item = package_item.inventory_item
                item.quantity += package_item.quantity
                item.save()

            self.status = self.RETURNED
            self.staff = user
            self.actual_return_date = actual_return_date or timezone.now().date()
            self.save()

    @property
    def duration_days(self):
        """Calculate the rental period in days"""
        if self.pickup_date and self.return_date:
            return (self.return_date - self.pickup_date).days
        return 0

    @property
    def is_overdue(self):
        """Check if the package is overdue for return"""
        if self.status in [self.RETURNED, self.REJECTED, self.CANCELLED]:
            return False
        return self.return_date and self.return_date < timezone.now().date()

    def get_status_badge(self):
        """Return Bootstrap badge class for current status"""
        status_classes = {
            self.PENDING: 'bg-warning',
            self.APPROVED: 'bg-success',
            self.REJECTED: 'bg-danger',
            self.COMPLETED: 'bg-info',
            self.RETURNED: 'bg-secondary',
            self.OVERDUE: 'bg-danger',
            self.CANCELLED: 'bg-dark',
        }
        return status_classes.get(self.status, 'bg-secondary')

    def clean(self):
        """Validate the rental dates"""
        # Remove date validation since it's handled in the form
        if self.return_date and self.pickup_date and self.return_date <= self.pickup_date:
            raise ValidationError("Return date must be after pickup date")
        
        super().clean()

    def save(self, *args, **kwargs):
        """Override save to auto-set dates"""
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
    inventory_item = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name='package_rentals')
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