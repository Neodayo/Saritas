from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model
from saritasapp.models import Category 

class HeroSection(models.Model):
    title = models.CharField(max_length=200, blank=True, default="") 
    subtitle = models.CharField(max_length=300, blank=True, default="")  
    background_image = models.ImageField(upload_to='hero_images/', blank=True)   
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True
    )
    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "Hero Section"
        verbose_name_plural = "Hero Sections"

class EventSlide(models.Model):
    title = models.CharField(max_length=200)
    subtitle = models.CharField(max_length=200)
    image = models.ImageField(upload_to='event_slides/')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.title
    

User = get_user_model()

class FeaturedCollectionsSection(models.Model):
    DEFAULT_CATEGORIES = ['Wedding Gown', 'Dress', 'Suit', 'Tuxedo']
    
    title = models.CharField(
        max_length=200,
        default="Featured Collections",
        help_text="Title for this featured collection section"
    )
    
    categories = models.ManyToManyField(
        'saritasapp.Category',
        blank=True
    )
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    class Meta:
        verbose_name = "Featured Collections Section"
        verbose_name_plural = "Featured Collections Sections"
    
    def __str__(self):
        return self.title
    
    def restore_defaults(s2elf):
        default_cats = Category.objects.filter(name__in=self.DEFAULT_CATEGORIES)
        self.categories.set(default_cats)
        self.save()

# models.py for email OTP
from django.db import models
from django.utils import timezone
import random

class EmailOTP(models.Model):
    email = models.EmailField()
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        return timezone.now() < self.created_at + timezone.timedelta(minutes=5)


        