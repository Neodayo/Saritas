from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import F, Sum
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction


# --- Branch Model ---
class Branch(models.Model):
    branch_name = models.CharField(max_length=255, unique=True)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.branch_name

# --- User Model ---
class User(AbstractUser):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    branch = models.ForeignKey("saritasapp.Branch", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["name", "email"] 

    def __str__(self):
        return self.name if self.name else self.username

# --- Customer Model ---
class Customer(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    image = models.ImageField(upload_to="static/images/", null=True, blank=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# --- Category Model (For Inventory Items) ---
class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

# --- Inventory Model ---
class Inventory(models.Model):
    name = models.CharField(max_length=255)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    color = models.CharField(max_length=50, blank=True)
    quantity = models.IntegerField(default=0)
    rental_price = models.DecimalField(max_digits=10, decimal_places=2)
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    available = models.BooleanField(default=True)
    image = models.ImageField(upload_to="static/images/", null=True, blank=True)

    def save(self, *args, **kwargs):
        self.available = self.quantity > 0
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.color})" if self.color else self.name

# --- Event Package & Pricing ---
class EventPackage(models.Model):
    name = models.CharField(max_length=255)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()

    def __str__(self):
        return self.name

class PackageItem(models.Model):
    package = models.ForeignKey(EventPackage, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

ORDER_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Confirmed", "Confirmed"),
    ("Completed", "Completed"),
    ("Cancelled", "Cancelled"),
)

class CustomerOrder(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    package = models.ForeignKey(EventPackage, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default="Pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def calculate_total_price(self):
        total_price = (
            self.package.base_price +
            (self.selected_items.filter(selected=True).aggregate(total=Sum("item__price"))["total"] or 0)
        )
        self.total_price = total_price
        self.save(update_fields=["total_price"])

    def __str__(self):
        return f"Order #{self.id} - {self.status}"

class SelectedPackageItem(models.Model):
    order = models.ForeignKey(CustomerOrder, related_name="selected_items", on_delete=models.CASCADE)
    item = models.ForeignKey(PackageItem, on_delete=models.CASCADE)
    selected = models.BooleanField(default=True)

    def __str__(self):
        return f"Order {self.order.id} - Item {self.item.name} - {'Selected' if self.selected else 'Not Selected'}"

@receiver(post_save, sender=SelectedPackageItem)
@receiver(post_delete, sender=SelectedPackageItem)
def update_order_total(sender, instance, **kwargs):
    instance.order.calculate_total_price()

# --- Wardrobe Package (Connected to Inventory) ---
class WardrobePackage(models.Model):
    PACKAGE_TIERS = [
        ("A", "Package A (₱12,000)"),
        ("B", "Package B (₱15,000)"),
        ("C", "Package C (₱18,000)"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)  # Optional description
    tier = models.CharField(max_length=1, choices=PACKAGE_TIERS)
    base_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    refundable_deposit = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Optional discount
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

# --- Rental System ---
class Rental(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    rental_start = models.DateField()
    rental_end = models.DateField()
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    status = models.CharField(max_length=10, choices=[("Rented", "Rented"), ("Returned", "Returned")], default="Rented")

    def clean(self):
        if self.rental_end < self.rental_start:
            raise ValidationError("Return date must be after the rental start date.")
        if self.status == "Rented" and self.inventory.quantity <= 0:
            raise ValidationError(f"{self.inventory.name} is out of stock.")

    def save(self, *args, **kwargs):
        self.full_clean()
        with transaction.atomic():
            self.inventory.refresh_from_db()
            if self.pk:
                old_rental = Rental.objects.select_for_update().get(pk=self.pk)
                if old_rental.status != self.status:
                    if old_rental.status == "Rented" and self.status == "Returned":
                        Inventory.objects.filter(id=self.inventory.id).update(quantity=F("quantity") + 1)
                    elif old_rental.status == "Returned" and self.status == "Rented":
                        if self.inventory.quantity <= 0:
                            raise ValidationError(f"{self.inventory.name} is out of stock.")
                        Inventory.objects.filter(id=self.inventory.id).update(quantity=F("quantity") - 1)
            else:
                if self.inventory.quantity <= 0:
                    raise ValidationError(f"{self.inventory.name} is out of stock.")
                Inventory.objects.filter(id=self.inventory.id).update(quantity=F("quantity") - 1)
            super().save(*args, **kwargs)

    def __str__(self):
        return f"Rental #{self.id} - {self.status}"

#Calendar to
class Event(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateField()
    end = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title