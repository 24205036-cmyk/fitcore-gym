/**
 * FITCORE - Main JavaScript Utilities
 */

document.addEventListener('DOMContentLoaded', function () {
  // 1. Sidebar Toggle (Mobile)
  const sidebarToggle = document.getElementById('sidebarToggle');
  const sidebar = document.getElementById('sidebar');
  let backdrop = document.querySelector('.sidebar-backdrop');

  if (!backdrop) {
    backdrop = document.createElement('div');
    backdrop.className = 'sidebar-backdrop';
    document.body.appendChild(backdrop);
  }

  if (sidebarToggle && sidebar) {
    sidebarToggle.addEventListener('click', function () {
      sidebar.classList.toggle('show');
      backdrop.classList.toggle('show');
    });

    backdrop.addEventListener('click', function () {
      sidebar.classList.remove('show');
      backdrop.classList.remove('show');
    });
  }

  // 2. Auto-dismiss flash alerts after 6 seconds
  const alerts = document.querySelectorAll('.alert-dismissible');
  alerts.forEach(function (alert) {
    setTimeout(function () {
      const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
      if (bsAlert) {
        bsAlert.close();
      }
    }, 6000);
  });

  // 3. Confirm dialog helper
  document.querySelectorAll('[data-confirm]').forEach(function (element) {
    element.addEventListener('click', function (e) {
      const message = this.getAttribute('data-confirm') || 'Are you sure you want to proceed?';
      if (!confirm(message)) {
        e.preventDefault();
      }
    });
  });

  // 4. Live Attendance Stopwatch Timer Controller
  function updateLiveStopwatches() {
    const now = new Date();
    document.querySelectorAll('.live-stopwatch').forEach(function (el) {
      const rawIso = el.getAttribute('data-checkin-iso') || el.getAttribute('data-checkin');
      if (!rawIso) return;

      let startDate = new Date(rawIso);
      if (isNaN(startDate.getTime())) {
        startDate = new Date(rawIso.replace(' ', 'T'));
      }
      if (isNaN(startDate.getTime())) return;

      const diffMs = Math.max(0, now.getTime() - startDate.getTime());
      const totalSec = Math.floor(diffMs / 1000);
      const hours = Math.floor(totalSec / 3600);
      const minutes = Math.floor((totalSec % 3600) / 60);
      const seconds = totalSec % 60;

      const formatted = 
        String(hours).padStart(2, '0') + ':' + 
        String(minutes).padStart(2, '0') + ':' + 
        String(seconds).padStart(2, '0');

      const targetSpan = el.querySelector('.timer-display');
      if (targetSpan) {
        targetSpan.textContent = formatted;
      } else {
        el.textContent = formatted;
      }
    });
  }

  updateLiveStopwatches();
  setInterval(updateLiveStopwatches, 1000);
});

// Print trigger function
window.printReport = function () {
  window.print();
};

