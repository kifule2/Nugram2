# social/models.py
from django.db import models
from users.models import CustomUser
from cloudinary.models import CloudinaryField

class BackgroundTemplate(models.Model):
    """Background templates for text posts - TikTok/IG style animated backgrounds"""
    TEMPLATE_TYPES = [
        ('gradient', 'Gradient Animation'),
        ('particle', 'Particle Motion'),
        ('abstract', 'Abstract Motion'),
        ('themed', 'Themed'),
        ('pattern', 'Pattern Animation'),
        ('solid', 'Solid with Animation'),
    ]
    
    name = models.CharField(max_length=100)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES)
    preview_image = CloudinaryField(
        'image', 
        blank=True, 
        null=True,
        folder='nusu/templates/previews/',
        transformation={'width': 300, 'height': 300, 'crop': 'fill', 'quality': 'auto'}
    )
    
    # For video backgrounds (animated templates)
    video_background = CloudinaryField(
        'video', 
        blank=True, 
        null=True,
        resource_type='video',
        folder='nusu/templates/backgrounds/',
        transformation={
            'quality': 'auto',
            'width': 1080,
            'height': 1920,
            'crop': 'fill',
            'video_codec': 'h264'
        }
    )
    
    # For CSS gradients
    gradient_css = models.TextField(blank=True, help_text="CSS gradient for static or animated gradients")
    css_class = models.CharField(max_length=100, blank=True, help_text="Custom CSS class for this template")
    
    # Animation properties
    is_animated = models.BooleanField(default=False)
    animation_duration = models.IntegerField(default=3, help_text="Animation duration in seconds")
    animation_data = models.JSONField(default=dict, blank=True, help_text="JSON data for complex animations")
    
    # Status
    is_active = models.BooleanField(default=True)
    is_premium = models.BooleanField(default=False, help_text="Premium templates for special users")
    created_at = models.DateTimeField(auto_now_add=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'name']
        indexes = [
            models.Index(fields=['is_active', 'order']),
            models.Index(fields=['template_type']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.get_template_type_display()})"
    
    @property
    def preview_url(self):
        if self.preview_image:
            return self.preview_image.url
        return None
    
    @property
    def background_url(self):
        if self.video_background:
            return self.video_background.url
        return None

class Post(models.Model):
    """Main post model for social feed with multiple media support"""
    POST_TYPES = [
        ('text', 'Text Only'),
        ('media', 'Media Only'),
        ('mixed', 'Text with Media'),
    ]
    
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='posts')
    content = models.TextField(max_length=500, blank=True)
    post_type = models.CharField(max_length=10, choices=POST_TYPES, default='text')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # For reposts/replies
    is_repost = models.BooleanField(default=False)
    original_post = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='reposts')
    is_reply = models.BooleanField(default=False)
    parent_post = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='replies')
    
    # View tracking
    views = models.ManyToManyField(CustomUser, related_name='viewed_posts', blank=True)
    
    # NEW: Text post background template
    background_template = models.ForeignKey(
        BackgroundTemplate, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='posts'
    )
    
    # NEW: Text customization options
    text_alignment = models.CharField(
        max_length=10, 
        choices=[
            ('left', 'Left'),
            ('center', 'Center'),
            ('right', 'Right'),
        ], 
        default='center'
    )
    text_size = models.FloatField(default=1.8, help_text="Font size in rem")
    text_color = models.CharField(max_length=20, default='#ffffff', help_text="Hex color code")
    text_font = models.CharField(
        max_length=50, 
        choices=[
            ('default', 'Default'),
            ('bold', 'Bold'),
            ('handwriting', 'Handwriting'),
            ('typewriter', 'Typewriter'),
        ],
        default='default'
    )
    
    # NEW: Video post info
    video_duration = models.FloatField(null=True, blank=True, help_text="Duration in seconds")
    song_name = models.CharField(max_length=200, blank=True, default='Original Audio')
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['post_type']),  # NEW
        ]
    
    def __str__(self):
        return f"{self.user.username}: {self.content[:50]}"
    
    @property
    def likes_count(self):
        return self.likes.count()
    
    @property
    def reposts_count(self):
        return self.reposts.count()
    
    @property
    def replies_count(self):
        return self.replies.count()
    
    @property
    def views_count(self):
        return self.views.count()
    
    @property
    def media_count(self):
        return self.media_items.count()
    
    @property
    def is_liked_by_user(self, user):
        if user.is_authenticated:
            return self.likes.filter(user=user).exists()
        return False
    
    @property
    def has_background(self):
        """Check if post has a background template (for text posts)"""
        return self.background_template is not None
    
    @property
    def is_video_post(self):
        """Check if this is a video post"""
        return self.media_items.filter(media_type='video').exists()
    
    def add_view(self, user):
        """Add a view only if user hasn't viewed before"""
        if user.is_authenticated and user != self.user:
            if not self.views.filter(id=user.id).exists():
                self.views.add(user)
                return True
        return False

    # Add these properties to your Post model

    @property
    def first_media(self):
        """Get the first media item"""
        return self.media_items.first()

    @property
    def all_media(self):
        """Get all media items"""
        return self.media_items.all()

    @property
    def media_count(self):
        """Get count of media items"""
        return self.media_items.count()

    @property
    def has_video(self):
        """Check if post has any video"""
        return self.media_items.filter(media_type='video').exists()

    @property
    def has_images(self):
        """Check if post has any images"""
        return self.media_items.filter(media_type='image').exists()

    def get_media_by_type(self, media_type):
        """Get media items by type"""
        return self.media_items.filter(media_type=media_type)

class PostMedia(models.Model):
    """Model for multiple media items per post using Cloudinary"""
    MEDIA_TYPES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('gif', 'GIF'),
    ]
    
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='media_items')
    media_type = models.CharField(max_length=10, choices=MEDIA_TYPES, default='image')
    
    # Cloudinary fields - store only the public_id
    image = CloudinaryField(
        'image', 
        blank=True, 
        null=True,
        resource_type='image'
    )
    
    video = CloudinaryField(
        'video', 
        blank=True, 
        null=True,
        resource_type='video'  # Important: Must be 'video' not 'auto'
    )
    
    # For external GIFs/embeds
    external_url = models.URLField(blank=True, null=True)
    
    # Media metadata
    width = models.IntegerField(null=True, blank=True)
    height = models.IntegerField(null=True, blank=True)
    duration = models.FloatField(null=True, blank=True)
    file_size = models.IntegerField(null=True, blank=True)
    format = models.CharField(max_length=10, blank=True)
    
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['order']
    
    def __str__(self):
        return f"Media {self.id} for Post {self.post_id} - {self.media_type}"
    
    @property
    def url(self):
        """Get the secure URL for the media"""
        if self.is_video:
            # For videos, return the video URL
            if self.video:
                try:
                    return self.video.url
                except:
                    # If URL generation fails, try manual construction
                    from django.conf import settings
                    cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
                    return f"https://res.cloudinary.com/{cloud_name}/video/upload/{self.video}"
        elif self.is_image:
            if self.image:
                try:
                    return self.image.url
                except:
                    from django.conf import settings
                    cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
                    return f"https://res.cloudinary.com/{cloud_name}/image/upload/{self.image}"
        elif self.external_url:
            return self.external_url
        return None
    
    @property
    def thumbnail_url(self):
        """Get thumbnail URL for videos or optimized thumbnail for images"""
        if self.is_video:
            # Generate video thumbnail at 1 second - returns JPG image
            if self.video:
                try:
                    return self.video.build_url(
                        transformation=[
                            {'width': 300, 'height': 300, 'crop': 'fill'},
                            {'quality': 'auto'},
                            {'start_offset': 1}
                        ],
                        format='jpg'
                    )
                except:
                    # Fallback to constructing URL manually
                    from django.conf import settings
                    cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
                    return f"https://res.cloudinary.com/{cloud_name}/video/upload/w_300,h_300,c_fill,q_auto/video_thumb_{self.id}.jpg"
        elif self.is_image:
            if self.image:
                try:
                    return self.image.build_url(
                        transformation=[
                            {'width': 300, 'height': 300, 'crop': 'fill'},
                            {'quality': 'auto'}
                        ]
                    )
                except:
                    from django.conf import settings
                    cloud_name = settings.CLOUDINARY_STORAGE['CLOUD_NAME']
                    return f"https://res.cloudinary.com/{cloud_name}/image/upload/w_300,h_300,c_fill,q_auto/{self.image}"
        return None
    
    @property
    def public_id(self):
        """Get the public_id of the media"""
        if self.image:
            return str(self.image)
        elif self.video:
            return str(self.video)
        return None
    
    @property
    def folder(self):
        """Extract folder from public_id"""
        public_id = self.public_id
        if public_id and '/' in public_id:
            return '/'.join(public_id.split('/')[:-1])
        return None
    
    @property
    def filename(self):
        """Extract filename from public_id"""
        public_id = self.public_id
        if public_id and '/' in public_id:
            return public_id.split('/')[-1]
        return public_id
    
    # FIXED: These were the main issues
    @property
    def is_video(self):
        """Check if media is a video - FIXED"""
        return self.media_type == 'video' or (self.video is not None)
    
    @property
    def is_image(self):
        """Check if media is an image - FIXED"""
        return self.media_type == 'image' and self.image is not None
    
    @property
    def is_external(self):
        """Check if media is from external URL"""
        return self.external_url is not None
    
    def build_url(self, resource_type='image', transformation=None, format=None):
        """Build a Cloudinary URL with custom transformations"""
        if resource_type == 'image' and self.image:
            return self.image.build_url(
                transformation=transformation or [],
                format=format
            )
        elif resource_type == 'video' and self.video:
            return self.video.build_url(
                transformation=transformation or [],
                format=format
            )
        return None
    
    def get_optimized_url(self, width=None, height=None):
        """Get optimized URL with specific dimensions"""
        transformation = [{'quality': 'auto', 'fetch_format': 'auto'}]
        
        if width and height:
            transformation.append({'width': width, 'height': height, 'crop': 'fill'})
        elif width:
            transformation.append({'width': width, 'crop': 'scale'})
        elif height:
            transformation.append({'height': height, 'crop': 'scale'})
        
        if self.is_video:
            return self.build_url(resource_type='video', transformation=transformation)
        else:
            return self.build_url(transformation=transformation)
    
    def get_video_poster(self, time_sec=1):
        """Get video thumbnail/poster at specific time"""
        if self.is_video:
            return self.build_url(
                resource_type='video',
                transformation=[
                    {'width': 640, 'height': 640, 'crop': 'fill'},
                    {'start_offset': time_sec},
                    {'quality': 'auto'}
                ],
                format='jpg'
            )
        return None
    
    def delete_from_cloudinary(self):
        """Delete the media from Cloudinary"""
        try:
            if self.image:
                result = cloudinary.uploader.destroy(self.image.public_id)
                return result.get('result') == 'ok'
            elif self.video:
                result = cloudinary.uploader.destroy(
                    self.video.public_id, 
                    resource_type='video'
                )
                return result.get('result') == 'ok'
        except Exception as e:
            logger.error(f"Failed to delete from Cloudinary: {e}")
            return False
        return False
    
    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            'id': self.id,
            'type': self.media_type,
            'url': self.url,
            'thumbnail_url': self.thumbnail_url,
            'width': self.width,
            'height': self.height,
            'duration': self.duration,
            'format': self.format,
            'order': self.order,
            'public_id': self.public_id,
            'folder': self.folder,
            'filename': self.filename,
            'is_video': self.is_video,
            'is_image': self.is_image,
            'optimized_urls': {
                'small': self.get_optimized_url(width=320),
                'medium': self.get_optimized_url(width=640),
                'large': self.get_optimized_url(width=1024),
            } if self.is_image else {
                'thumbnail': self.thumbnail_url,
                'poster': self.get_video_poster(),
            }
        }


class Like(models.Model):
    """Model for post likes"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='likes')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'post']
        indexes = [
            models.Index(fields=['user', 'post']),
            models.Index(fields=['-created_at']),
        ]
    
    def __str__(self):
        return f"{self.user.username} liked {self.post.id}"

class Follow(models.Model):
    """Model for user follows"""
    follower = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='following_set')
    following = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='followers_set')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['follower', 'following']
        indexes = [
            models.Index(fields=['follower', 'following']),
        ]
    
    def __str__(self):
        return f"{self.follower.username} follows {self.following.username}"

class Notification(models.Model):
    """Social notifications for interactions"""
    NOTIFICATION_TYPES = [
        ('like', '❤️ Liked your post'),
        ('repost', '🔄 Reposted your post'),
        ('reply', '💬 Replied to your post'),
        ('follow', '👤 Followed you'),
        ('mention', '@ Mentioned you'),
        ('post', '📝 New post from someone you follow'),
    ]
    
    recipient = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='social_notifications')
    sender = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='sent_notifications')
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
        ]
    
    def __str__(self):
        return f"{self.sender.username} {self.get_notification_type_display()}"

class FeedCache(models.Model):
    """Track which posts users have seen for the 'new posts' counter"""
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='feed_cache')
    last_seen_post = models.ForeignKey(Post, on_delete=models.CASCADE, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user']
    
    def __str__(self):
        return f"{self.user.username} last seen post: {self.last_seen_post_id or 'None'}"

# NEW: Initial templates data fixture - add this to create initial templates
def create_initial_templates():
    """Helper function to create initial background templates"""
    templates = [
        {
            'name': 'Sunset Gradient',
            'template_type': 'gradient',
            'gradient_css': 'linear-gradient(135deg, #667eea, #764ba2)',
            'css_class': 'gradient-sunset',
            'is_animated': False,
            'order': 1
        },
        {
            'name': 'Pink Dream',
            'template_type': 'gradient',
            'gradient_css': 'linear-gradient(135deg, #f093fb, #f5576c)',
            'css_class': 'gradient-pink',
            'is_animated': False,
            'order': 2
        },
        {
            'name': 'Ocean Waves',
            'template_type': 'gradient',
            'gradient_css': 'linear-gradient(135deg, #4facfe, #00f2fe)',
            'css_class': 'gradient-ocean',
            'is_animated': False,
            'order': 3
        },
        {
            'name': 'Northern Lights',
            'template_type': 'gradient',
            'gradient_css': 'linear-gradient(135deg, #ff6b6b, #4ecdc4, #45b7d1)',
            'css_class': 'animated-northern',
            'is_animated': True,
            'animation_duration': 3,
            'order': 4
        },
        {
            'name': 'Pastel Paradise',
            'template_type': 'gradient',
            'gradient_css': 'linear-gradient(135deg, #a8edea, #fed6e3, #ffd3b6)',
            'css_class': 'animated-pastel',
            'is_animated': True,
            'animation_duration': 3,
            'order': 5
        },
        {
            'name': 'Crypto King',
            'template_type': 'themed',
            'gradient_css': '#000000',
            'css_class': 'themed-crypto',
            'is_animated': False,
            'order': 6
        },
        {
            'name': 'Motivation Station',
            'template_type': 'themed',
            'gradient_css': 'linear-gradient(135deg, #ffd700, #ffa500)',
            'css_class': 'themed-motivation',
            'is_animated': False,
            'order': 7
        },
        {
            'name': 'Neon Nights',
            'template_type': 'gradient',
            'gradient_css': 'linear-gradient(135deg, #f12711, #f5af19, #00c6fb)',
            'css_class': 'animated-neon',
            'is_animated': True,
            'animation_duration': 4,
            'order': 8
        },
        {
            'name': 'Particle Field',
            'template_type': 'particle',
            'gradient_css': '#0f172a',
            'css_class': 'particle-field',
            'is_animated': True,
            'order': 9
        },
        {
            'name': 'Space Odyssey',
            'template_type': 'abstract',
            'gradient_css': '#000000',
            'css_class': 'space-theme',
            'is_animated': False,
            'order': 10
        }
    ]
    
    for template_data in templates:
        BackgroundTemplate.objects.get_or_create(
            name=template_data['name'],
            defaults=template_data
        )

@property
def url(self):
    """Get the secure URL for the media"""
    if self.image:
        try:
            return self.image.url
        except:
            # If URL generation fails, try to build manually
            return f"https://res.cloudinary.com/{settings.CLOUDINARY_STORAGE['CLOUD_NAME']}/image/upload/{self.image}"
    elif self.video:
        try:
            return self.video.url
        except:
            return f"https://res.cloudinary.com/{settings.CLOUDINARY_STORAGE['CLOUD_NAME']}/video/upload/{self.video}"
    elif self.external_url:
        return self.external_url
    return None