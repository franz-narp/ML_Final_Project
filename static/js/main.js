/**
 * EstiMate — Frontend UI Controller
 * Handles interactive buttons and sliders for Bedrooms, Bathrooms, Floor Area, and Land Area.
 */
(function initUI() {
  const ACTIVE_BTN_CLASSES = ['bg-primary', 'text-white', 'font-bold', 'shadow-md', 'shadow-primary/25', 'border-primary'];
  const INACTIVE_BTN_CLASSES = ['bg-surface-container-low', 'text-secondary', 'border-outline-variant', 'font-medium'];

  // Toggle active styling within a button group
  function setActiveButton(activeBtn, buttonGroup) {
    buttonGroup.forEach((btn) => {
      btn.classList.remove(...ACTIVE_BTN_CLASSES);
      btn.classList.add(...INACTIVE_BTN_CLASSES);
    });
    activeBtn.classList.add(...ACTIVE_BTN_CLASSES);
    activeBtn.classList.remove(...INACTIVE_BTN_CLASSES);
  }

  // Reusable stepper setup for Bedrooms & Bathrooms
  function setupStepper({ buttonSelector, dataKey, rangeId, displayId, maxThreshold, singular, plural }) {
    const buttons = document.querySelectorAll(buttonSelector);
    const rangeInput = document.getElementById(rangeId);
    const displayLabel = document.getElementById(displayId);

    function formatLabel(val) {
      if (val >= maxThreshold) return `${maxThreshold}+ ${plural}`;
      return `${val} ${val === 1 ? singular : plural}`;
    }

    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const value = parseFloat(btn.dataset[dataKey]);
        setActiveButton(btn, buttons);
        if (rangeInput) rangeInput.value = value;
        if (displayLabel) displayLabel.textContent = formatLabel(value);
      });
    });

    if (rangeInput) {
      rangeInput.addEventListener('input', (e) => {
        const value = parseFloat(e.target.value);
        if (displayLabel) displayLabel.textContent = formatLabel(value);
        buttons.forEach((btn) => {
          if (parseFloat(btn.dataset[dataKey]) === value) {
            setActiveButton(btn, buttons);
          }
        });
      });
    }
  }

  // Reusable area slider & input setup (in sqm)
  function setupAreaControl({ inputId, rangeId, min, max }) {
    const textInput = document.getElementById(inputId);
    const rangeInput = document.getElementById(rangeId);

    if (!textInput || !rangeInput) return;

    rangeInput.addEventListener('input', (e) => {
      const val = parseInt(e.target.value, 10);
      textInput.value = val.toLocaleString('en-US');
    });

    textInput.addEventListener('change', (e) => {
      const raw = parseInt(e.target.value.replace(/[^0-9]/g, ''), 10) || min;
      const clamped = Math.max(min, Math.min(max, raw));
      textInput.value = clamped.toLocaleString('en-US');
      rangeInput.value = clamped;
    });
  }

  // Initialize Bedrooms & Bathrooms steppers
  setupStepper({
    buttonSelector: '.bed-btn',
    dataKey: 'beds',
    rangeId: 'bedRange',
    displayId: 'bedDisplay',
    maxThreshold: 5,
    singular: 'Bed',
    plural: 'Beds',
  });

  setupStepper({
    buttonSelector: '.bath-btn',
    dataKey: 'baths',
    rangeId: 'bathRange',
    displayId: 'bathDisplay',
    maxThreshold: 4,
    singular: 'Bath',
    plural: 'Baths',
  });

  // Initialize Floor Area (20 - 1,000 sqm) & Land Area (20 - 30,000 sqm)
  setupAreaControl({
    inputId: 'floorInput',
    rangeId: 'floorRange',
    min: 20,
    max: 1000,
  });

  setupAreaControl({
    inputId: 'lotInput',
    rangeId: 'lotRange',
    min: 20,
    max: 30000,
  });

  // Calculate Value Button (Visual pulse feedback)
  const recalculateBtn = document.getElementById('recalculateBtn');
  const heroPrice = document.getElementById('heroEstimatedPrice');

  if (recalculateBtn && heroPrice) {
    recalculateBtn.addEventListener('click', () => {
      heroPrice.classList.add('opacity-40');
      setTimeout(() => heroPrice.classList.remove('opacity-40'), 150);
    });
  }
})();
