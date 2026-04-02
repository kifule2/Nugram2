// static/js/chat.js

class ChatManager {
    constructor() {
        this.currentChatId = null;
        this.pollingInterval = null;
        this.lastMessageTime = null;
        this.mediaRecorder = null;
        this.audioChunks = [];
        this.isRecording = false;
    }
    
    init() {
        this.loadChatList();
        this.setupEventListeners();
        this.setupPolling();
        this.setupVoiceRecording();
    }
    
    setupPolling() {
        // Poll every 2 seconds if chat is open
        if (this.pollingInterval) clearInterval(this.pollingInterval);
        
        this.pollingInterval = setInterval(() => {
            if (this.currentChatId && document.hasFocus()) {
                this.pollNewMessages();
            }
        }, 2000);
    }
    
    async pollNewMessages() {
        const url = `/chat/${this.currentChatId}/?since=${this.lastMessageTime || ''}`;
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.messages && data.messages.length > 0) {
            this.appendMessages(data.messages);
            this.lastMessageTime = data.messages[data.messages.length - 1].created_at;
        }
    }
    
    setupVoiceRecording() {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                this.mediaRecorder = new MediaRecorder(stream, {
                    mimeType: 'audio/webm;codecs=opus'
                });
                
                this.mediaRecorder.ondataavailable = (event) => {
                    this.audioChunks.push(event.data);
                };
                
                this.mediaRecorder.onstop = async () => {
                    const audioBlob = new Blob(this.audioChunks, { type: 'audio/webm' });
                    const audioFile = new File([audioBlob], 'voice_note.webm', { type: 'audio/webm' });
                    const duration = await this.getAudioDuration(audioBlob);
                    
                    await this.sendVoiceMessage(audioFile, duration);
                    this.audioChunks = [];
                };
            })
            .catch(err => console.error('Microphone access denied:', err));
    }
    
    startRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'inactive') {
            this.audioChunks = [];
            this.mediaRecorder.start(1000); // Collect data every second
            this.isRecording = true;
            
            // Update UI
            document.getElementById('recordBtn').classList.add('recording');
            document.getElementById('recordTimer').style.display = 'block';
            this.startTimer();
        }
    }
    
    stopRecording() {
        if (this.mediaRecorder && this.mediaRecorder.state === 'recording') {
            this.mediaRecorder.stop();
            this.isRecording = false;
            
            // Update UI
            document.getElementById('recordBtn').classList.remove('recording');
            document.getElementById('recordTimer').style.display = 'none';
            this.stopTimer();
        }
    }
    
    getAudioDuration(blob) {
        return new Promise((resolve) => {
            const audio = new Audio();
            audio.src = URL.createObjectURL(blob);
            audio.addEventListener('loadedmetadata', () => {
                resolve(Math.round(audio.duration));
                URL.revokeObjectURL(audio.src);
            });
            audio.addEventListener('error', () => resolve(0));
        });
    }
    
    async sendVoiceMessage(audioFile, duration) {
        const formData = new FormData();
        formData.append('voice_note', audioFile);
        formData.append('message_type', 'voice');
        formData.append('voice_duration', duration);
        
        const response = await fetch(`/chat/${this.currentChatId}/send/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCsrfToken()
            },
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            this.appendMessages([data.message]);
            this.scrollToBottom();
        } else {
            console.error('Failed to send voice note:', data.error);
        }
    }
    
    async sendTextMessage() {
        const input = document.getElementById('messageInput');
        const content = input.value.trim();
        
        if (!content) return;
        
        const formData = new FormData();
        formData.append('content', content);
        formData.append('message_type', 'text');
        
        const response = await fetch(`/chat/${this.currentChatId}/send/`, {
            method: 'POST',
            headers: {
                'X-CSRFToken': this.getCsrfToken()
            },
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            input.value = '';
            this.appendMessages([data.message]);
            this.scrollToBottom();
        } else {
            console.error('Failed to send message:', data.error);
        }
    }
    
    appendMessages(messages) {
        const container = document.getElementById('messagesContainer');
        const shouldScroll = container.scrollHeight - container.scrollTop - container.clientHeight < 100;
        
        messages.forEach(msg => {
            const messageEl = this.createMessageElement(msg);
            container.appendChild(messageEl);
        });
        
        if (shouldScroll) {
            this.scrollToBottom();
        }
    }
    
    createMessageElement(msg) {
        const div = document.createElement('div');
        div.className = `message ${msg.is_sender ? 'message-sent' : 'message-received'}`;
        
        if (msg.message_type === 'text') {
            div.innerHTML = `
                <div class="message-bubble">
                    <div class="message-content">${this.escapeHtml(msg.content)}</div>
                    <div class="message-time">${new Date(msg.created_at).toLocaleTimeString()}</div>
                </div>
            `;
        } else if (msg.message_type === 'voice') {
            div.innerHTML = `
                <div class="message-bubble">
                    <div class="voice-message">
                        <button class="play-voice-btn" data-url="${msg.voice_url}">
                            <i class="fas fa-play"></i>
                        </button>
                        <div class="voice-waveform"></div>
                        <span class="voice-duration">${msg.voice_duration}s</span>
                    </div>
                    <div class="message-time">${new Date(msg.created_at).toLocaleTimeString()}</div>
                </div>
            `;
            
            // Setup audio player
            const playBtn = div.querySelector('.play-voice-btn');
            let audio = null;
            let isPlaying = false;
            
            playBtn.addEventListener('click', () => {
                if (!audio) {
                    audio = new Audio(msg.voice_url);
                    audio.addEventListener('ended', () => {
                        playBtn.innerHTML = '<i class="fas fa-play"></i>';
                        isPlaying = false;
                    });
                }
                
                if (isPlaying) {
                    audio.pause();
                    playBtn.innerHTML = '<i class="fas fa-play"></i>';
                    isPlaying = false;
                } else {
                    audio.play();
                    playBtn.innerHTML = '<i class="fas fa-pause"></i>';
                    isPlaying = true;
                }
            });
        } else if (msg.message_type === 'system') {
            div.className = 'message-system';
            div.innerHTML = `<div class="system-message">${this.escapeHtml(msg.content)}</div>`;
        }
        
        return div;
    }
    
    async loadChatList() {
        const response = await fetch('/chat/');
        const data = await response.json();
        
        const listContainer = document.getElementById('chatList');
        listContainer.innerHTML = '';
        
        data.chats.forEach(chat => {
            const chatEl = this.createChatListItem(chat);
            listContainer.appendChild(chatEl);
        });
    }
    
    createChatListItem(chat) {
        const div = document.createElement('div');
        div.className = 'chat-list-item';
        div.dataset.chatId = chat.id;
        
        const lastMsg = chat.last_message;
        const unreadBadge = chat.unread_count > 0 ? 
            `<span class="unread-badge">${chat.unread_count}</span>` : '';
        
        div.innerHTML = `
            <div class="chat-avatar">
                ${chat.avatar ? 
                    `<img src="${chat.avatar}" alt="${chat.name}">` : 
                    `<div class="avatar-placeholder">${chat.name.charAt(0).toUpperCase()}</div>`}
            </div>
            <div class="chat-info">
                <div class="chat-name">${this.escapeHtml(chat.name)}</div>
                <div class="chat-last-message">
                    ${lastMsg ? 
                        `${this.escapeHtml(lastMsg.sender)}: ${this.escapeHtml(lastMsg.content)}` : 
                        'No messages yet'}
                </div>
            </div>
            ${unreadBadge}
        `;
        
        div.addEventListener('click', () => this.loadChat(chat.id));
        return div;
    }
    
    async loadChat(chatId) {
        this.currentChatId = chatId;
        this.lastMessageTime = null;
        
        const response = await fetch(`/chat/${chatId}/`);
        const data = await response.json();
        
        // Update UI
        document.getElementById('currentChatName').textContent = data.chat.name;
        document.getElementById('chatType').textContent = data.chat.chat_type === 'group' ? 'Group' : 'Direct Message';
        document.getElementById('participantCount').textContent = `${data.chat.participant_count} members`;
        
        // Display messages
        const container = document.getElementById('messagesContainer');
        container.innerHTML = '';
        this.appendMessages(data.messages.reverse()); // Show oldest first
        
        if (data.messages.length > 0) {
            this.lastMessageTime = data.messages[data.messages.length - 1].created_at;
        }
        
        this.scrollToBottom();
        
        // Show/hide group features
        const groupFeatures = document.getElementById('groupFeatures');
        if (data.chat.chat_type === 'group') {
            groupFeatures.style.display = 'flex';
            this.displayParticipants(data.participants);
        } else {
            groupFeatures.style.display = 'none';
        }
        
        // Show chat window
        document.getElementById('chatWindow').classList.remove('hidden');
        document.getElementById('emptyState').classList.add('hidden');
    }
    
    displayParticipants(participants) {
        const container = document.getElementById('participantsList');
        container.innerHTML = '';
        
        participants.forEach(p => {
            const badge = document.createElement('span');
            badge.className = 'participant-badge';
            badge.innerHTML = `
                <img src="${p.avatar || 'https://ui-avatars.com/api/?name=' + p.display_name.charAt(0)}" class="participant-avatar">
                <span>${this.escapeHtml(p.display_name)}</span>
                ${p.is_admin ? '<i class="fas fa-crown admin-icon"></i>' : ''}
            `;
            container.appendChild(badge);
        });
    }
    
    async convertToGroup() {
        const groupName = prompt('Enter group name:', 'My Awesome Group');
        if (!groupName) return;
        
        const formData = new FormData();
        formData.append('group_name', groupName);
        
        const response = await fetch(`/chat/${this.currentChatId}/convert-to-group/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': this.getCsrfToken() },
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            this.loadChat(this.currentChatId);
            this.loadChatList(); // Refresh list to show group name
        }
    }
    
    async addParticipant() {
        const username = prompt('Enter username to add:');
        if (!username) return;
        
        const formData = new FormData();
        formData.append('username', username);
        
        const response = await fetch(`/chat/${this.currentChatId}/add-participant/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': this.getCsrfToken() },
            body: formData
        });
        
        const data = await response.json();
        if (data.success) {
            alert('Invitation sent!');
        } else {
            alert(data.error);
        }
    }
    
    async loadRequests() {
        const response = await fetch('/chat/requests/');
        const data = await response.json();
        
        const container = document.getElementById('requestsModal');
        if (data.requests.length > 0) {
            container.innerHTML = '';
            data.requests.forEach(req => {
                const reqEl = document.createElement('div');
                reqEl.className = 'request-item';
                reqEl.innerHTML = `
                    <div class="request-info">
                        <strong>${this.escapeHtml(req.requester_name)}</strong>
                        ${req.request_type === 'add_to_group' ? 
                            `invited you to join "${this.escapeHtml(req.chat_name)}"` : 
                            `wants to convert chat to group "${this.escapeHtml(req.message)}"`}
                    </div>
                    <div class="request-actions">
                        <button onclick="chatManager.respondToRequest(${req.id}, 'accept')">Accept</button>
                        <button onclick="chatManager.respondToRequest(${req.id}, 'reject')">Reject</button>
                    </div>
                `;
                container.appendChild(reqEl);
            });
            
            // Show modal
            document.getElementById('requestsModal').classList.add('show');
        }
    }
    
    async respondToRequest(requestId, action) {
        const formData = new FormData();
        formData.append('action', action);
        
        const response = await fetch(`/chat/requests/${requestId}/respond/`, {
            method: 'POST',
            headers: { 'X-CSRFToken': this.getCsrfToken() },
            body: formData
        });
        
        if (response.ok) {
            this.loadRequests();
            this.loadChatList();
        }
    }
    
    scrollToBottom() {
        const container = document.getElementById('messagesContainer');
        container.scrollTop = container.scrollHeight;
    }
    
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    
    getCsrfToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]').value;
    }
    
    startTimer() {
        let seconds = 0;
        this.timerInterval = setInterval(() => {
            seconds++;
            const mins = Math.floor(seconds / 60);
            const secs = seconds % 60;
            document.getElementById('recordTimer').textContent = 
                `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }, 1000);
    }
    
    stopTimer() {
        if (this.timerInterval) {
            clearInterval(this.timerInterval);
            document.getElementById('recordTimer').textContent = '00:00';
        }
    }
}

// Initialize when DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.chatManager = new ChatManager();
    window.chatManager.init();
    
    // Global event listeners
    document.getElementById('sendBtn')?.addEventListener('click', () => chatManager.sendTextMessage());
    document.getElementById('messageInput')?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            chatManager.sendTextMessage();
        }
    });
    document.getElementById('recordBtn')?.addEventListener('mousedown', () => chatManager.startRecording());
    document.getElementById('recordBtn')?.addEventListener('mouseup', () => chatManager.stopRecording());
    document.getElementById('recordBtn')?.addEventListener('mouseleave', () => chatManager.stopRecording());
    document.getElementById('convertGroupBtn')?.addEventListener('click', () => chatManager.convertToGroup());
    document.getElementById('addParticipantBtn')?.addEventListener('click', () => chatManager.addParticipant());
    document.getElementById('requestsBtn')?.addEventListener('click', () => chatManager.loadRequests());
});