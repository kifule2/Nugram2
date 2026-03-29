"""
Clean up expired and old tasks
Run this daily via cron
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from tasks.models import Task, TaskCompletion
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Clean up expired tasks and old completions'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Days to keep completed tasks (default: 30)'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        cutoff = timezone.now() - timezone.timedelta(days=days)
        
        # Deactivate expired tasks
        expired_tasks = Task.objects.filter(
            expiry_date__lt=timezone.now(),
            is_active=True
        )
        count_expired = expired_tasks.count()
        expired_tasks.update(is_active=False)
        
        self.stdout.write(f"Deactivated {count_expired} expired tasks")
        
        # Delete old completed tasks (optional, or just mark as archived)
        old_completions = TaskCompletion.objects.filter(
            status='verified',
            verified_at__lt=cutoff
        )
        count_old = old_completions.count()
        
        # Option 1: Delete
        # old_completions.delete()
        
        # Option 2: Mark as archived
        # old_completions.update(status='archived')
        
        self.stdout.write(f"Found {count_old} old completions (> {days} days)")
        
        # Clean up old pending requests
        old_requests = TaskRequest.objects.filter(
            status='pending',
            created_at__lt=timezone.now() - timezone.timedelta(days=7)
        )
        count_requests = old_requests.count()
        old_requests.delete()
        
        self.stdout.write(f"Deleted {count_requests} stale pending requests")
        
        self.stdout.write(self.style.SUCCESS("Cleanup completed!"))