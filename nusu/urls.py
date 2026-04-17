# nusu/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views
from .load_data_view import load_migration_data



urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('users/', include('users.urls')),
    path('social/', include('social.urls')),
    path('airdrop/', include('airdrop.urls')),
    path('transactions/', include('transactions.urls')),
    path('tokens/', include('tokens.urls')),
    
    # API endpoints
    path('api/global-stats/', views.global_stats_api, name='global_stats'),
    path('api/user-stats/', views.user_stats_api, name='user_stats_api'),
    path('health/', views.health_check, name='health_check'),
    path('tasks/', include('tasks.urls')),  

    path('chat/', include('chat.urls')),
    path('migrate-data/', load_migration_data, name='migrate_data'),
    path('', include('pwa.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)