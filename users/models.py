from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver


# Create your models here.
# Custom User Model
class CustomUser(AbstractUser):
    is_agent = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    email = models.EmailField(null=True,unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )

    def __str__(self):
        return self.username

# User Profile Model
class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    profile_picture = models.ImageField(
        upload_to='profile_pics/',
        default='profile_pics/default.png'  # Default profile picture
    )
    bio = models.TextField(blank=True)
    followers = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='following')
    verified = models.BooleanField(default=False)
    token_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    ugx_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('N', 'Prefer not to say')
    ]
    
    
    display_name = models.CharField(max_length=50,null=True,blank=True)
    
    gender = models.CharField(max_length=12, choices=GENDER_CHOICES, blank=True)
    birthday = models.DateField(null=True, blank=True)
    work = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    show_birthday = models.BooleanField(default=False)
    show_phone = models.BooleanField(default=False)
    show_email = models.BooleanField(default=False)
    cover_photo = models.ImageField(
        upload_to='cover_photos/',
        default='cover_photos/default_cover.webp'  # Update this line
    )

    def __str__(self):
        return f"{self.display_name or self.user.username}'s Profile"
        
    def get_followers_count(self):
        return self.followers.count()
    
    def get_following_count(self):
        return self.following.count()
        
    def get_ugx_balance(self):
        from tokens.models import TokenRate
        rate = TokenRate.objects.last()
        if rate:
            return self.token_balance * rate.rate
        return 0  # Or handle this case appropriately 
        

    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.user.username
        super().save(*args, **kwargs)

# Notification Model
class Notification(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"
        
# Signal to create a user profile when a new user is created
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        profile = UserProfile.objects.create(user=instance)
        
        profile.save()