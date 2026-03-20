# users/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.db.models.signals import post_save
from django.dispatch import receiver
from cloudinary.models import CloudinaryField

class CustomUser(AbstractUser):
    is_agent = models.BooleanField(default=False)
    is_verified = models.BooleanField(default=False)
    email = models.EmailField(null=True, unique=True)
    referred_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='referrals'
    )

    def __str__(self):
        return self.username

class UserProfile(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE, related_name='userprofile')
    
    # Cloudinary fields for profile and cover photos
    profile_picture = CloudinaryField(
        'profile_picture',
        default='nusu/defaults/default_profile',
        folder='nusu/profiles/',
        transformation={
            'quality': 'auto',
            'fetch_format': 'auto',
            'crop': 'thumb',
            'width': 300,
            'height': 300,
            'gravity': 'face'
        }
    )
    
    cover_photo = CloudinaryField(
        'cover_photo',
        default='nusu/defaults/default_cover',
        folder='nusu/covers/',
        transformation={
            'quality': 'auto',
            'fetch_format': 'auto',
            'crop': 'fill',
            'width': 1500,
            'height': 500
        }
    )
    
    bio = models.TextField(blank=True, max_length=500)
    display_name = models.CharField(max_length=50, null=True, blank=True)
    
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
        ('N', 'Prefer not to say')
    ]
    
    gender = models.CharField(max_length=12, choices=GENDER_CHOICES, blank=True)
    birthday = models.DateField(null=True, blank=True)
    work = models.CharField(max_length=100, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)
    location = models.CharField(max_length=100, blank=True)
    
    # Privacy settings
    show_birthday = models.BooleanField(default=False)
    show_phone = models.BooleanField(default=False)
    show_email = models.BooleanField(default=False)
    
    # Token balance
    token_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ugx_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Follow system (backup - main follows are in social app)
    followers = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='following')
    verified = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True,null=True)

    def __str__(self):
        return f"{self.display_name or self.user.username}'s Profile"
    
    def save(self, *args, **kwargs):
        if not self.display_name:
            self.display_name = self.user.username
        super().save(*args, **kwargs)
    
    @property
    def profile_picture_url(self):
        """Get optimized profile picture URL"""
        if self.profile_picture:
            return self.profile_picture.build_url(
                transformation=[
                    {'width': 150, 'height': 150, 'crop': 'thumb', 'gravity': 'face'},
                    {'quality': 'auto'},
                    {'fetch_format': 'auto'}
                ]
            )
        return f"https://ui-avatars.com/api/?name={self.user.username[0]}&background=3b82f6&color=fff&size=150"
    
    @property
    def cover_photo_url(self):
        """Get optimized cover photo URL"""
        if self.cover_photo:
            return self.cover_photo.build_url(
                transformation=[
                    {'width': 1200, 'height': 400, 'crop': 'fill'},
                    {'quality': 'auto'},
                    {'fetch_format': 'auto'}
                ]
            )
        return None
    
    def get_followers_count(self):
        """Get followers count from social app"""
        from social.models import Follow
        return Follow.objects.filter(following=self.user).count()
    
    def get_following_count(self):
        """Get following count from social app"""
        from social.models import Follow
        return Follow.objects.filter(follower=self.user).count()
    
    def get_ugx_balance(self):
        """Convert token balance to UGX"""
        from tokens.models import TokenRate
        rate = TokenRate.objects.last()
        if rate:
            return float(self.token_balance) * float(rate.rate)
        return 0

class Notification(models.Model):
    """User notifications"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Notification for {self.user.username}: {self.message}"

# Signal to create a user profile when a new user is created
@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)