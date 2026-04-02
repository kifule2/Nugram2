# chat/forms.py
from django import forms
from .models import Chat, ChatMessage

class CreateChatForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    initial_message = forms.CharField(widget=forms.Textarea, required=False)


class SendMessageForm(forms.Form):
    content = forms.CharField(max_length=2000, required=False)
    message_type = forms.CharField(max_length=10, required=False)
    voice_note = forms.FileField(required=False)
    voice_duration = forms.IntegerField(required=False, min_value=0)
    
    def clean(self):
        cleaned_data = super().clean()
        content = cleaned_data.get('content')
        voice_note = cleaned_data.get('voice_note')
        message_type = cleaned_data.get('message_type', 'text')
        
        if message_type == 'text' and not content:
            raise forms.ValidationError("Message content is required")
        if message_type == 'voice' and not voice_note:
            raise forms.ValidationError("Voice note file is required")
        
        return cleaned_data


class AddParticipantForm(forms.Form):
    username = forms.CharField(max_length=150, required=True)
    message = forms.CharField(widget=forms.Textarea, required=False)


class ConvertToGroupForm(forms.Form):
    group_name = forms.CharField(max_length=200, required=True)
    message = forms.CharField(widget=forms.Textarea, required=False)