from django.urls import path
from . import views

app_name = 'tokens'

urlpatterns = [
    path('set-rate/', views.set_rate, name='set_rate'),
]