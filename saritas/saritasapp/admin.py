from django.apps import AppConfig
from django.contrib import admin
from .models import ItemType, Staff, Branch, User, Receipt, EventPackage, Rental, PackageItem, CustomerOrder, SelectedPackageItem, Inventory, Category, WardrobePackage, WardrobePackageItem, Customer, Event, Color, Size

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

#receipt

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'amount', 'payment_time', 'event_date', 'pickup_date', 'return_date')
    search_fields = ('customer_name', 'customer_number')
    list_filter = ('payment_method', 'event_date')
