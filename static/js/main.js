document.addEventListener('DOMContentLoaded', function() {
  // Initialize tooltips
  var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });
  
  // Initialize popovers
  var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
  var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
    return new bootstrap.Popover(popoverTriggerEl);
  });
  
  // Initialize any date pickers
  const datePickers = document.querySelectorAll('.datepicker');
  if (datePickers.length > 0) {
    datePickers.forEach(function(input) {
      // Using native input[type=date] functionality
      // You could add a more sophisticated date picker library if needed
    });
  }
  
  // Handle alert dismissals 
  document.querySelectorAll('.alert .btn-close').forEach(function(button) {
    button.addEventListener('click', function() {
      this.closest('.alert').remove();
    });
  });
  
  // Automatically fade out flash messages after 5 seconds
  setTimeout(function() {
    document.querySelectorAll('.alert.alert-success, .alert.alert-info').forEach(function(alert) {
      alert.classList.add('fade');
      setTimeout(function() {
        if (alert && alert.parentNode) {
          alert.parentNode.removeChild(alert);
        }
      }, 500);
    });
  }, 5000);
  
  // Form validation
  document.querySelectorAll('form').forEach(function(form) {
    form.addEventListener('submit', function(event) {
      if (!form.checkValidity()) {
        event.preventDefault();
        event.stopPropagation();
      }
      
      form.classList.add('was-validated');
    }, false);
  });
  
  // Toggle password visibility
  document.querySelectorAll('.toggle-password').forEach(function(toggle) {
    toggle.addEventListener('click', function() {
      const passwordInput = document.querySelector(this.dataset.target);
      if (passwordInput) {
        const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
        passwordInput.setAttribute('type', type);
        this.querySelector('i').classList.toggle('fa-eye');
        this.querySelector('i').classList.toggle('fa-eye-slash');
      }
    });
  });
});

// Function to format dates in a user-friendly way
function formatDate(dateString) {
  const date = new Date(dateString);
  return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
}

// Function to show a loading spinner
function showSpinner(targetElement) {
  const spinner = document.createElement('div');
  spinner.className = 'spinner-border text-primary spinner-border-sm';
  spinner.setAttribute('role', 'status');
  
  const span = document.createElement('span');
  span.className = 'visually-hidden';
  span.textContent = 'Loading...';
  
  spinner.appendChild(span);
  
  if (typeof targetElement === 'string') {
    targetElement = document.querySelector(targetElement);
  }
  
  if (targetElement) {
    // Save the original content
    targetElement.dataset.originalContent = targetElement.innerHTML;
    targetElement.innerHTML = '';
    targetElement.appendChild(spinner);
    targetElement.disabled = true;
  }
  
  return spinner;
}

// Function to hide the loading spinner
function hideSpinner(targetElement) {
  if (typeof targetElement === 'string') {
    targetElement = document.querySelector(targetElement);
  }
  
  if (targetElement && targetElement.dataset.originalContent) {
    targetElement.innerHTML = targetElement.dataset.originalContent;
    targetElement.disabled = false;
    delete targetElement.dataset.originalContent;
  }
}

// Function to show a toast notification
function showToast(message, type = 'info') {
  const toastContainer = document.getElementById('toast-container');
  
  if (!toastContainer) {
    // Create a toast container if it doesn't exist
    const container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    document.body.appendChild(container);
  }
  
  const toastId = 'toast-' + Date.now();
  const html = `
    <div id="${toastId}" class="toast" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="toast-header">
        <span class="rounded me-2 bg-${type}" style="width: 20px; height: 20px;"></span>
        <strong class="me-auto">Notification</strong>
        <small>Just now</small>
        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
      <div class="toast-body">
        ${message}
      </div>
    </div>
  `;
  
  document.getElementById('toast-container').insertAdjacentHTML('beforeend', html);
  
  const toastElement = document.getElementById(toastId);
  const toast = new bootstrap.Toast(toastElement);
  toast.show();
  
  // Auto-remove the element after it's hidden
  toastElement.addEventListener('hidden.bs.toast', function() {
    toastElement.remove();
  });
  
  return toast;
}
