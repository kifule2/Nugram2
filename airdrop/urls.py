from django.urls import path
from . import views

app_name = 'airdrop'

urlpatterns = [
    path('dashboard/', views.dashboard, name='dashboard'),
    path('toggle/', views.toggle_mining, name='toggle_mining'),
    path('status/', views.mining_status, name='mining_status'),
]