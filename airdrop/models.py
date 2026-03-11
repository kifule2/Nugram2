from django.db import models
from django.utils import timezone
from datetime import timedelta
from users.models import CustomUser

class UserMiningState(models.Model):
    user = models.OneToOneField(CustomUser, on_delete=models.CASCADE)
    is_mining = models.BooleanField(default=False)
    last_tap = models.DateTimeField(null=True, blank=True)
    total_points = models.FloatField(default=0.0)
    current_rate = models.FloatField(default=1.0)
    session_start = models.DateTimeField(null=True, blank=True)
    
    @property
    def elapsed_hours(self):
        """Calculate elapsed hours since session start"""
        if not self.is_mining or not self.session_start:
            return 0
        elapsed = (timezone.now() - self.session_start).total_seconds() / 3600
        return min(elapsed, 24)  # Cap at 24 hours
    
    @property
    def remaining_hours(self):
        """Calculate remaining hours in current session"""
        return max(24 - self.elapsed_hours, 0)
    
    @property
    def remaining_time(self):
        """Return remaining time as hours, minutes, seconds"""
        if not self.is_mining or not self.session_start:
            return (0, 0, 0)
        remaining = (self.session_start + timedelta(hours=24)) - timezone.now()
        if remaining.total_seconds() <= 0:
            return (0, 0, 0)
        hours = int(remaining.total_seconds() // 3600)
        minutes = int((remaining.total_seconds() % 3600) // 60)
        seconds = int(remaining.total_seconds() % 60)
        return (hours, minutes, seconds)
    
    @property
    def progress_percentage(self):
        """Calculate progress percentage (0-100)"""
        return min((self.elapsed_hours / 24) * 100, 100)
    
    @property
    def points_earned_today(self):
        """Calculate points earned in current session"""
        return self.elapsed_hours * self.current_rate
    
    def start_mining(self):
        """Start a new mining session"""
        now = timezone.now()
        # Reset if previous session expired
        if self.is_mining and self.session_start:
            elapsed = (now - self.session_start).total_seconds() / 3600
            if elapsed >= 24:
                self.stop_mining()
        
        self.is_mining = True
        self.session_start = now
        self.last_tap = now
        self.save()
    
    def stop_mining(self):
        """Stop mining and credit earned points"""
        if self.is_mining:
            self.total_points += self.points_earned_today
            self.is_mining = False
            self.session_start = None
            self.last_tap = None
            self.save()
    
    def check_session_completion(self):
        """Check if current session should be completed"""
        if self.is_mining and self.session_start:
            elapsed = (timezone.now() - self.session_start).total_seconds() / 3600
            if elapsed >= 24:
                self.stop_mining()
                return True
        return False