from django.contrib import admin
from .models import Branch, User, EventPackage, PackageItem, CustomerOrder, SelectedPackageItem, Inventory, Category, Rental, Customer, WardrobePackage, WardrobePackageItem, Event, WardrobePackageItem, WardrobePackageItem, WardrobePackageItem
# Register your models here.
admin.site.register(Branch)
admin.site.register(User)
admin.site.register(EventPackage)
admin.site.register(PackageItem)
admin.site.register(CustomerOrder)
admin.site.register(SelectedPackageItem)
admin.site.register(Inventory)
admin.site.register(Category)
admin.site.register(Rental)
admin.site.register(Customer)
admin.site.register(WardrobePackage)
admin.site.register(WardrobePackageItem)
admin.site.register(Event)

# Compare this snippet from saritas/saritasapp/forms.py:
# from django import forms 
# from .models import Inventory, Category