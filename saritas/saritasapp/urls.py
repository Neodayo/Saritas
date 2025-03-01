from django.urls import path
from . import views  

app_name = 'saritasapp'

urlpatterns = [
    path('add-inventory/', views.add_inventory, name='add_inventory'),
    path('inventory/', views.inventory_view, name='inventory_list'),
    path('add-category/', views.add_category, name='add_category'),
    path('inventory/<int:item_id>/', views.view_inventory, name='view_inventory'),
    path('inventory/<int:item_id>/edit/', views.edit_inventory, name='edit_inventory'), 
    path('inventory/<int:item_id>/delete/', views.delete_inventory, name='delete_inventory'),
    path("rental/<int:inventory_id>/", views.rent_item, name="rental"),
    path("customer/add/", views.add_customer, name="add_customer"),
    path("customer/list/", views.customer_list, name="customer_list"),
    path('customers/<int:customer_id>/', views.view_customer, name='view_customer'),
    path('rental/return/<int:rental_id>/', views.return_rental, name='return_rental'),
]
