/**
 * Functions for handling chatbot interactions
 */

document.addEventListener('DOMContentLoaded', function() {
  const chatbotForm = document.getElementById('chatbot-form');
  const chatbotInput = document.getElementById('chatbot-input');
  const chatbotMessages = document.getElementById('chatbot-messages');
  
  if (chatbotForm && chatbotInput && chatbotMessages) {
    chatbotForm.addEventListener('submit', function(event) {
      event.preventDefault();
      
      const message = chatbotInput.value.trim();
      if (!message) return;
      
      // Clear the input
      chatbotInput.value = '';
      
      // Show the user message immediately
      appendMessage('user', message);
      
      // Scroll to bottom of chat
      scrollToBottom();
      
      // Send message to server
      fetch('/chatbot/send', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: new URLSearchParams({
          'message': message
        })
      })
      .then(response => {
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        return response.json();
      })
      .then(data => {
        if (data.status === 'success') {
          // The user message is already shown, so we just need to show the bot response
          appendMessage('bot', data.bot_message.message);
          
          // Scroll to bottom of chat
          scrollToBottom();
        }
      })
      .catch(error => {
        console.error('Error sending message:', error);
        appendMessage('bot', 'Sorry, there was an error processing your message. Please try again.');
        scrollToBottom();
      });
    });
    
    // End chat session when leaving the page
    window.addEventListener('beforeunload', function() {
      // End the chat session
      fetch('/chatbot/end_session', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-www-form-urlencoded',
        }
      }).catch(err => console.error('Error ending chat session:', err));
    });
  }
  
  // Scroll to bottom of chat on page load
  scrollToBottom();
});

// Function to append a message to the chat
function appendMessage(sender, message) {
  const chatbotMessages = document.getElementById('chatbot-messages');
  if (!chatbotMessages) return;
  
  const messageDiv = document.createElement('div');
  messageDiv.classList.add('chat-message', sender === 'user' ? 'user-message' : 'bot-message');
  
  const messageContent = document.createElement('div');
  messageContent.classList.add('message-content');
  messageContent.textContent = message;
  
  const timestamp = document.createElement('div');
  timestamp.classList.add('message-timestamp');
  const now = new Date();
  timestamp.textContent = now.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  
  messageDiv.appendChild(messageContent);
  messageDiv.appendChild(timestamp);
  
  chatbotMessages.appendChild(messageDiv);
}

// Function to scroll to the bottom of the chat
function scrollToBottom() {
  const chatbotMessages = document.getElementById('chatbot-messages');
  if (chatbotMessages) {
    chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
  }
}
