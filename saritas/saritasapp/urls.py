from django.urls import path
from . import views  

app_name = 'saritasapp'

urlpatterns = [
    path('add-inventory/', views.add_inventory, name='add_inventory'),
    path('inventory/', views.inventory_list, name='inventory_list'),
    path('add-category/', views.add_category, name='add_category'),
    path('inventory/<int:item_id>/', views.view_inventory, name='view_inventory'),
    path('inventory/<int:item_id>/edit/', views.edit_inventory, name='edit_inventory'), 
    path('inventory/<int:item_id>/delete/', views.delete_inventory, name='delete_inventory'), 
]
