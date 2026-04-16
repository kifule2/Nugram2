# chat/forms.py

from django import forms
from .models import Chat, ChatMessage

class CreateChatForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    initial_message = forms.CharField(widget=forms.Textarea, required=False)


class SendMessageForm(forms.Form):
    content = forms.CharField(max_length=2000, required=False)
    message_type = forms.CharField(max_length=20, required=False)  # text, voice, image, video
    voice_note = forms.FileField(required=False)
    voice_duration = forms.IntegerField(required=False, min_value=0)
    media_file = forms.FileField(required=False)  # NEW: For images and videos
    
    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        voice_note = cleaned_data.get('voice_note')
        media_file = cleaned_data.get('media_file')
        message_type = cleaned_data.get('message_type', 'text')
        
        if message_type == 'text' and not content:
            raise forms.ValidationError("Message content is required")
        if message_type == 'voice' and not voice_note:
            raise forms.ValidationError("Voice note file is required")
        if message_type in ['image', 'video'] and not media_file:
            raise forms.ValidationError("Media file is required")
        
        # Validate media file size (max 30MB)
        if media_file and media_file.size > 30 * 1024 * 1024:
            raise forms.ValidationError("Media file too large. Maximum 30MB")
        
        return cleaned_data


class AddParticipantForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    message = forms.CharField(widget=forms.Textarea, required=False)


class ConvertToGroupForm(forms.Form):
    group_name = forms.CharField(max_length=200, required=True)
    message = forms.CharField(widget=forms.Textarea, required=False)