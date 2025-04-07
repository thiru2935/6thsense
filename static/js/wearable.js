/**
 * Functions for handling wearable device integration
 */

// Function to simulate data from a wearable device
// In a real application, this would be replaced with actual API calls to device SDKs
function simulateDeviceReading(deviceId, readingType) {
  return new Promise((resolve, reject) => {
    // Simulate API call delay
    setTimeout(() => {
      try {
        let reading = {};
        
        // Generate simulated data based on reading type
        if (readingType === 'blood_glucose') {
          // Generate a random glucose value between 70 and 200
          const value = Math.floor(Math.random() * (200 - 70 + 1)) + 70;
          
          reading = {
            device_id: deviceId,
            reading_type: 'blood_glucose',
            value: value,
            unit: 'mg/dL',
            timestamp: new Date().toISOString()
          };
        } 
        else if (readingType === 'blood_pressure') {
          // Generate random systolic (110-150) and diastolic (70-100) values
          const systolic = Math.floor(Math.random() * (150 - 110 + 1)) + 110;
          const diastolic = Math.floor(Math.random() * (100 - 70 + 1)) + 70;
          const pulse = Math.floor(Math.random() * (100 - 60 + 1)) + 60;
          
          reading = {
            device_id: deviceId,
            reading_type: 'blood_pressure',
            value: systolic, // Store systolic as the main value
            unit: 'mmHg',
            systolic: systolic,
            diastolic: diastolic,
            pulse: pulse,
            timestamp: new Date().toISOString()
          };
        }
        else if (readingType === 'weight') {
          // Generate a random weight between 50 and 100 kg
          const value = Math.floor(Math.random() * (100 - 50 + 1)) + 50;
          
          reading = {
            device_id: deviceId,
            reading_type: 'weight',
            value: value,
            unit: 'kg',
            timestamp: new Date().toISOString()
          };
        }
        
        resolve(reading);
      } catch (error) {
        reject(error);
      }
    }, 1000); // Simulate a 1-second delay
  });
}

// Function to send device reading to the server
function sendDeviceReading(reading) {
  return fetch('/api/device/reading', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(reading)
  })
  .then(response => {
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return response.json();
  });
}

// Function to manually sync a specific device
function syncDevice(deviceId, deviceType) {
  // Show loading state
  const syncButton = document.querySelector(`button[data-device-id="${deviceId}"]`);
  const originalText = syncButton ? syncButton.innerHTML : '';
  
  if (syncButton) {
    syncButton.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Syncing...';
    syncButton.disabled = true;
  }
  
  // Simulate device reading
  return simulateDeviceReading(deviceId, deviceType)
    .then(reading => sendDeviceReading(reading))
    .then(response => {
      // Show success message
      showToast('Device synced successfully!', 'success');
      
      // Reset button state
      if (syncButton) {
        syncButton.innerHTML = originalText;
        syncButton.disabled = false;
      }
      
      return response;
    })
    .catch(error => {
      console.error('Error syncing device:', error);
      
      // Show error message
      showToast('Error syncing device: ' + error.message, 'danger');
      
      // Reset button state
      if (syncButton) {
        syncButton.innerHTML = originalText;
        syncButton.disabled = false;
      }
      
      throw error;
    });
}

// Listen for device sync requests
document.addEventListener('DOMContentLoaded', function() {
  const syncButtons = document.querySelectorAll('.device-sync-btn');
  
  syncButtons.forEach(button => {
    button.addEventListener('click', function(event) {
      event.preventDefault();
      
      const deviceId = this.dataset.deviceId;
      const deviceType = this.dataset.deviceType;
      
      if (deviceId && deviceType) {
        syncDevice(deviceId, deviceType)
          .then(response => {
            // Reload the page after successful sync to show the new data
            if (response.status === 'success') {
              setTimeout(() => {
                window.location.reload();
              }, 1000);
            }
          });
      }
    });
  });
});
