from django.urls import path
from . import views

app_name = 'customerapp'

urlpatterns = [
    path('', views.homepage, name='homepage'),
    path('inventory/<int:pk>/', views.product_detail, name='product_detail'),
    path('category/<int:pk>/', views.category_view, name='category_view'),  
    path('package/<int:pk>/', views.package_detail, name='package_detail'),


    path('register/', views.register, name='register'),
    path('login/', views.login_view, name='login'), 
    path('dashboard/', views.customer_dashboard, name='dashboard'),
    path('wardrobe/', views.wardrobe_view, name='wardrobe'),
    path('wardrobe/<int:item_id>/', views.item_detail, name='item_detail'),
    path('rental/<int:inventory_id>/', views.rent_item, name='rental'),
    path('reservation/<int:inventory_id>/', views.reserve_item, name='reservation'),
    path('logout/', views.logout_view, name='logout'),

]
