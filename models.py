from django.db import models
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import F
from django.core.exceptions import ValidationError

class Branch(models.Model):
    branch_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255)
    
    def __str__(self):
        return self.branch_name

class User(models.Model):
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    branch = models.ForeignKey("saritasapp.Branch", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True) 
    
    def __str__(self):
        return self.name
    

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
    ('Pending', 'Pending'),
    ('Confirmed', 'Confirmed'),
    ('Completed', 'Completed'),
    ('Cancelled', 'Cancelled'),
)

class CustomerOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    package = models.ForeignKey(EventPackage, on_delete=models.CASCADE)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=10, choices=ORDER_STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Order #{self.id} - {self.status}"


class SelectedPackageItem(models.Model):
    order = models.ForeignKey(CustomerOrder, on_delete=models.CASCADE)
    item = models.ForeignKey(PackageItem, on_delete=models.CASCADE)
    selected = models.BooleanField(default=True)
    
    def __str__(self):
        return f"Order {self.order.id} - Item {self.item.name} - {'Selected' if self.selected else 'Not Selected'}"


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
    image = models.ImageField(upload_to='static/images/', null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.color})" if self.color else self.name



RENTAL_STATUS_CHOICES = (
    ('Rented', 'Rented'),
    ('Returned', 'Returned'),
)

class Rental(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    inventory = models.ForeignKey(Inventory, on_delete=models.CASCADE)
    rental_start = models.DateField()
    rental_end = models.DateField()
    deposit = models.DecimalField(max_digits=10, decimal_places=2, default=10000.00)
    status = models.CharField(max_length=10, choices=RENTAL_STATUS_CHOICES, default='Rented')

    def save(self, *args, **kwargs):
        """Automatically update inventory quantity when a rental is created or updated."""
        if self.pk:  # If rental already exists (update case)
            old_rental = Rental.objects.get(pk=self.pk)
            if old_rental.status == 'Rented' and self.status == 'Returned':
                # Increase stock when an item is returned
                self.inventory.quantity = F('quantity') + 1
                self.inventory.save(update_fields=['quantity'])
        else:  # New rental (create case)
            if self.inventory.quantity <= 0:
                raise ValidationError(f"{self.inventory.name} is out of stock.")
            # Decrease stock when rented
            self.inventory.quantity = F('quantity') - 1
            self.inventory.save(update_fields=['quantity'])

        super().save(*args, **kwargs)

    def __str__(self):
        return f"Rental #{self.id} - {self.status}"