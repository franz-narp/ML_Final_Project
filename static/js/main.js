/**
 * EstiMate — Frontend UI Controller
 * Handles property inputs, requests an estimate, and renders the results.
 */
(function initUI() {
  const ACTIVE_BTN_CLASSES = ['bg-primary', 'text-white', 'font-bold', 'shadow-md', 'shadow-primary/25', 'border-primary'];
  const INACTIVE_BTN_CLASSES = ['bg-surface-container-low', 'text-secondary', 'border-outline-variant', 'font-medium'];
  const LIMITS = JSON.parse(document.getElementById('limitsData').textContent);
  const CONDO = 'Condo / Apartment';

  const byId = (id) => document.getElementById(id);
  const formatArea = (value) => `${Number(value).toLocaleString('en-US')} sqm`;

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
  function setupStepper({ buttonSelector, dataKey, rangeId, displayId, singular, plural }) {
    const buttons = Array.from(document.querySelectorAll(buttonSelector));
    const rangeInput = byId(rangeId);
    const displayLabel = byId(displayId);

    function setValue(value) {
      rangeInput.value = value;
      displayLabel.textContent = `${value} ${value === 1 ? singular : plural}`;
      const match = buttons.find((btn) => parseInt(btn.dataset[dataKey], 10) === value);
      if (match) setActiveButton(match, buttons);
    }

    buttons.forEach((btn) => {
      btn.addEventListener('click', () => setValue(parseInt(btn.dataset[dataKey], 10)));
    });
    rangeInput.addEventListener('input', (e) => setValue(parseInt(e.target.value, 10)));

    return {
      setMax(max) {
        rangeInput.max = max;
        buttons.forEach((btn) => {
          btn.classList.toggle('hidden', parseInt(btn.dataset[dataKey], 10) > max);
        });
        setValue(Math.min(parseInt(rangeInput.value, 10), max));
      },
    };
  }

  // Reusable area slider & text input (in sqm), limited to the training range
  function setupAreaControl({ inputId, rangeId, labelPrefix }) {
    const textInput = byId(inputId);
    const rangeInput = byId(rangeId);
    let min = Number(rangeInput.min);
    let max = Number(rangeInput.max);

    function setValue(raw) {
      const clamped = Math.max(min, Math.min(max, raw));
      textInput.value = clamped.toLocaleString('en-US');
      rangeInput.value = clamped;
    }

    rangeInput.addEventListener('input', (e) => setValue(parseInt(e.target.value, 10)));
    textInput.addEventListener('change', (e) => {
      setValue(parseInt(e.target.value.replace(/[^0-9]/g, ''), 10) || min);
    });

    return {
      setLimits([newMin, newMax]) {
        min = newMin;
        max = newMax;
        rangeInput.min = min;
        rangeInput.max = max;
        byId(`${labelPrefix}MinLabel`).textContent = formatArea(min);
        byId(`${labelPrefix}MidLabel`).textContent = formatArea(Math.round((min + max) / 2));
        byId(`${labelPrefix}MaxLabel`).textContent = formatArea(max);
        setValue(parseInt(textInput.value.replace(/[^0-9]/g, ''), 10) || min);
      },
    };
  }

  const bedrooms = setupStepper({
    buttonSelector: '.bed-btn', dataKey: 'beds', rangeId: 'bedRange', displayId: 'bedDisplay', singular: 'Bed', plural: 'Beds',
  });
  setupStepper({
    buttonSelector: '.bath-btn', dataKey: 'baths', rangeId: 'bathRange', displayId: 'bathDisplay', singular: 'Bath', plural: 'Baths',
  });
  const floor = setupAreaControl({ inputId: 'floorInput', rangeId: 'floorRange', labelPrefix: 'floor' });
  const land = setupAreaControl({ inputId: 'lotInput', rangeId: 'lotRange', labelPrefix: 'lot' });

  // Result elements
  const heroPrice = byId('heroEstimatedPrice');
  const predictionStatus = byId('predictionStatus');
  const intervalRange = byId('intervalRange');
  const baselineLow = byId('baselineLowDisplay');
  const baselineHigh = byId('baselineHighDisplay');
  const baselineBar = byId('baselineBar');
  const baselineMarker = byId('baselineMarker');
  const pricePerSqm = byId('priceSqFtDisplay');
  const rent = byId('rentalYieldDisplay');
  const comparablesGrid = byId('comparablesGrid');
  const modelEstimatesGrid = byId('modelEstimatesGrid');
  const recalculateBtn = byId('recalculateBtn');
  const buttonLabel = recalculateBtn.querySelector('span:last-child');

  const peso = new Intl.NumberFormat('en-PH', { style: 'currency', currency: 'PHP', maximumFractionDigits: 0 });
  const pesoMillions = (value) => `₱${(value / 1e6).toFixed(2)}M`;

  function showHint(container, text) {
    if (!container) return; // The section is turned off in settings.txt
    const hint = document.createElement('p');
    hint.className = 'font-body-md text-sm text-secondary';
    hint.textContent = text;
    container.replaceChildren(hint);
  }

  function resetResults() {
    [heroPrice, intervalRange, baselineLow, baselineHigh, pricePerSqm, rent].forEach((el) => { el.textContent = '—'; });
    baselineBar.classList.add('hidden');
    baselineMarker.classList.add('hidden');
    predictionStatus.textContent = '';
    predictionStatus.classList.remove('text-crimson');
    showHint(comparablesGrid, 'Calculate a value to see similar listings.');
    showHint(modelEstimatesGrid, "Calculate a value to compare each model's estimate.");
  }

  // Property type switches which fields the model uses, and their limits
  let propertyType = CONDO;
  const typeButtons = Array.from(document.querySelectorAll('.type-btn'));

  function applyPropertyType(type) {
    propertyType = type;
    const limits = LIMITS[type];
    const isCondo = type === CONDO;
    setActiveButton(typeButtons.find((btn) => btn.dataset.type === type), typeButtons);
    byId('bathField').classList.toggle('hidden', !isCondo);
    byId('lotField').classList.toggle('hidden', isCondo);
    bedrooms.setMax(limits.Bedrooms[1]);
    floor.setLimits(limits['Floor_area (sqm)']);
    if (!isCondo) land.setLimits(limits['Land_area (sqm)']);
    resetResults();
  }

  typeButtons.forEach((btn) => btn.addEventListener('click', () => applyPropertyType(btn.dataset.type)));

  function areaValue(id) {
    return Number(byId(id).value.replace(/,/g, '').trim());
  }

  function buildRequest() {
    const data = {
      Property_Type: propertyType,
      Bedrooms: Number(byId('bedRange').value),
      'Floor_area (sqm)': areaValue('floorInput'),
    };
    if (propertyType === CONDO) data.Bath = Number(byId('bathRange').value);
    else data['Land_area (sqm)'] = areaValue('lotInput');
    return data;
  }

  function renderBaseline(prediction, [low, high]) {
    baselineLow.textContent = peso.format(low);
    baselineHigh.textContent = peso.format(high);
    // Scale the bar so that both the typical range and the estimate are visible
    const scale = Math.max(high, prediction) * 1.15;
    baselineBar.style.left = `${(low / scale) * 100}%`;
    baselineBar.style.width = `${((high - low) / scale) * 100}%`;
    baselineMarker.style.left = `${(prediction / scale) * 100}%`;
    baselineBar.classList.remove('hidden');
    baselineMarker.classList.remove('hidden');
  }

  function comparableCard(item) {
    const card = document.createElement('a');
    card.href = item.link;
    card.target = '_blank';
    card.rel = 'noopener noreferrer';
    card.className = 'bg-surface-container-lowest rounded-2xl shadow-sm border border-outline-variant p-space-md flex flex-col gap-1 hover:border-picton-blue transition-colors';

    const price = document.createElement('span');
    price.className = 'font-headline-sm text-lg text-primary font-bold font-label-data';
    price.textContent = peso.format(item.price);

    const title = document.createElement('p');
    title.className = 'font-body-md text-sm text-primary font-semibold truncate';
    title.textContent = item.title;
    title.title = item.title;

    const location = document.createElement('p');
    location.className = 'font-body-md text-sm text-secondary truncate';
    location.textContent = item.location;

    const details = [`${item.beds} ${item.beds === 1 ? 'Bed' : 'Beds'}`];
    if (item.baths) details.push(`${item.baths} ${item.baths === 1 ? 'Bath' : 'Baths'}`);
    details.push(`${item.floor_area} sqm floor`);
    if (item.land_area) details.push(`${item.land_area} sqm land`);
    const meta = document.createElement('p');
    meta.className = 'text-secondary font-label-data text-xs pt-1';
    meta.textContent = details.join(' • ');

    card.append(price, title, location, meta);
    return card;
  }

  function modelCard(item, selectedEstimate) {
    const card = document.createElement('div');
    card.className = `bg-surface-container-lowest rounded-2xl shadow-sm border p-space-md flex flex-col gap-1 ${item.selected ? 'border-primary' : 'border-outline-variant'}`;

    const name = document.createElement('p');
    name.className = 'font-body-md text-sm text-secondary font-semibold';
    name.textContent = item.name;

    const price = document.createElement('span');
    price.className = 'font-headline-sm text-lg text-primary font-bold font-label-data';
    price.textContent = peso.format(item.estimate);

    const note = document.createElement('p');
    note.className = 'font-label-data text-xs text-secondary';
    const percent = ((item.estimate - selectedEstimate) / selectedEstimate) * 100;
    note.textContent = item.selected
      ? 'Selected model'
      : `${percent >= 0 ? '+' : ''}${percent.toFixed(1)}% vs selected model`;

    card.append(name, price, note);
    return card;
  }

  recalculateBtn.addEventListener('click', async () => {
    recalculateBtn.disabled = true;
    recalculateBtn.setAttribute('aria-busy', 'true');
    if (buttonLabel) buttonLabel.textContent = 'Calculating...';
    predictionStatus.classList.remove('text-crimson');
    predictionStatus.textContent = 'Calculating your estimate...';
    heroPrice.classList.add('opacity-40');

    try {
      const response = await fetch('/predict', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(buildRequest()),
      });
      let result;
      try {
        result = await response.json();
      } catch {
        throw new Error('The server returned an invalid response.');
      }

      if (!response.ok) {
        throw new Error(result.error || 'The estimate could not be calculated.');
      }
      if (typeof result.prediction !== 'number' || !Number.isFinite(result.prediction)) {
        throw new Error('The server returned an invalid estimate.');
      }

      heroPrice.textContent = peso.format(result.prediction);
      intervalRange.textContent = `${pesoMillions(result.estimated_range[0])} – ${pesoMillions(result.estimated_range[1])}`;
      renderBaseline(result.prediction, result.market_baseline);
      pricePerSqm.textContent = peso.format(result.price_per_sqm);
      rent.textContent = `${peso.format(result.monthly_rent)}/mo`;
      if (comparablesGrid) comparablesGrid.replaceChildren(...result.comparables.map(comparableCard));
      if (modelEstimatesGrid) {
        modelEstimatesGrid.replaceChildren(
          ...result.model_estimates.map((item) => modelCard(item, result.prediction)),
        );
      }
      predictionStatus.textContent = 'Model-generated estimate; actual market prices may vary.';
    } catch (error) {
      predictionStatus.classList.add('text-crimson');
      predictionStatus.textContent = error.message || 'Unable to calculate an estimate. Please try again.';
    } finally {
      recalculateBtn.disabled = false;
      recalculateBtn.removeAttribute('aria-busy');
      if (buttonLabel) buttonLabel.textContent = 'Calculate Value';
      heroPrice.classList.remove('opacity-40');
    }
  });

  applyPropertyType(CONDO);
})();
