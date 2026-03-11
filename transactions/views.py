from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from .models import Transaction
from .forms import AgentDepositForm, AgentWithdrawForm
from users.models import CustomUser, UserProfile,Notification
from tokens.models import TokenRate
from django.views.generic.detail import DetailView
import random
from decimal import Decimal
import logging
import hashlib
import secrets
from .models import WithdrawalRequest, Transaction, User
from django.db import transaction  # Import Django's transaction module
from django.http import JsonResponse


def public_ledger_autocomplete(request):
    query = request.GET.get('term', '')
    transactions = Transaction.objects.filter(
        Q(id__icontains=query) |
        Q(user__username__icontains=query) |
        Q(agent__username__icontains=query)
    ).values_list('id', flat=True)[:10]  # Limit to 10 results
    return JsonResponse(list(transactions), safe=False)

# User initiates withdrawal
@login_required
def request_withdrawal(request):
    if request.method == 'POST':
        amount = request.POST.get('amount')
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Invalid amount")

            # Generate PIN and hash
            pin = ''.join(secrets.choice('0123456789') for _ in range(6))
            pin_hash = hashlib.sha256(pin.encode()).hexdigest()
            expiry = timezone.now() + timedelta(minutes=10)

            # Create withdrawal request
            withdrawal = WithdrawalRequest.objects.create(
                user=request.user,
                amount=amount,
                pin_hash=pin_hash,
                expiry=expiry
            )

            # Show PIN to user (simulate SMS/email)
            return render(request, 'transactions/withdrawal_pin.html', {
                'pin': pin,
                'expiry': expiry,
            })

        except (ValueError, ValidationError) as e:
            messages.error(request, str(e))

    return render(request, 'transactions/request_withdrawal.html')

# transactions/views.py (updated snippet)
@user_passes_test(lambda u: u.is_agent or u.is_superuser)
def process_withdrawal(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        amount = request.POST.get('amount')
        pin = request.POST.get('pin')

        try:
            user = User.objects.get(username=username)
            amount = float(amount)
            pin_hash = hashlib.sha256(pin.encode()).hexdigest()

            # Find matching withdrawal request
            withdrawal = WithdrawalRequest.objects.filter(
                user=user,
                amount=amount,
                pin_hash=pin_hash,
                status='pending'
            ).first()

            if not withdrawal:
                messages.error(request, "Invalid PIN, amount, or username.")
                return redirect('transactions:process_withdrawal')

            # Use Django's transaction.atomic() correctly
            with transaction.atomic():  # Refers to the imported module
                if withdrawal.is_expired():
                    withdrawal.status = 'expired'
                    withdrawal.save()
                    messages.error(request, "PIN expired.")
                    return redirect('transactions:process_withdrawal')

                if user.userprofile.token_balance < withdrawal.amount:
                    messages.error(request, "Insufficient balance.")
                    return redirect('transactions:process_withdrawal')

                # Deduct balance and mark as completed
                user.userprofile.token_balance -= withdrawal.amount
                user.userprofile.save()

                withdrawal.status = 'completed'
                withdrawal.save()

                # Create transaction record (renamed variable)
                tx = Transaction.objects.create(  # Changed to 'tx'
                    user=user,
                    agent=request.user,
                    amount=withdrawal.amount
                )
                
                Notification.objects.create(
                    user=user,
                    message=f"Withdrawal of {withdrawal.amount} tokens processed",
                    transaction=tx
                )
                Notification.objects.create(
                    user=request.user,
                    message=f"Processed withdrawal for {user.username}",
                    transaction=tx
                )

                messages.success(request, "Withdrawal processed successfully!")
                return redirect('transactions:transaction_receipt', pk=tx.id)  # Use 'tx'

        except User.DoesNotExist:
            messages.error(request, "User not found.")
        except (ValueError, ValidationError) as e:
            messages.error(request, str(e))

    return render(request, 'transactions/process_withdrawal.html')


# transactions/views.py (updated snippet)
class TransactionReceiptView(DetailView):
    """
    Display the receipt for a completed transaction.
    """
    model = Transaction
    template_name = 'transactions/receipt.html'
    context_object_name = 'transaction'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['printable'] = self.request.GET.get('print', False)
        return context

    def get_template_names(self):
        if self.request.GET.get('print'):
            return ['transactions/receipt_print.html']
        return [self.template_name]


@user_passes_test(lambda u: u.is_agent or u.is_superuser)
def agent_deposit(request):
    """Allow agents to deposit tokens for users."""
    if request.method == 'POST':
        form = AgentDepositForm(request.POST)
        if form.is_valid():
            user_identifier = form.cleaned_data['user_identifier']
            cash_amount = form.cleaned_data['amount']
            
            # Find user by username or ID
            try:
                user = CustomUser.objects.get(username=user_identifier)
            except CustomUser.DoesNotExist:
                try:
                    user = CustomUser.objects.get(id=int(user_identifier))
                except (ValueError, CustomUser.DoesNotExist):
                    form.add_error('user_identifier', 'User not found.')
                    return render(request, 'transactions/agent_deposit.html', {'form': form})
            
            # Convert cash to tokens using the current rate
            current_rate = TokenRate.objects.last().rate if TokenRate.objects.exists() else 3800
            tokens = cash_amount / current_rate
            
            # Update user balance
            user.userprofile.token_balance += tokens
            user.userprofile.save()
            
            # Record transaction (remove 'status' argument)
            transaction = Transaction.objects.create(
                user=user,
                agent=request.user,
                amount=tokens,  # Store tokens, not cash
                transaction_type='deposit',  # Set transaction type
            )
            
            Notification.objects.create(
                user=user,
                message=f"Deposit of {tokens} tokens received",
                transaction=transaction
            )
            Notification.objects.create(
                user=request.user,
                message=f"Deposited {tokens} tokens to {user.username}",
                transaction=transaction
            )
            
            messages.success(request, f"Deposited {tokens} tokens for {user.username}")
            return redirect('transactions:transaction_receipt', pk=transaction.pk)
    else:
        form = AgentDepositForm()
    return render(request, 'transactions/agent_deposit.html', {'form': form})

# Public Ledger
def public_ledger(request):
    """Display all transactions in a public ledger."""
    query = request.GET.get('q')
    transactions = Transaction.objects.all().order_by('-timestamp')

    if query:
        transactions = transactions.filter(
            Q(id__icontains=query) |
            Q(user__username__icontains=query) |
            Q(agent__username__icontains=query)
        )
    

    paginator = Paginator(transactions, 20)  # Show 20 transactions per page
    page_number = request.GET.get('page')
    transactions = paginator.get_page(page_number)

    return render(request, 'transactions/public_ledger.html', {'transactions': transactions})

# transactions/views.py
@login_required
def transfer_tokens(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        amount = request.POST.get('amount')
        
        try:
            amount = float(amount)
            if amount <= 0:
                raise ValueError("Amount must be positive")
                
            recipient = CustomUser.objects.get(username=username)
            sender_profile = request.user.userprofile
            recipient_profile = recipient.userprofile
            
            if sender_profile.token_balance >= amount:
                sender_profile.token_balance -= amount
                recipient_profile.token_balance += amount
                
                # Create transaction record
                transaction = Transaction.objects.create(
                    user=request.user,
                    amount=amount,
                    transaction_type='transfer',
                    status='completed',
                    recipient=recipient
                )
                
                # Save profiles
                sender_profile.save()
                recipient_profile.save()

                # Create notifications
                Notification.objects.create(
                    user=request.user,
                    message=f"You sent {amount} tokens to {recipient.username}.",
                    transaction=transaction
                )
                Notification.objects.create(
                    user=recipient,
                    message=f"You received {amount} tokens from {request.user.username}.",
                    transaction=transaction
                )
                
                messages.success(request, f"Transferred {amount} tokens to {username}")
            else:
                messages.error(request, "Insufficient balance")
                
        except CustomUser.DoesNotExist:
            messages.error(request, "User not found")
        except ValueError:
            messages.error(request, "Invalid amount")
    
    return render(request, 'transactions/transfer_tokens.html')
    
    
def transaction_detail(request, pk):
    """Display details of a single transaction."""
    transaction = get_object_or_404(Transaction, pk=pk)
    return render(request, 'transactions/transaction_detail.html', {'transaction': transaction})