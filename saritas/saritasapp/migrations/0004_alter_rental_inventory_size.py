# Generated by Django 5.2 on 2025-05-07 03:00

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('saritasapp', '0003_alter_reservation_options_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='rental',
            name='inventory_size',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='rentals', to='saritasapp.inventorysize'),
        ),
    ]
