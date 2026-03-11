from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import TokenRate
from .forms import TokenRateForm

@login_required
def set_rate(request):
    if not request.user.is_superuser:
        return redirect('users:dashboard')
    
    if request.method == 'POST':
        form = TokenRateForm(request.POST)
        if form.is_valid():
            TokenRate.objects.create(
                rate=form.cleaned_data['rate'],
                set_by=request.user
            )
            messages.success(request, "Exchange rate updated successfully")
            return redirect('users:dashboard')
    else:
        form = TokenRateForm()
    
    return render(request, 'tokens/set_rate.html', {'form': form})