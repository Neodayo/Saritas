from django.contrib import admin
from .models import Receipt#receipt
from .models import Branch, User, EventPackage, PackageItem, CustomerOrder, SelectedPackageItem, Inventory, Category
# Register your models here.
admin.site.register(Branch)
admin.site.register(User)
admin.site.register(EventPackage)
admin.site.register(PackageItem)
admin.site.register(CustomerOrder)
admin.site.register(SelectedPackageItem)
admin.site.register(Inventory)
admin.site.register(Category)
#receipt
from django.contrib import admin
from .models import Receipt

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('customer_name', 'amount', 'payment_time', 'event_date', 'pickup_date', 'return_date')
    search_fields = ('customer_name', 'customer_number')
    list_filter = ('payment_method', 'event_date')