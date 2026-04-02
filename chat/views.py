# chat/views.py - Complete fixed version

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Max, F  # Add F here
from django.core.paginator import Paginator
from django.utils import timezone
import cloudinary.uploader
import json
import logging

from .models import Chat, ChatMessage, ChatRequest
from .forms import CreateChatForm, SendMessageForm, AddParticipantForm, ConvertToGroupForm
from users.models import CustomUser
from users.models import Notification

logger = logging.getLogger(__name__)


@login_required
def chat_list(request):
    """Get chat list for current user - returns HTML template"""
    chats = Chat.objects.filter(
        participants=request.user,
        is_active=True
    ).annotate(
        last_msg_time=Max('messages__created_at')
    ).order_by('-last_msg_time', '-updated_at')
    
    chats_data = []
    for chat in chats:
        last_message = chat.messages.filter(is_deleted=False).last()
        
        chats_data.append({
            'id': chat.id,
            'name': chat.get_display_name(request.user),
            'avatar': chat.get_avatar(request.user),
            'chat_type': chat.chat_type,
            'participant_count': chat.participant_count,
            'last_message': {
                'content': last_message.content if last_message and last_message.message_type == 'text' else 
                           ('Voice note' if last_message and last_message.message_type == 'voice' else 
                            last_message.content if last_message else None),
                'sender': last_message.sender.username if last_message else None,
                'time': last_message.created_at.isoformat() if last_message else None,
                'message_type': last_message.message_type if last_message else None,
            } if last_message else None,
            'unread_count': chat.messages.filter(
                ~Q(read_by=request.user),
                ~Q(sender=request.user),
                is_deleted=False
            ).count()
        })
    
    return render(request, 'chat/chat_list.html', {'chats': chats_data})


@login_required
def chat_list_api(request):
    """API endpoint for chat list - returns JSON for badge updates"""
    chats = Chat.objects.filter(
        participants=request.user,
        is_active=True
    )
    
    total_unread = 0
    chats_data = []
    for chat in chats:
        unread = chat.messages.filter(
            ~Q(read_by=request.user),
            ~Q(sender=request.user),
            is_deleted=False
        ).count()
        total_unread += unread
        
        last_message = chat.messages.filter(is_deleted=False).last()
        
        chats_data.append({
            'id': chat.id,
            'name': chat.get_display_name(request.user),
            'unread_count': unread,
            'last_message': {
                'content': last_message.content if last_message and last_message.message_type == 'text' else 
                           ('Voice note' if last_message and last_message.message_type == 'voice' else None),
                'time': last_message.created_at.isoformat() if last_message else None,
            } if last_message else None,
        })
    
    return JsonResponse({
        'chats': chats_data,
        'total_unread': total_unread
    })


# chat/views.py - Update the chat_detail view

@login_required
def chat_detail(request, chat_id):
    """Render the chat detail HTML page"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    # Return HTML template instead of JSON
    return render(request, 'chat/chat_detail.html', {
        'chat_id': chat_id,
        'chat_name': chat.get_display_name(request.user),
        'chat_type': chat.chat_type,
    })




@login_required
def chat_messages_api(request, chat_id):
    """API endpoint to get messages for a chat (returns JSON)"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    # Get messages
    page = int(request.GET.get('page', 1))
    limit = int(request.GET.get('limit', 50))
    since = request.GET.get('since')
    
    messages_qs = chat.messages.filter(is_deleted=False).select_related('sender', 'sender__userprofile')
    
    if since:
        since_time = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
        messages_qs = messages_qs.filter(created_at__gt=since_time)
        messages = messages_qs.order_by('created_at')
    else:
        paginator = Paginator(messages_qs.order_by('-created_at'), limit)
        messages = paginator.get_page(page)
    
    messages_data = []
    for msg in messages:
        # Check read status
        is_read = msg.read_by.filter(id=request.user.id).exists()
        read_count = msg.read_by.count()
        total_participants = chat.participants.exclude(id=msg.sender.id).count()
        
        # Determine status: sent, delivered, read
        if msg.sender == request.user:
            if read_count >= total_participants and total_participants > 0:
                status = 'read'  # Double blue tick
            elif read_count > 0:
                status = 'delivered'  # Double grey tick
            else:
                status = 'sent'  # Single grey tick
        else:
            status = None
        
        messages_data.append({
            'id': msg.id,
            'sender': msg.sender.username,
            'sender_name': msg.sender.userprofile.display_name or msg.sender.username,
            'sender_avatar': msg.sender.userprofile.profile_picture.url if msg.sender.userprofile.profile_picture else None,
            'message_type': msg.message_type,
            'content': msg.content,
            'voice_url': msg.get_voice_url(),
            'voice_duration': msg.voice_duration,
            'created_at': msg.created_at.isoformat(),
            'is_sender': msg.sender == request.user,
            'status': status,  # 'sent', 'delivered', or 'read'
        })
    
    # Mark messages as read (for received messages)
    unread_messages = chat.messages.filter(
        ~Q(sender=request.user),
        ~Q(read_by=request.user),
        is_deleted=False
    )
    
    for msg in unread_messages:
        msg.read_by.add(request.user)
    
    # Get participants info
    participants_data = []
    for participant in chat.participants.select_related('userprofile'):
        participants_data.append({
            'id': participant.id,
            'username': participant.username,
            'display_name': participant.userprofile.display_name or participant.username,
            'avatar': participant.userprofile.profile_picture.url if participant.userprofile.profile_picture else None,
            'is_admin': participant in chat.admins.all(),
            'is_self': participant == request.user,
        })
    
    return JsonResponse({
        'chat': {
            'id': chat.id,
            'name': chat.get_display_name(request.user),
            'chat_type': chat.chat_type,
            'participant_count': chat.participant_count,
            'created_by': chat.created_by.username,
        },
        'messages': messages_data,
        'participants': participants_data,
        'has_more': not since and messages.has_next() if not since else False,
        'next_page': messages.next_page_number() if not since and messages.has_next() else None,
    })


@login_required
@require_POST
@csrf_exempt
def send_message(request, chat_id):
    """Send a text or voice message"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    form = SendMessageForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)
    
    data = form.cleaned_data
    message = None
    
    try:
        if data.get('message_type') == 'voice':
            # Upload voice note to Cloudinary
            voice_file = data.get('voice_note')
            if voice_file:
                upload_result = cloudinary.uploader.upload(
                    voice_file,
                    folder=f'chat/voice_notes/chat_{chat_id}',
                    resource_type='video',
                    format='opus',
                    transformation={'quality': 'auto'}
                )
                
                message = ChatMessage.objects.create(
                    chat=chat,
                    sender=request.user,
                    message_type='voice',
                    voice_note=upload_result['public_id'],
                    voice_duration=data.get('voice_duration', 0)
                )
        else:
            content = data.get('content', '').strip()
            if content:
                message = ChatMessage.objects.create(
                    chat=chat,
                    sender=request.user,
                    message_type='text',
                    content=content
                )
        
        if not message:
            return JsonResponse({'error': 'No message content'}, status=400)
        
        # Update chat's last message info
        chat.last_message = message.content if message.message_type == 'text' else 'Voice note'
        chat.last_message_time = message.created_at
        chat.last_message_sender = request.user
        chat.save()
        
        # Create notifications for other participants
        for participant in chat.participants.exclude(id=request.user.id):
            Notification.objects.create(
                user=participant,
                message=f"New message in {chat.get_display_name(participant)}",
                notification_type='chat_message'
            )
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': message.id,
                'sender': request.user.username,
                'sender_name': request.user.userprofile.display_name or request.user.username,
                'message_type': message.message_type,
                'content': message.content,
                'voice_url': message.get_voice_url(),
                'voice_duration': message.voice_duration,
                'created_at': message.created_at.isoformat(),
                'is_sender': True,
            }
        })
    
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def create_chat(request):
    """Create a new DM or group chat"""
    form = CreateChatForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)
    
    data = form.cleaned_data
    target_user = get_object_or_404(CustomUser, username=data['username'])
    
    # Don't allow creating chat with yourself
    if target_user == request.user:
        return JsonResponse({'error': 'Cannot create chat with yourself'}, status=400)
    
    # Check if DM already exists
    existing_chat = Chat.objects.filter(
        chat_type='dm',
        participants=request.user
    ).filter(participants=target_user).first()
    
    if existing_chat:
        return JsonResponse({
            'success': True,
            'chat_id': existing_chat.id,
            'existing': True
        })
    
    # Create new DM
    chat = Chat.objects.create(
        chat_type='dm',
        created_by=request.user
    )
    chat.participants.add(request.user, target_user)
    chat.admins.add(request.user)
    
    # Add initial message if provided
    if data.get('initial_message'):
        message = ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            message_type='text',
            content=data['initial_message']
        )
        
        # Update last message
        chat.last_message = data['initial_message']
        chat.last_message_time = timezone.now()
        chat.last_message_sender = request.user
        chat.save()
        
        # Notify
        Notification.objects.create(
            user=target_user,
            message=f"{request.user.username} started a chat with you",
            notification_type='chat_message'
        )
    
    return JsonResponse({
        'success': True,
        'chat_id': chat.id,
        'existing': False
    })


@login_required
@require_POST
def add_participant(request, chat_id):
    """Request to add a participant to a group"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    # Only admins can add participants
    if request.user not in chat.admins.all():
        return JsonResponse({'error': 'Only admins can add participants'}, status=403)
    
    form = AddParticipantForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)
    
    data = form.cleaned_data
    target_user = get_object_or_404(CustomUser, username=data['username'])
    
    # Check if already in chat
    if target_user in chat.participants.all():
        return JsonResponse({'error': 'User already in chat'}, status=400)
    
    # Create request
    chat_request = ChatRequest.objects.create(
        chat=chat,
        requester=request.user,
        target_user=target_user,
        request_type='add_to_group',
        message=data.get('message')
    )
    
    # Notify
    Notification.objects.create(
        user=target_user,
        message=f"{request.user.username} invited you to join '{chat.get_display_name(request.user)}'",
        notification_type='chat_invite'
    )
    
    return JsonResponse({
        'success': True,
        'request_id': chat_request.id
    })


@login_required
@require_POST
def convert_to_group(request, chat_id):
    """Convert a DM to a group chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    # Only DMs can be converted
    if chat.chat_type != 'dm':
        return JsonResponse({'error': 'Chat is already a group'}, status=400)
    
    form = ConvertToGroupForm(request.POST)
    if not form.is_valid():
        return JsonResponse({'error': form.errors}, status=400)
    
    data = form.cleaned_data
    
    # Convert immediately
    chat.chat_type = 'group'
    chat.name = data['group_name']
    chat.save()
    
    # Add both participants as admins
    chat.admins.add(request.user)
    for participant in chat.participants.exclude(id=request.user.id):
        chat.admins.add(participant)
    
    # System message
    ChatMessage.objects.create(
        chat=chat,
        sender=request.user,
        message_type='system',
        content=f"Chat converted to group '{data['group_name']}' by {request.user.userprofile.display_name or request.user.username}"
    )
    
    return JsonResponse({
        'success': True,
        'chat_id': chat.id,
        'converted': True
    })


@login_required
@require_GET
def get_requests(request):
    """Get pending requests for current user"""
    requests_list = ChatRequest.objects.filter(
        target_user=request.user,
        status='pending'
    ).select_related('chat', 'requester', 'requester__userprofile')
    
    requests_data = []
    for req in requests_list:
        requests_data.append({
            'id': req.id,
            'chat_id': req.chat.id,
            'chat_name': req.chat.get_display_name(request.user),
            'requester': req.requester.username,
            'requester_name': req.requester.userprofile.display_name or req.requester.username,
            'request_type': req.request_type,
            'message': req.message,
            'created_at': req.created_at.isoformat(),
        })
    
    return JsonResponse({'requests': requests_data})


@login_required
@require_POST
def respond_to_request(request, request_id):
    """Accept or reject a chat request"""
    chat_request = get_object_or_404(ChatRequest, id=request_id, target_user=request.user)
    
    action = request.POST.get('action')
    if action not in ['accept', 'reject']:
        return JsonResponse({'error': 'Invalid action'}, status=400)
    
    if action == 'accept':
        chat_request.accept()
        return JsonResponse({'success': True, 'message': 'Request accepted'})
    else:
        chat_request.reject()
        return JsonResponse({'success': True, 'message': 'Request rejected'})


@login_required
@require_POST
def leave_chat(request, chat_id):
    """Leave a chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    # Can't leave if you're the only admin and there are other participants
    if request.user in chat.admins.all() and chat.admins.count() == 1 and chat.participant_count > 1:
        return JsonResponse({'error': 'You are the only admin. Transfer admin role before leaving.'}, status=400)
    
    chat.participants.remove(request.user)
    if request.user in chat.admins.all():
        chat.admins.remove(request.user)
    
    # System message
    ChatMessage.objects.create(
        chat=chat,
        sender=request.user,
        message_type='system',
        content=f"{request.user.userprofile.display_name or request.user.username} left the chat"
    )
    
    # Delete chat if empty
    if chat.participant_count == 0:
        chat.is_active = False
        chat.save()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def make_admin(request, chat_id):
    """Make a participant an admin"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    if request.user not in chat.admins.all():
        return JsonResponse({'error': 'Only admins can make others admin'}, status=403)
    
    username = request.POST.get('username')
    target_user = get_object_or_404(CustomUser, username=username)
    
    if target_user not in chat.participants.all():
        return JsonResponse({'error': 'User not in chat'}, status=400)
    
    chat.admins.add(target_user)
    
    # System message
    ChatMessage.objects.create(
        chat=chat,
        sender=request.user,
        message_type='system',
        content=f"{target_user.userprofile.display_name or target_user.username} is now an admin"
    )
    
    return JsonResponse({'success': True})