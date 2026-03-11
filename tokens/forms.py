from django import forms
from .models import TokenRate

class TokenRateForm(forms.ModelForm):
    class Meta:
        model = TokenRate
        fields = ['rate']
        widgets = {
            'rate': forms.NumberInput(attrs={'step': '0.01'})
        }