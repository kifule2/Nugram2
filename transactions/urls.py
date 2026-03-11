# transactions/urls.py
from django.urls import path
from .views import (
    request_withdrawal, 
    process_withdrawal, 
    TransactionReceiptView,
    agent_deposit,
    public_ledger,
    transfer_tokens,
    transaction_detail,
    public_ledger_autocomplete,
)

app_name = 'transactions'

urlpatterns = [
    path('request-withdrawal/', request_withdrawal, name='request_withdrawal'),
    path('process-withdrawal/', process_withdrawal, name='process_withdrawal'),
    path('receipt/<int:pk>/', TransactionReceiptView.as_view(), name='transaction_receipt'),
    path('agent/deposit/', agent_deposit, name='agent_deposit'),
    path('ledger/', public_ledger, name='public_ledger'),
    path('transfer/', transfer_tokens, name='transfer_tokens'),
    path('ledger/transaction/<int:pk>/', transaction_detail, name='transaction_detail'),
    path('ledger/autocomplete/', public_ledger_autocomplete, name='public_ledger_autocomplete'),
]


#