from django.test import TestCase
#receipt

from .models import Receipt
from datetime import date


class ReceiptModelTest(TestCase):
    def setUp(self):
        self.receipt = Receipt.objects.create(
            customer_name="John Doe",
            customer_number="1234567890",
            amount=5000.00,
            event_date=date(2025, 5, 10),
            pickup_date=date(2025, 5, 8),
            return_date=date(2025, 5, 12),
            down_payment=1000.00,
            payment_method="Cash",
        )
    
    def test_receipt_creation(self):
        self.assertEqual(self.receipt.customer_name, "John Doe")
        self.assertEqual(float(self.receipt.amount), 5000.00)
        self.assertEqual(self.receipt.payment_method, "Cash")