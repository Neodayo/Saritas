from django.urls import path
from . import views 
from .views import receipt_detail, update_receipt, generate_receipt_pdf

app_name = 'saritasapp'

urlpatterns = [
    path('', views.homepage, name='homepage'),
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
    #data analysis
    path('data-analysis/', views.data_analysis, name='data_analysis'),
    #calendar
    path("calendar/", views.calendar_view, name="calendar"),
    path("ongoing-events/", views.ongoing_events, name="ongoing_events"),
    path("upcoming-events/", views.upcoming_events, name="upcoming_events"),
    path("past-events/", views.past_events, name="past_events"),
    path("create-event/", views.create_event, name="create_event"),
    path("view-event/<int:event_id>/", views.view_event, name="view_event"),
    path("api/events/", views.get_events, name="api_events"),
    path("individual/", views.individual, name="individual"),
    path("signup/", views.sign_up, name="sign_up"),
    path("signin/", views.sign_in, name="sign_in"),
    #all views
    path('profile/', views.profile_view, name='profile'),
    path('receipt/', views.receipt_view, name='receipt'),
    path('notifications/', views.notification_view, name='notifications'),
    path('rental-tracker/', views.rental_tracker_view, name='rental_tracker'),
    #receipt
    path('receipt/<int:receipt_id>/', receipt_detail, name='receipt-detail'),
    path('receipt/<int:receipt_id>/update/', update_receipt, name='receipt-update'),
    path('receipt/<int:receipt_id>/pdf/', generate_receipt_pdf, name='receipt-pdf'),
]
