from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models import F, Sum
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db import transaction

class Branch(models.Model):
    branch_name = models.CharField(max_length=255, unique=True)
    location = models.CharField(max_length=255)

    def __str__(self):
        return self.branch_name

class User(AbstractUser):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    branch = models.ForeignKey(Branch, null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name", "username"]

    def __str__(self):
        return self.name

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

class Category(models.Model):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

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

RENTAL_STATUS_CHOICES = (
    ("Rented", "Rented"),
    ("Returned", "Returned"),
)

class Rental(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    rental_start = models.DateField()
    rental_end = models.DateField()
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    
    RENTAL_STATUS_CHOICES = [
        ("Rented", "Rented"),
        ("Returned", "Returned"),
    ]
    status = models.CharField(max_length=10, choices=RENTAL_STATUS_CHOICES, default="Rented")

    def clean(self):
        """Validation rules before saving."""
        if self.rental_end < self.rental_start:
            raise ValidationError("Return date must be after the rental start date.")

        # Ensure inventory is available when renting
        if self.status == "Rented":
            inventory_quantity = Inventory.objects.filter(id=self.inventory.id).values_list("quantity", flat=True).first()
            if inventory_quantity is not None and inventory_quantity <= 0:
                raise ValidationError(f"{self.inventory.name} is out of stock.")

    def save(self, *args, **kwargs):
        """Handles inventory updates safely within a transaction."""
        self.full_clean()  # Run validations

        with transaction.atomic():  # Ensure database consistency
            self.inventory.refresh_from_db()  # Get latest inventory state

            if self.pk:  # Updating an existing rental
                old_rental = Rental.objects.select_for_update().get(pk=self.pk)

                # If status changes, update inventory accordingly
                if old_rental.status != self.status:
                    if old_rental.status == "Rented" and self.status == "Returned":
                        Inventory.objects.filter(id=self.inventory.id).update(quantity=F("quantity") + 1)
                    elif old_rental.status == "Returned" and self.status == "Rented":
                        if self.inventory.quantity <= 0:
                            raise ValidationError(f"{self.inventory.name} is out of stock.")
                        Inventory.objects.filter(id=self.inventory.id).update(quantity=F("quantity") - 1)
            else:  # Creating a new rental
                if self.inventory.quantity <= 0:
                    raise ValidationError(f"{self.inventory.name} is out of stock.")
                Inventory.objects.filter(id=self.inventory.id).update(quantity=F("quantity") - 1)

            super().save(*args, **kwargs)  # Save the rental instance

    def __str__(self):
        return f"Rental #{self.id} - {self.status}"


#Calendar to
class Event(models.Model):
    title = models.CharField(max_length=200)
    start = models.DateField()
    end = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.title