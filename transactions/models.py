from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.exceptions import ValidationError
import hashlib

User = get_user_model()

class WithdrawalRequest(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('expired', 'Expired'),
        ('failed', 'Failed'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    pin_hash = models.CharField(max_length=128)
    expiry = models.DateTimeField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        if self.amount <= 0:
            raise ValidationError("Amount must be positive.")
        if self.user.userprofile.token_balance < self.amount:
            raise ValidationError("Insufficient balance.")

    def is_expired(self):
        return timezone.now() > self.expiry

    def __str__(self):
        return f"Withdrawal Request #{self.id} - {self.user.username}"

class Transaction(models.Model):
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='user_transactions'  # Unique related name
    )
    agent = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='agent_transactions'  # Unique related name
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, default='withdrawal')
    timestamp = models.DateTimeField(auto_now_add=True)
    hashed_detail = models.CharField(max_length=64, blank=True, null=True)
    previous_hash = models.CharField(max_length=64, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.hashed_detail:
            detail = f"{self.user.username}{self.amount}{self.transaction_type}{self.timestamp}"
            self.hashed_detail = hashlib.sha256(detail.encode()).hexdigest()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Transaction #{self.id} - {self.user.username}"
        



    