/**
 * FITCORE - Real-Time Dashboard & Live Occupancy Controller
 * ZERO CHARTS - Pure responsive cards, progress bars and status badges
 */

document.addEventListener('DOMContentLoaded', function () {
  const occCurrentEl = document.getElementById('live-occupancy-current');
  const occCapacityEl = document.getElementById('live-occupancy-capacity');
  const occPctEl = document.getElementById('live-occupancy-pct');
  const occAvailEl = document.getElementById('live-occupancy-available');
  const occBarEl = document.getElementById('live-occupancy-bar');
  const occStatusBadgeEl = document.getElementById('live-occupancy-status-badge');
  const occStatusTextEl = document.getElementById('live-occupancy-status-text');

  // Function to fetch and update live gym occupancy
  function updateLiveOccupancy() {
    fetch('/api/occupancy')
      .then(response => {
        if (!response.ok) throw new Error('Network error');
        return response.json();
      })
      .then(data => {
        if (!data.success) return;

        // Update numbers
        if (occCurrentEl) occCurrentEl.textContent = data.current;
        if (occCapacityEl) occCapacityEl.textContent = data.capacity;
        if (occPctEl) occPctEl.textContent = `${data.percentage}% OCCUPIED`;
        if (occAvailEl) occAvailEl.textContent = `${data.available} spaces available`;

        // Update Progress Bar
        if (occBarEl) {
          occBarEl.style.width = `${Math.min(100, data.percentage)}%`;
          occBarEl.className = 'fc-occupancy-bar';
          if (data.percentage <= 50) {
            occBarEl.classList.add('bg-success');
          } else if (data.percentage <= 80) {
            occBarEl.classList.add('bg-warning');
          } else if (data.percentage <= 99) {
            occBarEl.classList.add('bg-orange');
          } else {
            occBarEl.classList.add('bg-danger');
          }
        }

        // Update Status Badge
        if (occStatusBadgeEl) {
          occStatusBadgeEl.className = `badge ${data.badge_class} fs-6 py-2 px-3`;
        }
        if (occStatusTextEl) {
          occStatusTextEl.innerHTML = `<span class="me-1">${data.emoji}</span> ${data.status}`;
        }
      })
      .catch(err => {
        console.warn('Occupancy auto-refresh note:', err);
      });
  }

  // Poll every 15 seconds
  if (occCurrentEl) {
    setInterval(updateLiveOccupancy, 15000);
  }

  // Quick Check-In Widget
  const quickForm = document.getElementById('quick-checkin-form');
  const quickInput = document.getElementById('quick-member-id');
  const quickAlert = document.getElementById('quick-checkin-alert');

  if (quickForm && quickInput) {
    quickForm.addEventListener('submit', function (e) {
      e.preventDefault();
      const memberId = quickInput.value.trim();
      if (!memberId) return;

      const submitBtn = quickForm.querySelector('button[type="submit"]');
      const originalText = submitBtn.innerHTML;
      submitBtn.disabled = true;
      submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span> Checking in...';

      fetch('/attendance/api/check-in', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest'
        },
        body: JSON.stringify({ member_id: memberId })
      })
        .then(res => res.json())
        .then(result => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalText;

          if (quickAlert) {
            quickAlert.className = `alert alert-${result.success ? 'success' : 'danger'} alert-dismissible fade show mt-3 mb-0`;
            quickAlert.innerHTML = `
              <div class="d-flex align-items-center">
                <i class="bi ${result.success ? 'bi-check-circle-fill' : 'bi-exclamation-triangle-fill'} me-2 fs-5"></i>
                <div>${result.message}</div>
              </div>
            `;
            quickAlert.classList.remove('d-none');
          }

          if (result.success) {
            quickInput.value = '';
            // Immediately update occupancy widget
            updateLiveOccupancy();
            // Reload page smoothly after 1.5s to refresh tables
            setTimeout(() => {
              window.location.reload();
            }, 1200);
          }
        })
        .catch(err => {
          submitBtn.disabled = false;
          submitBtn.innerHTML = originalText;
          if (quickAlert) {
            quickAlert.className = 'alert alert-danger mt-3 mb-0';
            quickAlert.textContent = 'Server communication error. Please try again.';
            quickAlert.classList.remove('d-none');
          }
        });
    });
  }
});
