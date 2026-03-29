# social/forms.py
from django import forms
from django.core.exceptions import ValidationError
from .models import Post, PostMedia, BackgroundTemplate
import mimetypes
import os
import json

class MultipleFileInput(forms.FileInput):
    """Custom widget that supports multiple file uploads"""
    def __init__(self, attrs=None):
        super().__init__(attrs)
        if 'multiple' not in self.attrs:
            self.attrs['multiple'] = 'multiple'
    
    def value_from_datadict(self, data, files, name):
        """Return all files for this field name"""
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return [files.get(name)] if files.get(name) else []

class MultipleFileField(forms.FileField):
    """Custom field that handles multiple file uploads"""
    def __init__(self, attrs=None, **kwargs):
        self.widget = MultipleFileInput(attrs=attrs)
        super().__init__(**kwargs)
    
    def clean(self, data, initial=None):
        """Handle multiple files - clean each one"""
        if not data:
            return []
        if isinstance(data, list):
            return [super(MultipleFileField, self).clean(file, initial) for file in data]
        return [super(MultipleFileField, self).clean(data, initial)]

class PostForm(forms.Form):
    """Form for creating posts (both text and media)"""
    
    # Text content
    content = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': "What's on your mind?",
            'id': 'postContent',
            'maxlength': '500'
        })
    )
    
    # Media files (images/videos) - Using custom MultipleFileField
    media_files = MultipleFileField(
        required=False,
        label='Media Files',
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,video/*',
            'id': 'mediaFiles'
        })
    )
    
    # For text post templates (optional now)
    template_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'templateId'})
    )
    
    # Text customization
    text_alignment = forms.ChoiceField(
        required=False,
        choices=[
            ('left', 'Left'),
            ('center', 'Center'),
            ('right', 'Right'),
        ],
        initial='center',
        widget=forms.HiddenInput(attrs={'id': 'textAlignment'})
    )
    
    text_size = forms.FloatField(
        required=False,
        min_value=0.5,
        max_value=5.0,
        initial=1.8,
        widget=forms.HiddenInput(attrs={'id': 'textSize'})
    )
    
    text_color = forms.CharField(
        required=False,
        max_length=20,
        initial='#ffffff',
        widget=forms.HiddenInput(attrs={'id': 'textColor'})
    )
    
    text_font = forms.ChoiceField(
        required=False,
        choices=[
            ('default', 'Default'),
            ('bold', 'Bold'),
            ('handwriting', 'Handwriting'),
            ('typewriter', 'Typewriter'),
        ],
        initial='default',
        widget=forms.HiddenInput(attrs={'id': 'textFont'})
    )
    
    # For video posts
    song_name = forms.CharField(
        required=False,
        max_length=200,
        initial='Original Audio',
        widget=forms.HiddenInput(attrs={'id': 'songName'})
    )
    
    def clean_content(self):
        """Validate content based on post type"""
        content = self.cleaned_data.get('content', '')
        media_files = self.cleaned_data.get('media_files', [])
        
        # Check if either content or media is provided
        if not content and not media_files:
            raise ValidationError("Please provide either text content or media files.")
        
        return content
    
    def clean_media_files(self):
        """Validate uploaded media files"""
        media_files = self.cleaned_data.get('media_files', [])
        
        # Check maximum number of files
        if len(media_files) > 4:
            raise ValidationError("Maximum 4 files allowed per post.")
        
        # Validate each file
        for file in media_files:
            self._validate_single_file(file)
        
        return media_files
    
    def _validate_single_file(self, file):
        """Validate individual file properties"""
        
        # Check file size (90MB max for videos, 20MB for images)
        max_size = 90 * 1024 * 1024  # 90MB default for videos
        
        # Detect if it's an image or video
        mime_type, _ = mimetypes.guess_type(file.name)
        if mime_type:
            if mime_type.startswith('image/'):
                max_size = 20 * 1024 * 1024  # 20MB for images
            elif mime_type.startswith('video/'):
                max_size = 90 * 1024 * 1024  # 90MB for videos
        
        if file.size > max_size:
            file_size_mb = file.size / (1024 * 1024)
            max_size_mb = max_size / (1024 * 1024)
            raise ValidationError(
                f"File '{file.name}' is {file_size_mb:.1f}MB. "
                f"Maximum size is {max_size_mb:.0f}MB."
            )
        
        # Check file extension
        ext = os.path.splitext(file.name)[1].lower()
        allowed_extensions = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'],
            'video': ['.mp4', '.webm', '.mov', '.avi', '.mkv', '.m4v', '.3gp']
        }
        
        all_allowed = allowed_extensions['image'] + allowed_extensions['video']
        
        if ext not in all_allowed:
            raise ValidationError(
                f"File '{file.name}' has unsupported extension. "
                f"Allowed: {', '.join(all_allowed)}"
            )
    
    def clean_template_id(self):
        """Validate template ID if provided"""
        template_id = self.cleaned_data.get('template_id')
        if template_id:
            try:
                template = BackgroundTemplate.objects.get(id=template_id, is_active=True)
            except BackgroundTemplate.DoesNotExist:
                raise ValidationError("Selected background template is not available.")
        return template_id
    
    def clean_text_color(self):
        """Validate hex color code"""
        color = self.cleaned_data.get('text_color', '#ffffff')
        if color and not color.startswith('#') or (len(color) not in [4, 7] and color != '#ffffff'):
            raise ValidationError("Invalid color format. Use hex color (e.g., #ffffff).")
        return color
    
    def clean(self):
        """Cross-field validation"""
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        template_id = cleaned_data.get('template_id')
        media_files = cleaned_data.get('media_files', [])
        
        # If it's a text post with template, content is recommended but not required
        # We'll let it pass - empty content with template is fine (just background)
        
        return cleaned_data


class CommentForm(forms.Form):
    """Form for adding comments/replies"""
    
    content = forms.CharField(
        required=True,
        max_length=200,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Write a comment...',
            'id': 'commentContent',
            'maxlength': '200'
        })
    )
    
    # Media files for comments (images only - no videos in comments)
    media_files = MultipleFileField(
        required=False,
        label='Images',
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*',
            'id': 'commentMedia'
        })
    )
    
    def clean_media_files(self):
        """Validate uploaded images for comments"""
        media_files = self.cleaned_data.get('media_files', [])
        
        # Comments can have at most 2 images
        if len(media_files) > 2:
            raise ValidationError("Maximum 2 images allowed per comment.")
        
        # Validate each file is an image
        for file in media_files:
            mime_type, _ = mimetypes.guess_type(file.name)
            if not mime_type or not mime_type.startswith('image/'):
                raise ValidationError(f"File '{file.name}' must be an image.")
            
            # Check file size (10MB max for comment images)
            if file.size > 10 * 1024 * 1024:
                file_size_mb = file.size / (1024 * 1024)
                raise ValidationError(
                    f"Image '{file.name}' is {file_size_mb:.1f}MB. "
                    f"Maximum size is 10MB."
                )
        
        return media_files


class BackgroundTemplateForm(forms.ModelForm):
    """Form for managing background templates (admin only)"""
    
    class Meta:
        model = BackgroundTemplate
        fields = [
            'name', 'template_type', 'preview_image', 'video_background',
            'gradient_css', 'css_class', 'is_animated', 'animation_duration',
            'animation_data', 'is_active', 'is_premium', 'order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., Sunset Gradient'
            }),
            'template_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'preview_image': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'image/*'
            }),
            'video_background': forms.ClearableFileInput(attrs={
                'class': 'form-control',
                'accept': 'video/*'
            }),
            'gradient_css': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'linear-gradient(135deg, #667eea, #764ba2)',
            }),
            'css_class': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'custom-gradient-class'
            }),
            'is_animated': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'animation_duration': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 10,
                'step': 0.5,
                'placeholder': '3'
            }),
            'animation_data': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': '{"type": "particle", "count": 50}'
            }),
            'order': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_premium': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'name': 'Template Name',
            'template_type': 'Template Type',
            'preview_image': 'Preview Image',
            'video_background': 'Video Background (optional)',
            'gradient_css': 'Gradient CSS',
            'css_class': 'CSS Class',
            'is_animated': 'Animated',
            'animation_duration': 'Animation Duration (seconds)',
            'animation_data': 'Animation Data (JSON)',
            'order': 'Display Order',
            'is_active': 'Active',
            'is_premium': 'Premium Only',
        }
        help_texts = {
            'gradient_css': 'Enter CSS gradient. For animated gradients, set background-size: 300% 300%',
            'css_class': 'Optional custom CSS class for this template',
            'animation_data': 'JSON data for complex animations (particle effects, etc.)',
            'order': 'Lower numbers appear first',
        }
    
    def clean_gradient_css(self):
        """Basic validation for gradient CSS"""
        gradient = self.cleaned_data.get('gradient_css', '')
        
        # If it's a gradient template, require gradient CSS
        template_type = self.cleaned_data.get('template_type')
        if template_type in ['gradient', 'themed'] and not gradient and not self.cleaned_data.get('video_background'):
            # Not required, but warn
            pass
        
        return gradient
    
    def clean_animation_duration(self):
        """Validate animation duration"""
        duration = self.cleaned_data.get('animation_duration', 3)
        is_animated = self.cleaned_data.get('is_animated', False)
        
        if is_animated and (duration < 1 or duration > 10):
            raise ValidationError("Animation duration must be between 1 and 10 seconds.")
        
        return duration
    
    def clean_animation_data(self):
        """Validate JSON animation data"""
        data = self.cleaned_data.get('animation_data', '')
        if data:
            try:
                json.loads(data)
            except json.JSONDecodeError:
                raise ValidationError("Invalid JSON format.")
        return data
    
    def clean(self):
        """Cross-field validation for templates"""
        cleaned_data = super().clean()
        template_type = cleaned_data.get('template_type')
        gradient = cleaned_data.get('gradient_css')
        video = cleaned_data.get('video_background')
        css_class = cleaned_data.get('css_class')
        
        # Template must have either gradient, video, or CSS class
        if not any([gradient, video, css_class]):
            # Not required, but warn
            pass
        
        return cleaned_data


class PostMediaForm(forms.ModelForm):
    """Form for managing post media (admin/advanced use)"""
    
    class Meta:
        model = PostMedia
        fields = ['media_type', 'image', 'video', 'external_url', 'order']
        widgets = {
            'media_type': forms.Select(attrs={'class': 'form-control'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'video': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'external_url': forms.URLInput(attrs={'class': 'form-control'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def clean(self):
        """Ensure either image, video, or external_url is provided"""
        cleaned_data = super().clean()
        media_type = cleaned_data.get('media_type')
        image = cleaned_data.get('image')
        video = cleaned_data.get('video')
        external_url = cleaned_data.get('external_url')
        
        if media_type == 'image' and not image and not external_url:
            raise ValidationError("Image or external URL required for image media type.")
        
        if media_type == 'video' and not video and not external_url:
            raise ValidationError("Video or external URL required for video media type.")
        
        return cleaned_data


class PostFilterForm(forms.Form):
    """Form for filtering/searching posts"""
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Search posts...',
            'id': 'searchInput'
        })
    )
    
    post_type = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + Post.POST_TYPES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    sort_by = forms.ChoiceField(
        required=False,
        choices=[
            ('-created_at', 'Latest'),
            ('-likes_count', 'Most Liked'),
            ('-views_count', 'Most Viewed'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )