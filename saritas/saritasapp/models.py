from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction
from django.db.models import F
from django.core.exceptions import ValidationError


class Branch(models.Model):
    branch_name = models.CharField(max_length=255, unique=True)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.branch_name

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

class Staff(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="staff_profile")
    position = models.CharField(max_length=100)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.username} ({self.position})"

class Customer(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="customer_profile")
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="customers/", null=True, blank=True)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}"



# --- Category Model (For Inventory Items) ---
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

# --- Color Model ---
class Color(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name

# --- Size Model ---
class Size(models.Model):
    name = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return self.name

# --- Inventory Model ---
class Inventory(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="items")
    color = models.ForeignKey(Color, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_items")
    size = models.ForeignKey(Size, null=True, blank=True, on_delete=models.SET_NULL, related_name="inventory_items")
    quantity = models.IntegerField(default=0)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    reservation_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    available = models.BooleanField(default=True)
    image = models.ImageField(upload_to="inventory/", null=True, blank=True)

    def save(self, *args, **kwargs):
        self.available = self.quantity > 0
        super().save(*args, **kwargs)

    def __str__(self):
        details = [self.name]
        if self.color:
            details.append(f"Color: {self.color}")
        if self.size:
            details.append(f"Size: {self.size}")
        return " - ".join(details)


# --- Event Package & Pricing ---
class EventPackage(models.Model):
    name = models.CharField(max_length=255)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()

    def __str__(self):
        return self.name

class PackageItem(models.Model):
    SERVICE_TYPES = [
        ("internal", "Provided by Sarita's"),
        ("external", "Outsourced Service"),
    ]
    package = models.ForeignKey(EventPackage, on_delete=models.CASCADE, related_name="items")
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    service_type = models.CharField(max_length=10, choices=SERVICE_TYPES, default="internal")
    acquired = models.BooleanField(default=False)  # For external services

    def __str__(self):
        return f"{self.name} ({self.get_service_type_display()})"

class SelectedPackageItem(models.Model):
    order = models.ForeignKey("CustomerOrder", related_name="selected_items", on_delete=models.CASCADE)
    item = models.ForeignKey(PackageItem, on_delete=models.CASCADE)
    selected = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        # Automatically set 'acquired' to True for external services when selected
        if self.item.service_type == "external" and self.selected:
            self.item.acquired = True
            self.item.save()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Order {self.order.id} - Item {self.item.name} - {'Selected' if self.selected else 'Not Selected'}"

# --- Wardrobe Package (Connected to Inventory) ---
class WardrobePackage(models.Model):
    PACKAGE_TIERS = [
        ("A", "Package A (₱12,000)"),
        ("B", "Package B (₱15,000)"),
        ("C", "Package C (₱18,000)"),
    ]
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    tier = models.CharField(max_length=1, choices=PACKAGE_TIERS)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refundable_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")

    def final_price(self):
        return self.base_price - self.discount

    def __str__(self):
        return f"{self.name} - {self.get_tier_display()}"

class WardrobePackageItem(models.Model):
    package = models.ForeignKey(WardrobePackage, on_delete=models.CASCADE, related_name="package_items")
    inventory_item = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def clean(self):
        if self.quantity > self.inventory_item.quantity:
            raise ValidationError(f"Not enough stock for {self.inventory_item.name} in inventory.")

    def __str__(self):
        return f"{self.inventory_item.name} in {self.package.name}"

class SelectedWardrobeItem(models.Model):
    order = models.ForeignKey("CustomerOrder", related_name="selected_wardrobe_items", on_delete=models.CASCADE)
    wardrobe_package_item = models.ForeignKey(WardrobePackageItem, on_delete=models.CASCADE)
    selected_quantity = models.PositiveIntegerField(default=0)

    def clean(self):
        if self.selected_quantity > self.wardrobe_package_item.inventory_item.quantity:
            raise ValidationError(
                f"Not enough stock for {self.wardrobe_package_item.inventory_item.name}. Available: {self.wardrobe_package_item.inventory_item.quantity}"
            )

    def __str__(self):
        return f"Order {self.order.id} - {self.wardrobe_package_item.inventory_item.name} - Quantity: {self.selected_quantity}"

# --- Order System ---
ORDER_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Confirmed", "Confirmed"),
    ("Completed", "Completed"),
    ("Cancelled", "Cancelled"),
)

class CustomerOrder(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="orders")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="handled_orders")
    package = models.ForeignKey(EventPackage, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    wardrobe_package = models.ForeignKey(WardrobePackage, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_total_price(self):
        # Calculate total price from selected wedding package items
        wedding_total = sum(
            item.item.price for item in self.selected_items.filter(selected=True)
        )
        # Calculate total price from selected wardrobe package items
        wardrobe_total = sum(
            item.selected_quantity * item.wardrobe_package_item.inventory_item.rental_price
            for item in self.selected_wardrobe_items.all()
        )
        self.total_price = wedding_total + wardrobe_total
        self.save(update_fields=["total_price"])

    def __str__(self):
        return f"Order #{self.id} - {self.status}"

@receiver(post_save, sender=SelectedPackageItem)
@receiver(post_delete, sender=SelectedPackageItem)
def update_order_total(sender, instance, **kwargs):
    instance.order.calculate_total_price()

@receiver(post_save, sender=SelectedWardrobeItem)
@receiver(post_delete, sender=SelectedWardrobeItem)
def update_order_total(sender, instance, **kwargs):
    instance.order.calculate_total_price()

# --- Rental System ---
from django.db import models, transaction
from django.db.models import F
from django.core.exceptions import ValidationError
from django.utils import timezone
from saritasapp.models import Customer, Inventory, User

class Rental(models.Model):
    STATUS_CHOICES = [
        ("Pending", "Pending"),        # Waiting for staff approval
        ("Approved", "Approved"),      # Approved by staff but not yet active
        ("Rented", "Rented"),          # Currently rented out
        ("Returned", "Returned"),      # Item has been returned
        ("Overdue", "Overdue"),        # Item not returned by due date
        ("Cancelled", "Cancelled"),    # Cancelled before approval
        ("Rejected", "Rejected"),      # Rejected by staff
    ]
    
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name="rentals")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="managed_rentals")
    approved_by = models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="approved_rentals")
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE, related_name="rentals")
    rental_start = models.DateField(default=timezone.now, db_index=True)
    rental_end = models.DateField(db_index=True)
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="Pending", db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Rental"
        verbose_name_plural = "Rentals"
        indexes = [
            models.Index(fields=['rental_start', 'rental_end']),
            models.Index(fields=['status']),
            models.Index(fields=['created_at']),
        ]

    def clean(self):
        """Validates rental dates and inventory availability."""
        if self.rental_end < self.rental_start:
            raise ValidationError("Return date must be after the rental start date.")

        # Only check inventory if status is being set to Rented
        if self.status == "Rented" and self.inventory.quantity <= 0:
            raise ValidationError(f"{self.inventory.name} is out of stock.")

    def save(self, *args, **kwargs):
        """Handles inventory updates based on status changes."""
        self.full_clean()

        with transaction.atomic():
            self.inventory.refresh_from_db()
            
            if self.pk:
                # Existing rental - check for status changes
                old_rental = Rental.objects.select_for_update().get(pk=self.pk)
                
                if old_rental.status != self.status:
                    # Handle returns/cancellations
                    if old_rental.status == "Rented" and self.status in ["Returned", "Cancelled"]:
                        self.inventory.quantity += 1
                    
                    # Handle new rentals
                    elif old_rental.status in ["Pending", "Approved"] and self.status == "Rented":
                        if self.inventory.quantity <= 0:
                            raise ValidationError(f"{self.inventory.name} is out of stock.")
                        self.inventory.quantity -= 1
                        self.approved_at = timezone.now()
                    
                    # Handle approvals
                    elif old_rental.status == "Pending" and self.status == "Approved":
                        self.approved_by = self.user
                        self.approved_at = timezone.now()
            else:
                # New rental - only reduce inventory if immediately rented
                if self.status == "Rented":
                    if self.inventory.quantity <= 0:
                        raise ValidationError(f"{self.inventory.name} is out of stock.")
                    self.inventory.quantity -= 1
                    self.approved_at = timezone.now()

            self.inventory.save()
            super().save(*args, **kwargs)

    @property
    def duration_days(self):
        """Calculate rental duration in days."""
        return (self.rental_end - self.rental_start).days + 1  # Include both start and end days

    @property
    def days_left(self):
        """Days remaining until due date."""
        if self.status not in ["Rented", "Approved"]:
            return None
        return (self.rental_end - timezone.now().date()).days

    @property
    def total_cost(self):
        """Calculate total rental cost."""
        return self.duration_days * self.inventory.rental_price

    @property
    def is_active(self):
        """Check if rental is currently active."""
        return self.status in ["Rented", "Approved"] and timezone.now().date() <= self.rental_end

    @property
    def is_overdue(self):
        """Check if rental is overdue."""
        return self.status == "Rented" and timezone.now().date() > self.rental_end

    def approve(self, user):
        """Approve this rental request."""
        if self.status != "Pending":
            raise ValidationError("Only pending rentals can be approved.")
        
        self.status = "Approved"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save()

    def reject(self, user, reason=""):
        """Reject this rental request."""
        if self.status != "Pending":
            raise ValidationError("Only pending rentals can be rejected.")
        
        self.status = "Rejected"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    def mark_as_rented(self, user):
        """Mark an approved rental as rented (when customer picks up item)."""
        if self.status != "Approved":
            raise ValidationError("Only approved rentals can be marked as rented.")
        
        if self.inventory.quantity <= 0:
            raise ValidationError(f"{self.inventory.name} is out of stock.")
        
        self.status = "Rented"
        self.user = user
        self.inventory.quantity -= 1
        self.inventory.save()
        self.save()

    def __str__(self):
        return f"Rental #{self.id} - {self.get_status_display()} ({self.inventory.name})"
    
# --- Reservation System---
class Reservation(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]
    
    item = models.ForeignKey('Inventory', on_delete=models.CASCADE, related_name='reservations')
    customer = models.ForeignKey('Customer', on_delete=models.CASCADE, related_name='reservations')
    reservation_date = models.DateField()
    return_date = models.DateField()
    quantity = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, 
                                  related_name='approved_reservations')
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-reservation_date']
        verbose_name = 'Reservation'
        verbose_name_plural = 'Reservations'

    def __str__(self):
        return f"Reservation #{self.id} - {self.customer.user.get_full_name()} for {self.item.name}"

    def clean(self):
        if self.return_date < self.reservation_date:
            raise ValidationError("Return date must be after reservation date.")
        
        if self.quantity > self.item.quantity:
            raise ValidationError(f"Only {self.item.quantity} available. You requested {self.quantity}.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def duration_days(self):
        return (self.return_date - self.reservation_date).days + 1

    @property
    def total_cost(self):
        return self.duration_days * self.item.rental_price * self.quantity

    def approve(self, user):
        if self.status != 'pending':
            raise ValidationError("Only pending reservations can be approved.")
        
        self.status = 'approved'
        self.approved_by = user
        self.save()
        
        # Update inventory
        self.item.quantity -= self.quantity
        self.item.save()

    def reject(self, user, reason=None):
        if self.status != 'pending':
            raise ValidationError("Only pending reservations can be rejected.")
        
        self.status = 'rejected'
        self.approved_by = user
        self.notes = reason
        self.save()

    def cancel(self, user, reason=None):
        if self.status not in ['pending', 'approved']:
            raise ValidationError("Only pending or approved reservations can be cancelled.")
        
        if self.status == 'approved':
            # Return items to inventory
            self.item.quantity += self.quantity
            self.item.save()
        
        self.status = 'cancelled'
        self.notes = reason
        self.save()
    
    # --- Fitting Schedule System ---
class FittingAppointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    customer = models.ForeignKey(
        Customer, 
        on_delete=models.CASCADE,
        related_name='fitting_appointments'
    )
    inventory_item = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name='fitting_appointments'
    )
    branch = models.ForeignKey(
        Branch,
        on_delete=models.CASCADE,
        related_name='fitting_appointments'
    )
    staff = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_fittings'
    )
    scheduled_start = models.DateTimeField()
    scheduled_end = models.DateTimeField()
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='scheduled'
    )
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

