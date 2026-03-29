from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
import secrets
import string

User = get_user_model()


class SocialProfile(models.Model):
    """User's social media handles - one per platform"""
    PLATFORM_CHOICES = [
        ('twitter', 'Twitter/X'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='social_profiles')
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES)
    handle = models.CharField(max_length=100, help_text="Username or channel ID (without @)")
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'platform']
        indexes = [
            models.Index(fields=['user', 'platform']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.get_platform_display()}: @{self.handle}"


class Task(models.Model):
    """Tasks that users can complete"""
    PLATFORM_CHOICES = [
        ('twitter', 'Twitter/X'),
        ('youtube', 'YouTube'),
        ('tiktok', 'TikTok'),
        ('custom', 'Custom URL'),
        ('social', 'Social Media Link'),
        ('kyc', 'KYC Verification'),
        ('learning', 'Learn & Earn'),
        ('referral', 'Referral'),
    ]
    
    ACTION_CHOICES = [
        ('follow', 'Follow Account'),
        ('like', 'Like Post'),
        ('comment', 'Comment'),
        ('subscribe', 'Subscribe'),
        ('visit', 'Visit URL'),
        ('watch', 'Watch Video'),
        ('upload', 'Upload Document'),
        ('share', 'Share'),
    ]
    
    # Basic info
    name = models.CharField(max_length=200)
    description = models.TextField()
    task_code = models.CharField(max_length=20, unique=True, blank=True)
    task_type = models.CharField(max_length=10, choices=PLATFORM_CHOICES, default='social')
    
    # Platform & action
    platform = models.CharField(max_length=10, choices=PLATFORM_CHOICES, null=True, blank=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='visit')
    
    # Target
    target_url = models.URLField(blank=True, null=True)
    target_identifier = models.CharField(max_length=200, blank=True, help_text="e.g., @username to follow")
    
    # Task data (flexible JSON for complex tasks)
    task_data = models.JSONField(default=dict, blank=True)
    # Example for custom: {'keyword': 'thank you', 'success_message': 'Registration complete'}
    # Example for learning: {'video_url': '...', 'quiz': [...]}
    
    # Rewards
    points_reward = models.IntegerField(default=50)
    mining_boost = models.FloatField(default=1.05, help_text="Multiplier boost (1.05 = 5%)")
    boost_duration_hours = models.IntegerField(default=1)
    
    # Verification settings
    verification_method = models.CharField(max_length=10, choices=[
        ('auto', 'Auto Verification'),
        ('manual', 'Manual Review'),
        ('hybrid', 'Hybrid (Auto with Manual Fallback)'),
    ], default='auto')
    
    requires_approval = models.BooleanField(default=False, help_text="Require creator approval to join")
    
    # Limits
    max_participants = models.IntegerField(null=True, blank=True)
    daily_limit = models.IntegerField(default=5, help_text="Max times per user per day")
    total_limit = models.IntegerField(null=True, blank=True, help_text="Total completions allowed")
    
    # Status
    is_active = models.BooleanField(default=True)
    expiry_date = models.DateTimeField(null=True, blank=True)
    
    # Creator
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tasks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['task_code']),
            models.Index(fields=['platform', 'is_active']),
            models.Index(fields=['task_type', 'is_active']),
        ]
    
    def save(self, *args, **kwargs):
        if not self.task_code:
            # Generate unique code: e.g., "TASK-A3B9C2"
            random_chars = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            self.task_code = f"TASK-{random_chars}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.name} ({self.task_code})"
    
    @property
    def participants_count(self):
        return self.completions.filter(status='verified').count()
    
    @property
    def pending_count(self):
        return self.completions.filter(status='pending').count()
    
    @property
    def is_full(self):
        if self.max_participants:
            return self.participants_count >= self.max_participants
        return False
    
    @property
    def is_expired(self):
        if self.expiry_date:
            return timezone.now() > self.expiry_date
        return False


class TaskCompletion(models.Model):
    """Records when a user completes a task"""
    STATUS_CHOICES = [
        ('pending', 'Pending Verification'),
        ('processing', 'Processing'),
        ('verified', 'Verified'),
        ('failed', 'Failed'),
        ('expired', 'Expired'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_completions')
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='completions')
    
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    
    # User submission data
    submission_data = models.JSONField(default=dict, blank=True)
    
    # Verification tracking
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_completions')
    verification_data = models.JSONField(default=dict, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # Reward tracking
    reward_claimed = models.BooleanField(default=False)
    reward_claimed_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True,null=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'task']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'status']),
            models.Index(fields=['task', 'status']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.task.name} ({self.status})"
    
    def verify(self, verified_by=None):
        """Mark as verified and award rewards"""
        if self.status == 'pending':
            self.status = 'verified'
            self.verified_at = timezone.now()
            self.verified_by = verified_by
            self.save()
            self.award_rewards()
            return True
        return False
    
    def fail(self, reason=""):
        """Mark as failed"""
        if self.status in ['pending', 'processing']:
            self.status = 'failed'
            self.rejection_reason = reason
            self.save()
            return True
        return False
    
    def award_rewards(self):
        """Award points and mining boost"""
        if self.reward_claimed:
            return False
        
        user = self.user
        task = self.task
        
        # Award points
        if task.points_reward > 0:
            user.userprofile.token_balance += task.points_reward
            user.userprofile.save()
        
        # Award mining boost
        if task.mining_boost > 1.0:
            from .utils.rewards import apply_mining_boost
            apply_mining_boost(
                user=user,
                boost=task.mining_boost,
                duration_hours=task.boost_duration_hours
            )
        
        self.reward_claimed = True
        self.reward_claimed_at = timezone.now()
        self.save()
        
        # Create notification
        from users.models import Notification
        Notification.objects.create(
            user=user,
            message=f"✓ Task '{task.name}' completed! +{task.points_reward} NSU points earned!"
        )
        
        return True


class TaskRequest(models.Model):
    """Track join requests for tasks requiring approval"""
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='task_requests')
    
    message = models.TextField(blank=True)
    status = models.CharField(max_length=10, choices=[
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], default='pending')
    
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['task', 'user']
    
    def __str__(self):
        return f"{self.user.username} -> {self.task.name} ({self.status})"
    
    def approve(self, reviewer):
        self.status = 'approved'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.save()
        
        # Create completion record
        TaskCompletion.objects.create(
            task=self.task,
            user=self.user,
            status='pending'
        )
        
        from users.models import Notification
        Notification.objects.create(
            user=self.user,
            message=f"✅ Your request to join '{self.task.name}' has been approved!"
        )
    
    def reject(self, reviewer, reason=""):
        self.status = 'rejected'
        self.reviewed_by = reviewer
        self.reviewed_at = timezone.now()
        self.review_notes = reason
        self.save()
        
        from users.models import Notification
        Notification.objects.create(
            user=self.user,
            message=f"❌ Your request to join '{self.task.name}' was rejected. {reason}"
        )