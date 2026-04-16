from django import forms
from django.core.exceptions import ValidationError
from .models import Post, PostMedia, BackgroundTemplate
import mimetypes
import os

class MultipleFileInput(forms.FileInput):
    def allow_multiple_selected(self):
        return True
    
    def value_from_datadict(self, data, files, name):
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return [files.get(name)] if files.get(name) else []

class MultipleFileField(forms.FileField):
    def to_python(self, data):
        if not data:
            return []
        if isinstance(data, list):
            return data
        return [data]

class PostForm(forms.Form):
    """Main form for creating posts with media (from feed app)"""
    content = forms.CharField(
        required=False,
        max_length=500,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'What\'s on your mind?'
        })
    )
    
    post_type = forms.ChoiceField(
        choices=Post.POST_TYPES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    media_files = MultipleFileField(
        required=False,
        label='Media Files',
        widget=MultipleFileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*,video/*',
            'multiple': True
        })
    )
    
    # Video trim fields
    trim_start = forms.FloatField(
        required=False,
        initial=0,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'min': '0'
        })
    )
    
    trim_end = forms.FloatField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.1',
            'min': '0'
        })
    )
    
    # Text post styling
    background_template = forms.ModelChoiceField(
        queryset=BackgroundTemplate.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    text_alignment = forms.ChoiceField(
        choices=[
            ('left', 'Left'),
            ('center', 'Center'),
            ('right', 'Right'),
        ],
        required=False,
        initial='center',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    text_color = forms.CharField(
        required=False,
        initial='#ffffff',
        widget=forms.TextInput(attrs={'class': 'form-control', 'type': 'color'})
    )
    
    text_font = forms.ChoiceField(
        choices=[
            ('default', 'Default'),
            ('bold', 'Bold'),
            ('handwriting', 'Handwriting'),
            ('typewriter', 'Typewriter'),
        ],
        required=False,
        initial='default',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    song_name = forms.CharField(
        required=False,
        initial='Original Audio',
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content', '')
        media_files = cleaned_data.get('media_files', [])
        post_type = cleaned_data.get('post_type', 'text')
        
        if not content and not media_files:
            raise ValidationError("Please provide either text content or media files.")
        
        if post_type == 'text' and not content:
            raise ValidationError("Text post requires content.")
        
        if post_type == 'media' and not media_files:
            raise ValidationError("Media post requires at least one media file.")
        
        return cleaned_data
    
    def clean_media_files(self):
        """Validate media files (from feed app)"""
        media_files = self.cleaned_data.get('media_files', [])
        
        if len(media_files) > 4:
            raise ValidationError("Maximum 4 media files per post.")
        
        for file in media_files:
            max_size = 90 * 1024 * 1024  # 90MB default
            
            # Get mime type
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
        
        return media_files
    
    def clean_trim_fields(self):
        """Validate trim fields (from feed app)"""
        trim_start = self.cleaned_data.get('trim_start', 0)
        trim_end = self.cleaned_data.get('trim_end')
        
        if trim_start < 0:
            raise ValidationError("Start time cannot be negative")
        
        if trim_end is not None and trim_end <= trim_start:
            raise ValidationError("End time must be greater than start time")
        
        return trim_start, trim_end


class BackgroundTemplateForm(forms.ModelForm):
    """Form for admin to create/edit background templates"""
    class Meta:
        model = BackgroundTemplate
        fields = [
            'name', 'template_type', 'preview_image', 'video_background',
            'gradient_css', 'css_class', 'is_animated', 'animation_duration',
            'animation_data', 'is_active', 'is_premium', 'order'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template_type': forms.Select(attrs={'class': 'form-control'}),
            'preview_image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'video_background': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'gradient_css': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'css_class': forms.TextInput(attrs={'class': 'form-control'}),
            'is_animated': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'animation_duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'animation_data': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_premium': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order': forms.NumberInput(attrs={'class': 'form-control'}),
        }