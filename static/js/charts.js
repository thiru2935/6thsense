/**
 * Create and render charts for patient health data
 */

// Function to create a blood glucose chart
function createGlucoseChart(elementId, readings) {
  const ctx = document.getElementById(elementId);
  
  if (!ctx || !readings || readings.length === 0) {
    console.warn('Cannot create glucose chart: missing element or data');
    return null;
  }
  
  // Sort readings by timestamp
  readings.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  
  // Extract data for the chart
  const labels = readings.map(r => {
    const date = new Date(r.timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  });
  
  const values = readings.map(r => {
    // Convert all values to mg/dL for consistency
    if (r.unit === 'mmol/L') {
      return r.value * 18; // Convert mmol/L to mg/dL
    }
    return r.value;
  });
  
  // Determine which points are abnormal
  const abnormalIndices = readings.map((r, i) => r.is_abnormal ? i : -1).filter(i => i !== -1);
  
  // Create the chart
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: 'Blood Glucose (mg/dL)',
        data: values,
        borderColor: 'rgba(75, 192, 192, 1)',
        tension: 0.1,
        fill: false
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: false,
          title: {
            display: true,
            text: 'mg/dL'
          },
          grid: {
            color: 'rgba(200, 200, 200, 0.1)'
          }
        },
        x: {
          grid: {
            display: false
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
        },
        tooltip: {
          callbacks: {
            afterLabel: function(context) {
              const index = context.dataIndex;
              const reading = readings[index];
              return reading.is_abnormal ? 'Abnormal reading' : '';
            }
          }
        },
        annotation: {
          annotations: {
            highLine: {
              type: 'line',
              yMin: 180,
              yMax: 180,
              borderColor: 'rgba(255, 99, 132, 0.5)',
              borderWidth: 2,
              label: {
                content: 'High',
                enabled: true,
                position: 'start'
              }
            },
            lowLine: {
              type: 'line',
              yMin: 70,
              yMax: 70,
              borderColor: 'rgba(255, 99, 132, 0.5)',
              borderWidth: 2,
              label: {
                content: 'Low',
                enabled: true,
                position: 'start'
              }
            }
          }
        }
      }
    }
  });
  
  return chart;
}

// Function to create a blood pressure chart
function createBloodPressureChart(elementId, readings) {
  const ctx = document.getElementById(elementId);
  
  if (!ctx || !readings || readings.length === 0) {
    console.warn('Cannot create blood pressure chart: missing element or data');
    return null;
  }
  
  // Sort readings by timestamp
  readings.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
  
  // Extract data for the chart
  const labels = readings.map(r => {
    const date = new Date(r.timestamp);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
  });
  
  const systolicValues = readings.map(r => r.value_systolic);
  const diastolicValues = readings.map(r => r.value_diastolic);
  const pulseValues = readings.map(r => r.value_pulse);
  
  // Create the chart
  const chart = new Chart(ctx, {
    type: 'line',
    data: {
      labels: labels,
      datasets: [
        {
          label: 'Systolic',
          data: systolicValues,
          borderColor: 'rgba(255, 99, 132, 1)',
          tension: 0.1,
          fill: false
        },
        {
          label: 'Diastolic',
          data: diastolicValues,
          borderColor: 'rgba(54, 162, 235, 1)',
          tension: 0.1,
          fill: false
        },
        {
          label: 'Pulse',
          data: pulseValues,
          borderColor: 'rgba(255, 206, 86, 1)',
          tension: 0.1,
          fill: false,
          hidden: true // Hidden by default
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        y: {
          beginAtZero: false,
          title: {
            display: true,
            text: 'mmHg / BPM'
          },
          grid: {
            color: 'rgba(200, 200, 200, 0.1)'
          }
        },
        x: {
          grid: {
            display: false
          }
        }
      },
      plugins: {
        legend: {
          position: 'top',
        },
        tooltip: {
          callbacks: {
            afterLabel: function(context) {
              const index = context.dataIndex;
              const reading = readings[index];
              return reading.is_abnormal ? 'Abnormal reading' : '';
            }
          }
        },
        annotation: {
          annotations: {
            highSystolicLine: {
              type: 'line',
              yMin: 140,
              yMax: 140,
              borderColor: 'rgba(255, 99, 132, 0.5)',
              borderWidth: 2,
              label: {
                content: 'High Systolic',
                enabled: true,
                position: 'start'
              }
            },
            highDiastolicLine: {
              type: 'line',
              yMin: 90,
              yMax: 90,
              borderColor: 'rgba(54, 162, 235, 0.5)',
              borderWidth: 2,
              label: {
                content: 'High Diastolic',
                enabled: true,
                position: 'start'
              }
            }
          }
        }
      }
    }
  });
  
  return chart;
}

// Function to create a risk score gauge chart
function createRiskGaugeChart(elementId, riskScore) {
  const ctx = document.getElementById(elementId);
  
  if (!ctx) {
    console.warn('Cannot create risk gauge chart: missing element');
    return null;
  }
  
  let color = 'green';
  if (riskScore > 75) {
    color = 'red';
  } else if (riskScore > 50) {
    color = 'orange';
  } else if (riskScore > 25) {
    color = 'yellow';
  }
  
  const chart = new Chart(ctx, {
    type: 'doughnut',
    data: {
      datasets: [{
        data: [riskScore, 100 - riskScore],
        backgroundColor: [color, 'lightgray'],
        circumference: 180,
        rotation: 270
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        tooltip: {
          enabled: false
        },
        legend: {
          display: false
        },
        title: {
          display: true,
          text: 'Risk Score',
          position: 'bottom'
        }
      },
      cutout: '80%'
    },
    plugins: [{
      id: 'centerText',
      afterDraw: function(chart) {
        const width = chart.width;
        const height = chart.height;
        const ctx = chart.ctx;
        
        ctx.restore();
        const fontSize = (height / 100).toFixed(2);
        ctx.font = fontSize + 'em sans-serif';
        ctx.textBaseline = 'middle';
        
        const text = riskScore;
        const textX = Math.round((width - ctx.measureText(text).width) / 2);
        const textY = height / 2;
        
        ctx.fillText(text, textX, textY);
        ctx.save();
      }
    }]
  });
  
  return chart;
}

// Function to create a distribution chart for patient diagnoses
function createDiagnosisChart(elementId, diagnosisSummary) {
  const ctx = document.getElementById(elementId);
  
  if (!ctx || !diagnosisSummary || diagnosisSummary.length === 0) {
    console.warn('Cannot create diagnosis chart: missing element or data');
    return null;
  }
  
  // Extract data for the chart
  const labels = diagnosisSummary.map(d => d[0] || 'Undiagnosed');
  const values = diagnosisSummary.map(d => d[1]);
  
  // Generate colors
  const colors = [
    'rgba(255, 99, 132, 0.7)',
    'rgba(54, 162, 235, 0.7)',
    'rgba(255, 206, 86, 0.7)',
    'rgba(75, 192, 192, 0.7)',
    'rgba(153, 102, 255, 0.7)',
    'rgba(255, 159, 64, 0.7)'
  ];
  
  // Create the chart
  const chart = new Chart(ctx, {
    type: 'pie',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: colors.slice(0, values.length),
        borderWidth: 1
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
        },
        title: {
          display: true,
          text: 'Patients by Diagnosis'
        }
      }
    }
  });
  
  return chart;
}
