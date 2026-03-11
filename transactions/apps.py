# transactions/apps.py
from django.apps import AppConfig

class TransactionsConfig(AppConfig):
    name = 'transactions'

    def ready(self):
        import transactions.signals  # Register the signal