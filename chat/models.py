# chat/models.py
from django.db import models
from django.utils import timezone
from users.models import CustomUser
from cloudinary.models import CloudinaryField

class Chat(models.Model):
    CHAT_TYPES = [
        ('dm', 'Direct Message'),
        ('group', 'Group Chat'),
    ]
    
    chat_type = models.CharField(max_length=10, choices=CHAT_TYPES, default='dm')
    name = models.CharField(max_length=200, blank=True, null=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='created_chats')
    participants = models.ManyToManyField(CustomUser, related_name='chats')
    admins = models.ManyToManyField(CustomUser, related_name='admin_chats', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    # For tracking last message preview
    last_message = models.TextField(blank=True, null=True)
    last_message_time = models.DateTimeField(null=True, blank=True)
    last_message_sender = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, related_name='last_message_in_chat')
    
    class Meta:
        indexes = [
            models.Index(fields=['updated_at']),
            models.Index(fields=['chat_type']),
        ]
    
    def __str__(self):
        if self.name:
            return self.name
        if self.chat_type == 'dm':
            other_users = self.participants.exclude(id=self.created_by.id)
            if other_users.exists():
                return f"DM: {other_users.first().username}"
        return f"Chat {self.id}"
    
    def get_display_name(self, user):
        """Get chat name as seen by user"""
        if self.name:
            return self.name
        if self.chat_type == 'dm':
            other = self.participants.exclude(id=user.id).first()
            if other:
                return other.userprofile.display_name or other.username
        return "Group Chat"
    
    def get_avatar(self, user):
        """Get chat avatar URL"""
        if self.chat_type == 'dm':
            other = self.participants.exclude(id=user.id).first()
            if other and hasattr(other, 'userprofile') and other.userprofile.profile_picture:
                return other.userprofile.profile_picture.url
        return None
    
    @property
    def participant_count(self):
        return self.participants.count()
    
    def add_participant(self, user, added_by=None):
        """Add a participant to the chat"""
        if user not in self.participants.all():
            self.participants.add(user)
            
            # System message
            ChatMessage.objects.create(
                chat=self,
                sender=added_by or self.created_by,
                message_type='system',
                content=f"{user.userprofile.display_name or user.username} was added to the chat"
            )
            return True
        return False
    
    def remove_participant(self, user, removed_by=None):
        """Remove a participant from the chat"""
        if user in self.participants.all():
            # Don't allow removing the last admin
            if user in self.admins.all() and self.admins.count() == 1:
                return False
            
            self.participants.remove(user)
            if user in self.admins.all():
                self.admins.remove(user)
            
            # System message
            ChatMessage.objects.create(
                chat=self,
                sender=removed_by or self.created_by,
                message_type='system',
                content=f"{user.userprofile.display_name or user.username} was removed from the chat"
            )
            return True
        return False


# chat/models.py - Update ChatMessage model

class ChatMessage(models.Model):
    MESSAGE_TYPES = [
        ('text', 'Text'),
        ('voice', 'Voice Note'),
        ('image', 'Image'),
        ('video', 'Video'),  # NEW
        ('system', 'System Message'),
    ]
    
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_messages')
    message_type = models.CharField(max_length=10, choices=MESSAGE_TYPES, default='text')
    content = models.TextField(blank=True)
    
    # Voice notes
    voice_note = CloudinaryField(
        'voice_note',
        blank=True,
        null=True,
        resource_type='video',
        folder='chat/voice_notes/'
    )
    voice_duration = models.IntegerField(null=True, blank=True)
    
    # Images
    image = CloudinaryField(
        'image',
        blank=True,
        null=True,
        resource_type='image',
        folder='chat/images/'
    )
    
    # Videos (NEW)
    video = CloudinaryField(
        'video',
        blank=True,
        null=True,
        resource_type='video',
        folder='chat/videos/'
    )
    video_duration = models.FloatField(null=True, blank=True)
    video_thumbnail = models.CharField(max_length=500, blank=True, null=True)  # Store thumbnail URL
    
    read_by = models.ManyToManyField(CustomUser, related_name='read_messages', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_deleted = models.BooleanField(default=False)
    
    class Meta:
        indexes = [
            models.Index(fields=['chat', '-created_at']),
            models.Index(fields=['sender', '-created_at']),
        ]
    
    def __str__(self):
        if self.message_type == 'image':
            return f"{self.sender.username}: 📷 Image"
        elif self.message_type == 'video':
            return f"{self.sender.username}: 🎬 Video"
        elif self.message_type == 'voice':
            return f"{self.sender.username}: 🎙️ Voice note"
        return f"{self.sender.username}: {self.content[:50]}" if self.content else "Message"
    
    def mark_as_read(self, user):
        if user != self.sender and user not in self.read_by.all():
            self.read_by.add(user)
    
    def is_read_by_all(self):
        total_others = self.chat.participants.exclude(id=self.sender.id).count()
        return self.read_by.count() >= total_others if total_others > 0 else True
    
    def get_media_url(self):
        if self.image:
            return self.image.url
        elif self.video:
            return self.video.url
        elif self.voice_note:
            return self.voice_note.url
        return None
    

    
    def get_thumbnail_url(self):
        """Get video thumbnail URL"""
        if self.message_type == 'video' and self.video:
            try:
                return self.video.build_url(
                    transformation=[
                        {'start_offset': '0', 'flags': 'video_snapshot'},
                        {'width': 300, 'height': 300, 'crop': 'fill'}
                    ],
                    format='jpg'
                )
            except:
                return None
        return None


class ChatRequest(models.Model):
    REQUEST_TYPES = [
        ('add_to_group', 'Add to Group'),
        ('convert_to_group', 'Convert to Group'),
    ]
    
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='requests')
    requester = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_chat_requests')
    target_user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='received_chat_requests')
    request_type = models.CharField(max_length=20)
    status = models.CharField(max_length=10, default='pending')  # pending, accepted, rejected
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['target_user', 'status']),
            models.Index(fields=['chat', 'status']),
        ]
    
    def accept(self):
        """Accept the request"""
        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.save()
        
        if self.request_type == 'add_to_group':
            self.chat.add_participant(self.target_user, self.requester)
        elif self.request_type == 'convert_to_group':
            self.chat.chat_type = 'group'
            self.chat.name = self.message or f"Group with {self.chat.participants.count()} members"
            self.chat.save()
            
            # System message about conversion
            ChatMessage.objects.create(
                chat=self.chat,
                sender=self.requester,
                message_type='system',
                content=f"Chat converted to group by {self.requester.userprofile.display_name or self.requester.username}"
            )
        return True
    
    def reject(self):
        """Reject the request"""
        self.status = 'rejected'
        self.responded_at = timezone.now()
        self.save()
        return True