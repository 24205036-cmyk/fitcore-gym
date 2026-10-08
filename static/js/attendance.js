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
});
