from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser,UserProfile

class CustomUserCreationForm(UserCreationForm):
    referral_code = forms.CharField(
        required=False,
        label='Referral Code (optional)',
        help_text="Enter the username of the person who referred you"
    )

    class Meta:
        model = CustomUser
        fields = ['username', 'email', 'password1', 'password2']

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = [
            'cover_photo',
            'profile_picture', 'display_name', 'gender',
            'birthday', 'work', 'location', 'phone_number',
            'bio',  'show_birthday', 'show_phone', 'show_email'
        ]
        widgets = {
            'birthday': forms.DateInput(attrs={'type': 'date'}),
            'show_birthday': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_phone': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'show_email': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
class CreateAgentForm(forms.Form):
    email = forms.EmailField()
    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

class SendTokensForm(forms.Form):
    username = forms.CharField()
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=1)