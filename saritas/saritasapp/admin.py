from django.apps import AppConfig
from django.contrib import admin
from .models import ItemType, Staff, Branch, User, Receipt, EventPackage, Rental, PackageItem, CustomerOrder, SelectedPackageItem, Inventory, Category, WardrobePackage, WardrobePackageItem, Customer, Event, Color, Size, WardrobePackageRental

# Register your models here.
admin.site.register(Branch)
admin.site.register(User)
admin.site.register(EventPackage)
admin.site.register(PackageItem)
admin.site.register(CustomerOrder)
admin.site.register(SelectedPackageItem)
admin.site.register(Inventory)
admin.site.register(Category)
admin.site.register(WardrobePackage)
admin.site.register(WardrobePackageItem)
admin.site.register(Customer)
admin.site.register(Event)
admin.site.register(Rental)
admin.site.register(Color)
admin.site.register(Size)
admin.site.register(Staff)
admin.site.register(ItemType)

class SaritasappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'saritasapp'

    def ready(self):
        import saritasapp.signals

# Receipt Admin
@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'amount', 'payment_time', 'event_date', 'pickup_date', 'return_date')
    search_fields = ('customer_name', 'customer_number')
    list_filter = ('payment_method', 'event_date')

# Combined WardrobePackageRental Admin (single registration)
@admin.register(WardrobePackageRental)
class RentalAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'package', 'event_date', 'status', 'actual_return_date')
    list_filter = ('status', 'event_date')
    search_fields = ('customer__user__username', 'package__name')
