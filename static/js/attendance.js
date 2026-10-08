/**
 * FITCORE - Attendance Module Controller
 */

document.addEventListener('DOMContentLoaded', function () {
  // Quick member search filter for table if needed
  const tableSearchInput = document.getElementById('attendance-search');
  if (tableSearchInput) {
    tableSearchInput.addEventListener('input', function () {
      const term = this.value.toLowerCase();
      const rows = document.querySelectorAll('#attendance-table tbody tr');
      rows.forEach(row => {
        const text = row.textContent.toLowerCase();
        row.style.display = text.includes(term) ? '' : 'none';
      });
    });
  }

  // Live Stopwatch Controller for Checked-In Members and Trainers
  function runStopwatches() {
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

  runStopwatches();
  setInterval(runStopwatches, 1000);
});
