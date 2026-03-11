from django.db import models
from users.models import CustomUser

class TokenRate(models.Model):
    rate = models.DecimalField(max_digits=10, decimal_places=2)  # 1 Token = $X
    effective_date = models.DateTimeField(auto_now_add=True)
    set_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def __str__(self):
        return f"Rate: {self.rate} (Set by {self.set_by.username})"

class TokenAllocation(models.Model):
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=15, decimal_places=2)
    allocated_by = models.ForeignKey(CustomUser, related_name='allocations', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.amount} Tokens to {self.user.username}"