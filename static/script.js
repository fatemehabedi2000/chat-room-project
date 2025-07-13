document.addEventListener('DOMContentLoaded', function() {
    // Only initialize chat functionality on the chat page
    if (document.getElementById('messages')) {
        initChat();
    }
});

function initChat() {
    // Connect to WebSocket
    const socket = new WebSocket(`ws://${window.location.host}/ws`);
    
    // Message input and send button
    const messageInput = document.getElementById('message-input');
    const sendButton = document.getElementById('send-btn');
    const messagesContainer = document.getElementById('messages');
    
    // Handle sending messages
    function sendMessage() {
        const content = messageInput.value.trim();
        if (content) {
            socket.send(content);
            messageInput.value = '';
        }
    }
    
    // Send message on button click
    sendButton.addEventListener('click', sendMessage);
    
    // Send message on Enter key (but allow Shift+Enter for new lines)
    messageInput.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Handle incoming WebSocket messages
    socket.onmessage = function(event) {
        const message = JSON.parse(event.data);
        addMessageToUI(message);
    };
    
    // Add a new message to the UI
    function addMessageToUI(message) {
        const alignClass = (message.username === currentUser) ? 'align-right' : 'align-left';
        const messageElement = document.createElement('div');
        messageElement.className = `message ${alignClass}`;
        messageElement.dataset.id = message.id;
        
        messageElement.innerHTML = `
            <div class="message-header">
                <span class="username">${message.username}</span>
                <span class="timestamp">${message.timestamp}</span>
                ${message.username === currentUser ? `
                <div class="message-actions">
                    <button class="edit-btn" title="Edit">✏️</button>
                    <button class="delete-btn" title="Delete">🗑️</button>
                </div>
                ` : ''}
            </div>
            <div class="message-content">${message.content}</div>
        `;
        
        // Prepend new message (to show at button)
        messagesContainer.appendChild(messageElement);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
        
        // Add event listeners for the new message's buttons
        addMessageActionListeners(messageElement);
    }
    
    // Add event listeners for message actions (edit/delete)
    function addMessageActionListeners(messageElement) {
        const editBtn = messageElement.querySelector('.edit-btn');
        const deleteBtn = messageElement.querySelector('.delete-btn');
        
        if (editBtn) {
            editBtn.addEventListener('click', function() {
                startEditingMessage(messageElement);
            });
        }
        
        if (deleteBtn) {
            deleteBtn.addEventListener('click', function() {
                deleteMessage(messageElement.dataset.id, messageElement);
            });
        }
    }
    
    // Start editing a message
    function startEditingMessage(messageElement) {
        const messageId = messageElement.dataset.id;
        const contentElement = messageElement.querySelector('.message-content');
        const currentContent = contentElement.textContent;
        
        // Create edit form
        const editForm = document.createElement('div');
        editForm.className = 'edit-form';
        editForm.innerHTML = `
            <input type="text" value="${currentContent}">
            <button class="save-edit">Save</button>
            <button class="cancel-edit">Cancel</button>
        `;
        
        // Add to message
        messageElement.classList.add('editing');
        messageElement.appendChild(editForm);
        
        // Focus the input
        const input = editForm.querySelector('input');
        input.focus();
        input.setSelectionRange(0, input.value.length);
        
        // Handle save
        editForm.querySelector('.save-edit').addEventListener('click', function() {
            const newContent = input.value.trim();
            if (newContent && newContent !== currentContent) {
                updateMessage(messageId, newContent, messageElement, contentElement);
            }
            cancelEditing(messageElement);
        });
        
        // Handle cancel
        editForm.querySelector('.cancel-edit').addEventListener('click', function() {
            cancelEditing(messageElement);
        });
    }
    
    // Cancel editing
    function cancelEditing(messageElement) {
        messageElement.classList.remove('editing');
        const editForm = messageElement.querySelector('.edit-form');
        if (editForm) {
            editForm.remove();
        }
    }
    
    // Update message via API
    function updateMessage(messageId, newContent, messageElement, contentElement) {
        fetch(`/api/messages/${messageId}`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `new_content=${encodeURIComponent(newContent)}`
        })
        .then(response => {
            if (response.ok) {
                contentElement.textContent = newContent;
            } else {
                throw new Error('Failed to update message');
            }
        })
        .catch(error => {
            console.error('Error updating message:', error);
            alert('Failed to update message');
        });
    }
    
    // Delete message via API
    function deleteMessage(messageId, messageElement) {
        if (confirm('Are you sure you want to delete this message?')) {
            fetch(`/api/messages/${messageId}`, {
                method: 'DELETE'
            })
            .then(response => {
                if (response.ok) {
                    messageElement.remove();
                } else {
                    throw new Error('Failed to delete message');
                }
            })
            .catch(error => {
                console.error('Error deleting message:', error);
                alert('Failed to delete message');
            });
        }
    }
    
    // Add event listeners to existing messages (loaded on page load)
    document.querySelectorAll('.message').forEach(messageElement => {
        addMessageActionListeners(messageElement);
    });
}

