# chat/views.py - Complete working version

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.core.paginator import Paginator
from django.utils import timezone
import cloudinary.uploader
import json
import logging
import time

from .models import Chat, ChatMessage, ChatRequest
from .forms import CreateChatForm, SendMessageForm, AddParticipantForm, ConvertToGroupForm
from users.models import CustomUser
from social.models import Notification

logger = logging.getLogger(__name__)


@login_required
def chat_list(request):
    """List all chats for the current user"""
    chats = Chat.objects.filter(
        participants=request.user,
        is_active=True
    ).order_by('-updated_at')
    
    chats_data = []
    for chat in chats:
        # Get unread count
        unread = chat.messages.filter(
            ~Q(read_by=request.user),
            ~Q(sender=request.user),
            is_deleted=False
        ).count()
        
        # Get last message
        last_message = chat.messages.filter(is_deleted=False).last()
        
        # Format last message preview
        last_message_preview = None
        if last_message:
            if last_message.message_type == 'text':
                last_message_preview = last_message.content[:40]
            elif last_message.message_type == 'image':
                last_message_preview = "📷 Image"
            elif last_message.message_type == 'video':
                last_message_preview = "🎬 Video"
            elif last_message.message_type == 'voice':
                last_message_preview = "🎙️ Voice note"
        
        chats_data.append({
            'id': chat.id,
            'name': chat.get_display_name(request.user),
            'avatar': None,
            'chat_type': chat.chat_type,
            'unread_count': unread,
            'last_message': {
                'sender': last_message.sender.username if last_message else None,
                'content': last_message_preview,
                'time': last_message.created_at.isoformat() if last_message else None,
            } if last_message else None,
        })
    
    return render(request, 'chat/chat_list.html', {'chats': chats_data})


@login_required
def chat_list_api(request):
    """API endpoint for chat list"""
    chats = Chat.objects.filter(
        participants=request.user,
        is_active=True
    ).order_by('-updated_at')
    
    chats_data = []
    for chat in chats:
        unread = chat.messages.filter(
            ~Q(read_by=request.user),
            ~Q(sender=request.user),
            is_deleted=False
        ).count()
        
        chats_data.append({
            'id': chat.id,
            'name': chat.get_display_name(request.user),
            'chat_type': chat.chat_type,
            'unread_count': unread,
            'updated_at': chat.updated_at.isoformat(),
        })
    
    return JsonResponse({'chats': chats_data})


@login_required
def chat_detail(request, chat_id):
    """View a specific chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    # Mark messages as read - FIXED: Cannot use .update() on ManyToMany field
    unread_messages = chat.messages.filter(
        ~Q(sender=request.user),
        ~Q(read_by=request.user),
        is_deleted=False
    )
    
    # Add each message to read_by individually
    for message in unread_messages:
        message.read_by.add(request.user)
    
    context = {
        'chat_id': chat.id,
        'chat_name': chat.get_display_name(request.user),
        'chat_type': chat.chat_type,
    }
    return render(request, 'chat/chat_detail.html', context)


@login_required
def chat_messages_api(request, chat_id):
    """API endpoint to get messages for a chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    since = request.GET.get('since')
    messages_qs = chat.messages.filter(is_deleted=False).select_related('sender', 'sender__userprofile')
    
    if since:
        try:
            since_time = timezone.datetime.fromisoformat(since.replace('Z', '+00:00'))
            messages_qs = messages_qs.filter(created_at__gt=since_time)
        except:
            pass
    
    messages = messages_qs.order_by('created_at')
    
    messages_data = []
    for msg in messages:
        # Check if message is read by current user
        is_read = msg.read_by.filter(id=request.user.id).exists()
        
        # Determine status for sender
        if msg.sender == request.user:
            total_participants = chat.participants.exclude(id=msg.sender.id).count()
            read_count = msg.read_by.count()
            if total_participants > 0 and read_count >= total_participants:
                status = 'read'
            elif read_count > 0:
                status = 'delivered'
            else:
                status = 'sent'
        else:
            status = None
        
        # Build message data
        msg_data = {
            'id': msg.id,
            'sender': msg.sender.username,
            'sender_name': msg.sender.userprofile.display_name or msg.sender.username,
            'sender_avatar': msg.sender.userprofile.profile_picture.url if msg.sender.userprofile.profile_picture else None,
            'message_type': msg.message_type,
            'content': msg.content,
            'created_at': msg.created_at.isoformat(),
            'is_sender': msg.sender == request.user,
            'is_read': is_read,
            'status': status,
        }
        
        # Add media URLs based on type
        if msg.message_type == 'image' and msg.image:
            msg_data['image_url'] = msg.image.url
        elif msg.message_type == 'video' and msg.video:
            msg_data['video_url'] = msg.video.url
            msg_data['video_thumbnail'] = msg.get_thumbnail_url() if hasattr(msg, 'get_thumbnail_url') else None
            msg_data['video_duration'] = msg.video_duration
        elif msg.message_type == 'voice' and msg.voice_note:
            msg_data['voice_url'] = msg.voice_note.url
            msg_data['voice_duration'] = msg.voice_duration
        
        messages_data.append(msg_data)
    
    # Get participants for group info
    participants_data = []
    if chat.chat_type == 'group':
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
        'messages': messages_data,
        'participants': participants_data if chat.chat_type == 'group' else [],
        'chat': {
            'id': chat.id,
            'name': chat.get_display_name(request.user),
            'chat_type': chat.chat_type,
        }
    })


@login_required
@require_POST
@csrf_exempt
def send_message(request, chat_id):
    """Send a message (text, voice, image, or video)"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    message_type = request.POST.get('message_type', 'text')
    content = request.POST.get('content', '').strip()
    voice_note = request.FILES.get('voice_note')
    
    # IMPORTANT: Check for BOTH 'media_file' and 'file_data' (like feed app)
    media_file = request.FILES.get('media_file') or request.FILES.get('file_data')
    
    voice_duration = request.POST.get('voice_duration')
    
    message = None
    last_message_preview = None
    
    try:
        # Handle text message
        if message_type == 'text' and content:
            message = ChatMessage.objects.create(
                chat=chat,
                sender=request.user,
                message_type='text',
                content=content
            )
            last_message_preview = content[:50]
            
        # Handle voice note
        elif message_type == 'voice' and voice_note:
            if voice_note.size > 30 * 1024 * 1024:
                return JsonResponse({'error': 'Voice note too large. Maximum 30MB'}, status=400)
            
            upload_result = cloudinary.uploader.upload(
                voice_note,
                resource_type='video',
                folder=f'chat/voice_notes/{chat.id}',
                public_id=f"voice_{int(time.time())}_{request.user.id}"
            )
            message = ChatMessage.objects.create(
                chat=chat,
                sender=request.user,
                message_type='voice',
                content="🎙️ Voice note",
                voice_note=upload_result['public_id'],
                voice_duration=int(voice_duration) if voice_duration else None
            )
            last_message_preview = "🎙️ Voice note"
            
        # Handle image upload
        elif media_file and media_file.content_type and media_file.content_type.startswith('image/'):
            if media_file.size > 30 * 1024 * 1024:
                return JsonResponse({'error': 'Image too large. Maximum 30MB'}, status=400)
            
            upload_result = cloudinary.uploader.upload(
                media_file,
                resource_type='image',
                folder=f'chat/images/{chat.id}',
                public_id=f"img_{int(time.time())}_{request.user.id}",
                transformation={'quality': 'auto', 'fetch_format': 'auto', 'width': 800, 'crop': 'limit'}
            )
            message = ChatMessage.objects.create(
                chat=chat,
                sender=request.user,
                message_type='image',
                content=content or "📷 Image",
                image=upload_result['public_id']
            )
            last_message_preview = "📷 Image"
            
        # Handle video upload - FIXED: Removed invalid eager transformation
        elif media_file and media_file.content_type and media_file.content_type.startswith('video/'):
            if media_file.size > 30 * 1024 * 1024:
                return JsonResponse({'error': 'Video too large. Maximum 30MB'}, status=400)
            
            # Simple upload without eager transformations
            upload_result = cloudinary.uploader.upload(
                media_file,
                resource_type='video',
                folder=f'chat/videos/{chat.id}',
                public_id=f"video_{int(time.time())}_{request.user.id}"
            )
            
            message = ChatMessage.objects.create(
                chat=chat,
                sender=request.user,
                message_type='video',
                content=content or "🎬 Video",
                video=upload_result['public_id'],
                video_duration=upload_result.get('duration')
            )
            last_message_preview = "🎬 Video"
        
        else:
            return JsonResponse({'error': 'No valid message content'}, status=400)
        
        if not message:
            return JsonResponse({'error': 'Failed to create message'}, status=500)
        
        # Update chat last message info
        chat.last_message = last_message_preview
        chat.last_message_time = timezone.now()
        chat.last_message_sender = request.user
        chat.save(update_fields=['last_message', 'last_message_time', 'last_message_sender'])
        
        # Mark message as read by sender
        message.read_by.add(request.user)
        
        # Create notifications for other participants
        from social.models import Notification
        
        for participant in chat.participants.exclude(id=request.user.id):
            try:
                Notification.objects.create(
                    recipient=participant,
                    sender=request.user,
                    notification_type='chat_message',
                    message=f"{request.user.username} sent a message"
                )
            except Exception as e:
                logger.error(f"Failed to create notification: {e}")
        
        # Return the message data
        response_data = {
            'success': True,
            'message': {
                'id': message.id,
                'sender': message.sender.username,
                'message_type': message.message_type,
                'content': message.content,
                'created_at': message.created_at.isoformat(),
                'is_sender': True,
                'status': 'sent',
            }
        }
        
        # Add media URLs to response
        if message.message_type == 'image' and message.image:
            response_data['message']['image_url'] = message.image.url
        elif message.message_type == 'video' and message.video:
            response_data['message']['video_url'] = message.video.url
            response_data['message']['video_duration'] = message.video_duration
        elif message.message_type == 'voice' and message.voice_note:
            response_data['message']['voice_url'] = message.voice_note.url
            response_data['message']['voice_duration'] = message.voice_duration
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f"Send message error: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@require_POST
def create_chat(request):
    """Create a new direct message chat"""
    username = request.POST.get('username')
    initial_message = request.POST.get('initial_message', '')
    
    if not username:
        return JsonResponse({'error': 'Username required'}, status=400)
    
    target_user = get_object_or_404(CustomUser, username=username)
    
    if target_user == request.user:
        return JsonResponse({'error': 'Cannot create chat with yourself'}, status=400)
    
    # Check if chat already exists
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
    
    # Create new chat
    chat = Chat.objects.create(
        chat_type='dm',
        created_by=request.user
    )
    chat.participants.add(request.user, target_user)
    chat.admins.add(request.user)
    
    # Send initial message if provided
    if initial_message:
        ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            message_type='text',
            content=initial_message
        )
        chat.last_message = initial_message[:50]
        chat.last_message_time = timezone.now()
        chat.last_message_sender = request.user
        chat.save()
    
    # Create notification
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
    """Add a participant to a group chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    username = request.POST.get('username')
    if not username:
        return JsonResponse({'error': 'Username required'}, status=400)
    
    target_user = get_object_or_404(CustomUser, username=username)
    
    if target_user in chat.participants.all():
        return JsonResponse({'error': 'User already in chat'}, status=400)
    
    chat.participants.add(target_user)
    
    message = request.POST.get('message', '')
    ChatMessage.objects.create(
        chat=chat,
        sender=request.user,
        message_type='system',
        content=f"{request.user.username} added {target_user.username} to the group"
    )
    
    if message:
        ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            message_type='text',
            content=message
        )
    
    Notification.objects.create(
        user=target_user,
        message=f"{request.user.username} added you to {chat.name}",
        notification_type='chat_message'
    )
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def convert_to_group(request, chat_id):
    """Convert a DM to a group chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    if chat.chat_type != 'dm':
        return JsonResponse({'error': 'Chat is already a group'}, status=400)
    
    group_name = request.POST.get('group_name')
    if not group_name:
        return JsonResponse({'error': 'Group name required'}, status=400)
    
    message = request.POST.get('message', '')
    
    chat.chat_type = 'group'
    chat.name = group_name
    chat.save()
    chat.admins.add(request.user)
    
    # Make all participants admins
    for participant in chat.participants.exclude(id=request.user.id):
        chat.admins.add(participant)
    
    ChatMessage.objects.create(
        chat=chat,
        sender=request.user,
        message_type='system',
        content=f"Chat converted to group '{group_name}' by {request.user.username}"
    )
    
    if message:
        ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            message_type='text',
            content=message
        )
    
    return JsonResponse({'success': True, 'chat_id': chat.id})


@login_required
@require_POST
def leave_chat(request, chat_id):
    """Leave a chat"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user, is_active=True)
    
    chat.participants.remove(request.user)
    
    if chat.admins.filter(id=request.user.id).exists():
        chat.admins.remove(request.user)
    
    ChatMessage.objects.create(
        chat=chat,
        sender=request.user,
        message_type='system',
        content=f"{request.user.username} left the chat"
    )
    
    # If no participants left, deactivate chat
    if chat.participants.count() == 0:
        chat.is_active = False
        chat.save()
    
    return JsonResponse({'success': True})


@login_required
def get_requests(request):
    """Get pending chat requests"""
    requests = ChatRequest.objects.filter(
        target_user=request.user,
        status='pending'
    ).select_related('requester', 'chat')
    
    requests_data = []
    for req in requests:
        requests_data.append({
            'id': req.id,
            'requester': req.requester.username,
            'requester_avatar': req.requester.userprofile.profile_picture.url if req.requester.userprofile.profile_picture else None,
            'chat_name': req.chat.name if req.chat.name else f"Chat with {req.requester.username}",
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
    
    if action == 'accept':
        chat_request.accept()
        return JsonResponse({'success': True, 'message': 'Request accepted'})
    elif action == 'reject':
        chat_request.reject()
        return JsonResponse({'success': True, 'message': 'Request rejected'})
    
    return JsonResponse({'error': 'Invalid action'}, status=400)
    
@login_required
@require_POST
def delete_message(request, chat_id, message_id):
    """Delete a single message"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user)
    message = get_object_or_404(ChatMessage, id=message_id, chat=chat, sender=request.user)
    
    message.is_deleted = True
    message.content = "This message was deleted"
    message.message_type = 'system'
    message.save()
    
    return JsonResponse({'success': True})


@login_required
@require_POST
def delete_chat(request, chat_id):
    """Delete entire chat for the user"""
    chat = get_object_or_404(Chat, id=chat_id, participants=request.user)
    
    # Remove user from chat
    chat.participants.remove(request.user)
    
    # If no participants left, delete the chat
    if chat.participants.count() == 0:
        chat.delete()
    else:
        # Add system message
        ChatMessage.objects.create(
            chat=chat,
            sender=request.user,
            message_type='system',
            content=f"{request.user.username} left the chat"
        )
    
    return JsonResponse({'success': True})