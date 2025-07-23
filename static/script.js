// ChatApp.js - Complete Implementation
if (!window.ChatAppInitialized) {
    document.addEventListener('DOMContentLoaded', function() {
        if (document.getElementById('messages')) {
            new ChatApp();
            window.ChatAppInitialized = true;
        }
    });
}

class ChatApp {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 3000;
        this.currentUser = document.getElementById('app-data')?.dataset.currentUser || 'anonymous';
        this.isTyping = false;
        
        this.initElements();
        this.initEventListeners();
        this.connectWebSocket();
        this.scrollToBottom(true);
    }

    initElements() {
        this.elements = {
            messageInput: document.getElementById('message-input'),
            sendButton: document.getElementById('send-btn'),
            messagesContainer: document.getElementById('messages'),
            fileInput: document.getElementById('file-input'),
            filePreview: document.getElementById('file-preview'),
            removeFileBtn: document.getElementById('remove-file-btn'),
            messageForm: document.getElementById('message-form')
        };
    }

    initEventListeners() {
        const { messageForm, messageInput, fileInput, removeFileBtn } = this.elements;

        messageForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        messageInput.addEventListener('input', () => {
            this.autoResizeTextarea();
            this.handleTyping();
        });

        messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        fileInput.addEventListener('change', () => this.handleFileSelect());
        removeFileBtn.addEventListener('click', () => this.resetFileInput());

        document.querySelectorAll('.message').forEach(message => {
            this.addMessageActionListeners(message);
        });
    }

    connectWebSocket() {
        this.socket = new WebSocket(`ws://${window.location.host}/ws`);

        this.socket.onopen = () => {
            this.reconnectAttempts = 0;
            this.showToast('Connected to chat', 'success');
        };

        this.socket.onclose = () => {
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                this.showToast('Connection lost. Reconnecting...', 'warning');
                setTimeout(() => this.connectWebSocket(), this.reconnectDelay);
                this.reconnectAttempts++;
            } else {
                this.showToast('Failed to reconnect. Please refresh the page.', 'error');
            }
        };

        this.socket.onerror = (error) => {
            console.error('WebSocket error:', error);
            this.showToast('Connection error', 'error');
        };

        this.socket.onmessage = (event) => {
            try {
                const message = JSON.parse(event.data);
                if (message.id && message.content && message.username) {
                    this.addMessageToUI(message);
                } else {
                    console.error('Invalid message format:', message);
                }
            } catch (error) {
                console.error('Error parsing message:', error);
            }
        };
    }

    async sendMessage() {
        const { messageForm } = this.elements;
        const formData = new FormData(messageForm);
        const content = formData.get('content')?.trim() || '';
        const file = formData.get('attachment');

        if (!content && !file) {
            this.showToast('Message cannot be empty', 'error');
            return;
        }

        try {
            this.setSendButtonState(true);
            
            if (file && file.size > 0) {
                this.showFileUploadStatus('Uploading file...');
            }

            const response = await fetch('/api/messages', {
                method: 'POST',
                body: formData
            });
            
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(errorData.message || 'Failed to send message');
            }
            
            this.resetForm();
        } catch (error) {
            console.error('Error sending message:', error);
            this.showToast(error.message || 'Failed to send message', 'error');
        } finally {
            this.setSendButtonState(false);
        }
    }

    addMessageToUI(message) {
        const messagesContainer = this.elements.messagesContainer;
        const messageElement = this.createMessageElement(message);
        messagesContainer.appendChild(messageElement);
        this.addMessageActionListeners(messageElement);
        this.scrollToBottom();
    }

    createMessageElement(message) {
        const alignClass = message.username === this.currentUser ? 'message-right' : 'message-left';
        const messageElement = document.createElement('div');
        messageElement.className = `message ${alignClass}`;
        messageElement.dataset.id = message.id;
        messageElement.dataset.timestamp = new Date(message.timestamp).getTime();
        
        const formattedTime = this.formatTimestamp(message.timestamp);
        
        messageElement.innerHTML = `
            <div class="message-header">
                <span class="message-user">${message.username}</span>
                <span class="message-time">${formattedTime}</span>
                ${message.username === this.currentUser ? `
                <div class="message-actions">
                    <button class="message-action edit-btn" aria-label="Edit message">✏️</button>
                    <button class="message-action delete-btn" aria-label="Delete message">🗑️</button>
                </div>
                ` : ''}
            </div>
            <div class="message-content">${message.content}</div>
            ${message.has_attachment ? this.createAttachmentHTML(message.attachment) : ''}
        `;
        
        return messageElement;
    }

    createAttachmentHTML(attachment) {
        const type = attachment.mime_type.split('/')[0];
        let preview = '';
        
        if (type === 'image') {
            preview = `
                <div class="attachment-preview">
                    <img src="/attachments/${attachment.id}" 
                         alt="${attachment.file_name}"
                         loading="lazy">
                </div>
            `;
        } else if (type === 'video') {
            preview = `
                <video controls preload="metadata">
                    <source src="/attachments/${attachment.id}" 
                            type="${attachment.mime_type}">
                    Your browser doesn't support video
                </video>
            `;
        } else if (type === 'audio') {
            preview = `
                <audio controls preload="metadata">
                    <source src="/attachments/${attachment.id}" 
                            type="${attachment.mime_type}">
                    Your browser doesn't support audio
                </audio>
            `;
        } else {
            const icon = attachment.mime_type === 'application/pdf' ? '📄' : '📎';
            preview = `
                <div class="file-icon">
                    ${icon}
                    <span>${attachment.file_name}</span>
                </div>
            `;
        }
        
        return `
            <div class="attachment" data-type="${type}">
                <a href="/attachments/${attachment.id}" 
                   target="_blank"
                   rel="noopener noreferrer"
                   download="${attachment.file_name}">
                    ${preview}
                    <span class="file-size">(${this.formatFileSize(attachment.file_size)})</span>
                </a>
            </div>
        `;
    }

    addMessageActionListeners(messageElement) {
        const editBtn = messageElement.querySelector('.edit-btn');
        const deleteBtn = messageElement.querySelector('.delete-btn');
        
        if (editBtn) {
            editBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.startEditingMessage(messageElement);
            });
        }
        
        if (deleteBtn) {
            deleteBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.deleteMessage(messageElement.dataset.id, messageElement);
            });
        }
    }

    startEditingMessage(messageElement) {
        const messageId = messageElement.dataset.id;
        const contentElement = messageElement.querySelector('.message-content');
        const currentContent = contentElement.textContent;
        
        const editForm = document.createElement('div');
        editForm.className = 'edit-form';
        editForm.innerHTML = `
            <input type="text" class="edit-input" value="${currentContent}">
            <button type="button" class="save-edit">Save</button>
            <button type="button" class="cancel-edit">Cancel</button>
        `;
        
        messageElement.classList.add('editing');
        messageElement.appendChild(editForm);
        
        const input = editForm.querySelector('.edit-input');
        input.focus();
        input.setSelectionRange(0, input.value.length);
        
        editForm.querySelector('.save-edit').addEventListener('click', () => {
            const newContent = input.value.trim();
            if (newContent && newContent !== currentContent) {
                this.updateMessage(messageId, newContent, messageElement, contentElement);
            }
            this.cancelEditing(messageElement);
        });
        
        editForm.querySelector('.cancel-edit').addEventListener('click', () => {
            this.cancelEditing(messageElement);
        });
    }

    cancelEditing(messageElement) {
        messageElement.classList.remove('editing');
        const editForm = messageElement.querySelector('.edit-form');
        if (editForm) {
            editForm.remove();
        }
    }

    updateMessage(messageId, newContent, messageElement, contentElement) {
        fetch(`/api/messages/${messageId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ new_content: newContent })
        })
        .then(response => {
            if (response.ok) {
                contentElement.textContent = newContent;
                this.showToast('Message updated', 'success');
            } else {
                throw new Error('Failed to update message');
            }
        })
        .catch(error => {
            console.error('Error updating message:', error);
            this.showToast('Failed to update message', 'error');
        });
    }

    deleteMessage(messageId, messageElement) {
        if (confirm('Are you sure you want to delete this message?')) {
            fetch(`/api/messages/${messageId}`, {
                method: 'DELETE'
            })
            .then(response => {
                if (response.ok) {
                    messageElement.remove();
                    this.showToast('Message deleted', 'success');
                } else {
                    throw new Error('Failed to delete message');
                }
            })
            .catch(error => {
                console.error('Error deleting message:', error);
                this.showToast('Failed to delete message', 'error');
            });
        }
    }

    handleFileSelect() {
        const { fileInput, filePreview, removeFileBtn } = this.elements;
        const file = fileInput.files[0];
        
        if (!file) return;
        
        const validTypes = ['image/*', 'video/*', 'audio/*', 'application/pdf', 'text/plain'];
        const maxSize = 50 * 1024 * 1024; // 50MB
        
        if (!validTypes.some(type => file.type.match(type.replace('*', '.*')))) {
            this.showToast('Unsupported file type', 'error');
            this.resetFileInput();
            return;
        }
        
        if (file.size > maxSize) {
            this.showToast(`File too large (max ${this.formatFileSize(maxSize)})`, 'error');
            this.resetFileInput();
            return;
        }
        
        filePreview.innerHTML = `
            <div class="file-preview-item">
                <span class="file-preview-name">${file.name}</span>
                <span class="file-preview-size">${this.formatFileSize(file.size)}</span>
            </div>
        `;
        filePreview.style.display = 'block';
        removeFileBtn.style.display = 'inline-block';
    }

    resetFileInput() {
        const { fileInput, filePreview, removeFileBtn } = this.elements;
        fileInput.value = '';
        filePreview.style.display = 'none';
        filePreview.innerHTML = '';
        removeFileBtn.style.display = 'none';
    }

    showFileUploadStatus(message) {
        const { filePreview } = this.elements;
        filePreview.innerHTML = `<div class="file-preview-item">${message}</div>`;
        filePreview.style.display = 'block';
    }

    setSendButtonState(isSending) {
        const { sendButton } = this.elements;
        sendButton.disabled = isSending;
        sendButton.innerHTML = isSending 
            ? '<span class="spinner"></span> Sending...' 
            : '<span class="btn-text">Send</span>';
    }

    resetForm() {
        const { messageInput } = this.elements;
        messageInput.value = '';
        this.resetFileInput();
        this.autoResizeTextarea();
    }

    autoResizeTextarea() {
        const { messageInput } = this.elements;
        messageInput.style.height = 'auto';
        messageInput.style.height = `${Math.min(messageInput.scrollHeight, 150)}px`;
    }

    scrollToBottom(instant = false) {
        const { messagesContainer } = this.elements;
        messagesContainer.scrollTo({
            top: messagesContainer.scrollHeight,
            behavior: instant ? 'auto' : 'smooth'
        });
    }

    formatTimestamp(timestamp) {
        const date = new Date(timestamp);
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    }

    formatFileSize(bytes) {
        if (bytes < 1024) return `${bytes} B`;
        if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
        return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    }

    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
}