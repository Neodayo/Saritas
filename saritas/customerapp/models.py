from django.db import models
from django.conf import settings
from django.contrib.auth import get_user_model

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