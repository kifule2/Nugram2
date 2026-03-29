"""
Background worker to process pending verifications with async batching
"""
import asyncio
from django.core.management.base import BaseCommand
from django.utils import timezone
from tasks.models import TaskCompletion
from tasks.utils.verification import VerificationService
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Process pending task verifications asynchronously'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--loop',
            action='store_true',
            help='Run continuously in a loop'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Seconds between checks when in loop mode'
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Maximum verifications to process per batch'
        )
    
    def handle(self, *args, **options):
        if options['loop']:
            self.stdout.write(self.style.SUCCESS("Starting async verification worker..."))
            asyncio.run(self.run_loop(options))
        else:
            asyncio.run(self.process_batch(options))
    
    async def run_loop(self, options):
        """Run continuously"""
        try:
            while True:
                try:
                    await self.process_batch(options)
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f"Error in batch: {e}"))
                    logger.error(f"Verification worker error: {e}")
                
                await asyncio.sleep(options['interval'])
        except KeyboardInterrupt:
            self.stdout.write(self.style.WARNING("\nWorker stopped."))
    
    async def process_batch(self, options):
        """Process a batch of pending verifications with async"""
        cutoff = timezone.now() - timezone.timedelta(seconds=15)
        
        pending = TaskCompletion.objects.filter(
            status='pending',
            created_at__lte=cutoff
        ).exclude(
            task__platform__in=['tiktok', 'social']
        ).exclude(
            task__task_type__in=['tiktok', 'social']
        )[:options['batch_size']]
        
        if not pending:
            return
        
        self.stdout.write(f"\n[{timezone.now().strftime('%H:%M:%S')}] Processing {len(pending)} verifications...")
        
        # Use batch verification for grouped tasks
        await VerificationService.verify_batch(pending)
        
        # Process remaining individually
        remaining = [c for c in pending if c.status == 'pending']
        
        if remaining:
            tasks = [VerificationService.verify(c) for c in remaining]
            results = await asyncio.gather(*tasks)
            
            success_count = sum(1 for r in results if r[0] is True)
            fail_count = sum(1 for r in results if r[0] is False)
            
            self.stdout.write(f"  ✓ Verified: {success_count} | ✗ Failed: {fail_count} | ⏳ Pending: {len(remaining) - success_count - fail_count}")