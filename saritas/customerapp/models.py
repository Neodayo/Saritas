from django.db import models

# Create your models here.
class WardrobePackage(models.Model):
    PACKAGE_TIERS = [
        ("A", "Package A"),
        ("B", "Package B"), 
        ("C", "Package C"),
    ]
    
    name = models.CharField(max_length=255)
    tier = models.CharField(max_length=1, choices=PACKAGE_TIERS)
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    status = models.CharField(
        max_length=10,
        choices=[('active','Active'),('inactive','Inactive')],
        default='active'
    )
    
    def __str__(self):
        return f"{self.name} ({self.get_tier_display()})"