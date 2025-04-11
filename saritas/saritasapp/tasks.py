from django.utils import timezone
from .models import Rental

def check_and_mark_overdue():
    today = timezone.now().date()
    overdue_rentals = Rental.objects.filter(status="Rented", rental_end__lt=today)
    for rental in overdue_rentals:
        rental.status = "Overdue"
        rental.save()
