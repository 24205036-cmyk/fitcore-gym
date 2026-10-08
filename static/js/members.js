/**
 * FITCORE - Members Module JS
 */

document.addEventListener('DOMContentLoaded', function () {
  const planSelect = document.getElementById('member-plan-select');
  const startDateInput = document.getElementById('start_date');
  const endDateInput = document.getElementById('end_date');

  function calculateEndDate() {
    if (!planSelect || !startDateInput || !endDateInput) return;
    
    const selectedOption = planSelect.options[planSelect.selectedIndex];
    if (!selectedOption) return;
    
    const durationDays = parseInt(selectedOption.getAttribute('data-duration') || '30', 10);
    const startVal = startDateInput.value;
    if (!startVal) return;

    const parts = startVal.split('-');
    if (parts.length === 3) {
      const dt = new Date(parts[0], parts[1] - 1, parts[2]);
      dt.setDate(dt.getDate() + durationDays);

      const yyyy = dt.getFullYear();
      const mm = String(dt.getMonth() + 1).padStart(2, '0');
      const dd = String(dt.getDate()).padStart(2, '0');
      endDateInput.value = `${yyyy}-${mm}-${dd}`;
    }
  }

  if (planSelect && startDateInput) {
    planSelect.addEventListener('change', calculateEndDate);
    startDateInput.addEventListener('change', calculateEndDate);
  }
});
