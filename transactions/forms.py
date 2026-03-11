from django import forms
from users.models import CustomUser
from .models import Transaction

class AgentWithdrawForm(forms.Form):
    user_identifier = forms.CharField(label="Username or ID", max_length=150)
    amount = forms.DecimalField(label="Amount (Tokens)", max_digits=12, decimal_places=2)


class AgentDepositForm(forms.Form):
    user_identifier = forms.CharField(
        label="Username or ID",
        max_length=150,
        help_text="Enter the username or ID of the user."
    )
    amount = forms.DecimalField(
        label="Cash Amount (UGX)",
        min_value=1000,  # Minimum deposit amount
        max_digits=12,
        decimal_places=2
    )

class AgentWithdrawForm(forms.Form):
    user_identifier = forms.CharField(
        label="Username or ID",
        max_length=150,
        help_text="Enter the username or ID of the user."
    )
    amount = forms.DecimalField(
        label="Token Amount",
        min_value=1,  # Minimum token withdrawal
        max_digits=12,
        decimal_places=2
    )