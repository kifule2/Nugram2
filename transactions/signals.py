# transactions/signals.py
from django.db.models.signals import Signal
from django.dispatch import receiver
from django.utils import timezone
from django.apps import apps

# Create a custom signal
pin_verified = Signal()

@receiver(pin_verified)
def handle_pin_verification(sender, transaction_id, pin, **kwargs):
    """
    Handle PIN verification and update the transaction status.
    """
    # Lazily load the Transaction model to avoid circular imports
    Transaction = apps.get_model('transactions', 'Transaction')

    try:
        # Retrieve the transaction
        tx = Transaction.objects.get(id=transaction_id, status='pending')

        # Verify the PIN
        if pin == tx.verification_code:
            # Check if the PIN has expired
            if tx.expiry and tx.expiry < timezone.now():
                tx.status = 'expired'
                tx.save()
                return False, "PIN has expired."

            # Check if the user has sufficient balance
            if tx.user.userprofile.token_balance < tx.amount:
                return False, "Insufficient balance."

            # Deduct tokens from the user's balance
            tx.user.userprofile.token_balance -= tx.amount
            tx.user.userprofile.save()

            # Mark the transaction as completed
            tx.status = 'completed'
            tx.save()

            return True, "Withdrawal processed successfully."
        else:
            return False, "Invalid PIN."
    except Transaction.DoesNotExist:
        return False, "Transaction not found."