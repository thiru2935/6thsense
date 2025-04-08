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
  
  // Animate elements with data-delay attribute
  document.querySelectorAll('.animate__animated[data-delay]').forEach(function(element) {
    const delay = parseInt(element.getAttribute('data-delay'));
    element.style.animationDelay = delay + 'ms';
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
  
  // Add active class to current nav link
  const currentLocation = window.location.pathname;
  document.querySelectorAll('.navbar .nav-link').forEach(function(link) {
    const href = link.getAttribute('href');
    if (href && currentLocation.startsWith(href) && href !== '/') {
      link.classList.add('active');
    } else if (href === '/' && currentLocation === '/') {
      link.classList.add('active');
    }
  });
  
  // Enhanced scroll behavior for tables with many rows
  document.querySelectorAll('.table-responsive').forEach(function(table) {
    if (table.scrollHeight > table.clientHeight) {
      table.classList.add('scrollable');
    }
  });
  
  // Medical icons hover effects
  document.querySelectorAll('.medical-icon').forEach(function(icon) {
    icon.addEventListener('mouseenter', function() {
      this.classList.add('pulse');
    });
    
    icon.addEventListener('mouseleave', function() {
      this.classList.remove('pulse');
    });
  });
  
  // Enhance device sync buttons
  document.querySelectorAll('.sync-device').forEach(function(button) {
    button.addEventListener('mouseenter', function() {
      const syncIcon = this.querySelector('i');
      if (syncIcon) {
        syncIcon.classList.add('fa-spin');
      }
    });
    
    button.addEventListener('mouseleave', function() {
      const syncIcon = this.querySelector('i');
      if (syncIcon) {
        syncIcon.classList.remove('fa-spin');
      }
    });
  });
  
  // Lazy load images for performance
  if ('loading' in HTMLImageElement.prototype) {
    // Browser supports native lazy loading
    document.querySelectorAll('img').forEach(img => {
      if (!img.hasAttribute('loading')) {
        img.setAttribute('loading', 'lazy');
      }
    });
  } else {
    // Fallback for browsers that don't support lazy loading
    // This would be an ideal place to add a JS lazy loading library
  }
  
  // Smooth scrolling for anchor links
  document.querySelectorAll('a[href^="#"]:not([href="#"])').forEach(function(anchor) {
    anchor.addEventListener('click', function(e) {
      e.preventDefault();
      const targetId = this.getAttribute('href');
      const targetElement = document.querySelector(targetId);
      
      if (targetElement) {
        targetElement.scrollIntoView({
          behavior: 'smooth'
        });
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

// Function to show a toast notification with enhanced styling
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
  
  // Set icon based on type
  let icon = 'info-circle';
  if (type === 'success') icon = 'check-circle';
  if (type === 'warning') icon = 'exclamation-triangle';
  if (type === 'danger') icon = 'exclamation-circle';
  
  const html = `
    <div id="${toastId}" class="toast health-toast ${type}" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="toast-header">
        <i class="fas fa-${icon} me-2"></i>
        <strong class="me-auto">6th Sense</strong>
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
  const toast = new bootstrap.Toast(toastElement, {
    animation: true,
    autohide: true,
    delay: 5000
  });
  toast.show();
  
  // Add animation effect
  setTimeout(() => {
    toastElement.classList.add('show-toast');
  }, 100);
  
  // Auto-remove the element after it's hidden
  toastElement.addEventListener('hidden.bs.toast', function() {
    toastElement.classList.remove('show-toast');
    setTimeout(() => {
      if (toastElement && toastElement.parentNode) {
        toastElement.remove();
      }
    }, 300);
  });
  
  return toast;
}

// Function to animate count up for statistics
function animateCountUp(element, target, duration = 2000) {
  if (typeof element === 'string') {
    element = document.querySelector(element);
  }
  
  if (!element) return;
  
  let start = 0;
  const startTime = performance.now();
  
  function updateCount(currentTime) {
    const elapsedTime = currentTime - startTime;
    if (elapsedTime > duration) {
      element.textContent = target;
      return;
    }
    
    const progress = elapsedTime / duration;
    const currentCount = Math.round(progress * target);
    element.textContent = currentCount;
    
    requestAnimationFrame(updateCount);
  }
  
  requestAnimationFrame(updateCount);
}

// Function to format numbers with commas for thousands
function formatNumber(number) {
  return number.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

// Function to determine if an element is in viewport
function isInViewport(element) {
  if (typeof element === 'string') {
    element = document.querySelector(element);
  }
  
  if (!element) return false;
  
  const rect = element.getBoundingClientRect();
  
  return (
    rect.top >= 0 &&
    rect.left >= 0 &&
    rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
    rect.right <= (window.innerWidth || document.documentElement.clientWidth)
  );
}

// Function to update health indicators with animation
function updateHealthIndicator(element, value, maxValue) {
  if (typeof element === 'string') {
    element = document.querySelector(element);
  }
  
  if (!element) return;
  
  const percentage = (value / maxValue) * 100;
  let colorClass = 'success';
  
  if (percentage > 75) {
    colorClass = 'danger';
  } else if (percentage > 50) {
    colorClass = 'warning';
  }
  
  // Remove existing color classes
  element.classList.remove('bg-success', 'bg-warning', 'bg-danger');
  // Add the new color class
  element.classList.add(`bg-${colorClass}`);
  
  // Animate the width
  element.style.transition = 'width 1s ease';
  element.style.width = `${percentage}%`;
  element.setAttribute('aria-valuenow', value);
}

// Debounce function for performance optimization
function debounce(func, wait = 20, immediate = true) {
  let timeout;
  return function() {
    const context = this, args = arguments;
    const later = function() {
      timeout = null;
      if (!immediate) func.apply(context, args);
    };
    const callNow = immediate && !timeout;
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
    if (callNow) func.apply(context, args);
  };
}

// Apply scroll animations
document.addEventListener('scroll', debounce(function() {
  document.querySelectorAll('.animate-on-scroll:not(.animated)').forEach(function(element) {
    if (isInViewport(element)) {
      element.classList.add('animated');
      element.classList.add('animate__fadeIn');
    }
  });
}));
