# chat/urls.py
from django.urls import path
from . import views

app_name = 'chat'

urlpatterns = [
    path('', views.chat_list, name='chat_list'),
    path('api/list/', views.chat_list_api, name='chat_list_api'),
    path('<int:chat_id>/', views.chat_detail, name='chat_detail'),  # HTML page
    path('<int:chat_id>/api/', views.chat_messages_api, name='chat_messages_api'),  # JSON API
    path('create/', views.create_chat, name='create_chat'),
    path('<int:chat_id>/send/', views.send_message, name='send_message'),
    path('<int:chat_id>/add-participant/', views.add_participant, name='add_participant'),
    path('<int:chat_id>/convert-to-group/', views.convert_to_group, name='convert_to_group'),
    path('<int:chat_id>/leave/', views.leave_chat, name='leave_chat'),
    path('requests/', views.get_requests, name='get_requests'),
    path('requests/<int:request_id>/respond/', views.respond_to_request, name='respond_to_request'),
]