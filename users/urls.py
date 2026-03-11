from django.urls import path
from . import views
from django.urls import path, reverse_lazy
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from django.contrib.auth.views import (
    PasswordResetDoneView,
    PasswordResetConfirmView,
    PasswordResetCompleteView
)



app_name = 'users'

urlpatterns = [
  path('admin-balances/', views.admin_balances, name='admin_balances'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),  # Add this line
    path('dashboard/', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('password-reset/', views.ConsolePasswordResetView.as_view(), 
         name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         PasswordResetConfirmView.as_view(
             success_url=reverse_lazy('users:password_reset_complete')
         ), name='password_reset_confirm'),
    path('password-reset-complete/', PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html'
    ), name='password_reset_complete'),
   path('create-agent/', views.create_agent, name='create_agent'),
    path('send-tokens/', views.send_tokens, name='send_tokens'),
    path('transaction/<int:tx_id>/receipt/', views.transaction_receipt, name='transaction_receipt'),
    path('notifications/', views.notifications, name='notifications'),
    path('notifications/<int:notification_id>/read/', 
         views.mark_notification_as_read, name='mark_notification_as_read'),
    path('notifications/<int:notification_id>/delete/', 
         views.delete_notification, name='delete_notification'),
    path('profile/<str:username>/', views.user_profile, name='user_profile'),
    
    path('follow/<str:username>/', views.follow_user, name='follow_user'),
    path('profile/<str:username>/<str:list_type>/', views.follow_list, name='follow_list'),
    path('unfollow/<str:username>/', views.unfollow_user, name='unfollow_user'),
  
]








    
    
