from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.utils import timezone
from .models import Task, TaskCompletion, TaskRequest
from users.models import Notification


@receiver(post_save, sender=TaskCompletion)
def task_completion_notification(sender, instance, created, **kwargs):
    """Send notification when task is completed"""
    if instance.status == 'verified' and not instance.reward_claimed:
        Notification.objects.create(
            user=instance.user,
            message=f"🎉 Task '{instance.task.name}' completed! +{instance.task.points_reward} points earned!",
            notification_type='task_completed'
        )
        
        # Also notify task creator
        if instance.task.created_by != instance.user:
            Notification.objects.create(
                user=instance.task.created_by,
                message=f"📊 {instance.user.username} completed your task '{instance.task.name}'",
                notification_type='task_completed_by_user'
            )


@receiver(post_save, sender=TaskRequest)
def task_request_notification(sender, instance, created, **kwargs):
    """Send notification when task request is created or resolved"""
    if created:
        Notification.objects.create(
            user=instance.task.created_by,
            message=f"📝 {instance.user.username} requested to join your task '{instance.task.name}'",
            notification_type='task_request'
        )
    elif instance.status == 'approved':
        Notification.objects.create(
            user=instance.user,
            message=f"✅ Your request to join '{instance.task.name}' was approved!",
            notification_type='task_approved'
        )
    elif instance.status == 'rejected':
        Notification.objects.create(
            user=instance.user,
            message=f"❌ Your request to join '{instance.task.name}' was rejected. {instance.review_notes}",
            notification_type='task_rejected'
        )


@receiver(post_save, sender=Task)
def new_task_notification(sender, instance, created, **kwargs):
    """Send notification when new task is created"""
    if created:
        # Notify followers of task creator?
        # For now, we can add to a feed
        pass