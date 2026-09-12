document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-widget-shell-builder]');
  if (!root) return;

  const form = root.querySelector('#shell-form');
  const widgetIdInput = root.querySelector('#shell-widget-id');
  const statsList = root.querySelector('#stats-list');
  const linksList = root.querySelector('#links-list');
  const rowsList = root.querySelector('#rows-list');
  const payloadInput = root.querySelector('#shell-payload');
  const presetList = root.querySelector('#preset-list');
  const shellSizeChip = root.querySelector('#shell-size-chip');
  const widgetIdDisplay = root.querySelector('#shell-widget-id-display');
  const csrfTokenInput = form.querySelector('input[name="csrfmiddlewaretoken"]');
  const saveButton = root.querySelector('#shell-save-button');
  const livePreview = {
    box: document.getElementById('shell-live-preview-box'),
    label: document.getElementById('shell-live-preview-label'),
    meta: document.getElementById('shell-live-preview-meta'),
    description: document.getElementById('shell-live-preview-description'),
  };
  let presetState = {};
  const config = window.widgetShellBuilderConfig || {};
  let activeWidgetId = new URLSearchParams(window.location.search).get('widget_id') || config.activePresetId || '';
  const savedFlag = new URLSearchParams(window.location.search).get('saved');

  function addEntry(container, left, right, placeholderLeft, placeholderRight) {
    const row = document.createElement('div');
    row.className = 'shell-entry';
    row.innerHTML = `
      <input type="text" placeholder="${placeholderLeft}" value="${left || ''}">
      <input type="text" placeholder="${placeholderRight}" value="${right || ''}">
      <button type="button">Remove</button>
    `;
    row.querySelector('button').addEventListener('click', () => {
      row.remove();
      render();
    });
    row.querySelectorAll('input').forEach((input) => input.addEventListener('input', render));
    container.appendChild(row);
    return row;
  }

  function readEntries(container) {
    return Array.from(container.querySelectorAll('.shell-entry'))
      .map((row) => {
        const inputs = row.querySelectorAll('input');
        return { left: inputs[0]?.value || '', right: inputs[1]?.value || '' };
      })
      .filter((item) => item.left || item.right);
  }

  function render() {
    const data = Object.fromEntries(new FormData(form).entries());
    if (!form || !livePreview.box) return;
    const width = Math.max(Number(data.width || 1), 1);
    const height = Math.max(Number(data.height || 1), 1);
    livePreview.box.style.setProperty('--shell-live-width', String(width));
    livePreview.box.style.setProperty('--shell-live-height', String(height));
    livePreview.box.style.minHeight = `calc(${height} * var(--shell-grid-row-height) + ${(height - 1) * 10}px)`;
    if (livePreview.label) livePreview.label.textContent = data.label || 'Widget';
    if (livePreview.meta) livePreview.meta.textContent = `${data.area || 'custom'} · ${data.category || 'overview'} · ${width}x${height}`;
    if (livePreview.description) livePreview.description.textContent = data.description || 'Select a preset to preview it here.';
  }

  function clearEntries(container) {
    container.innerHTML = '';
  }

  function setFormFromPreset(preset) {
    presetState = JSON.parse(JSON.stringify(preset));
    widgetIdInput.value = preset.widget_id || '';
    if (widgetIdDisplay) widgetIdDisplay.textContent = preset.widget_id || '—';
    form.label.value = preset.label || '';
    form.description.value = preset.description || '';
    form.area.value = preset.area || 'custom';
    form.category.value = preset.category || 'overview';
    form.width.value = String(preset.width || form.width.value || '6');
    form.height.value = String(preset.height || form.height.value || '1');
    clearEntries(statsList);
    clearEntries(linksList);
    clearEntries(rowsList);
    (preset.stats || []).forEach((item) => addEntry(statsList, item.label, item.value, 'Label', 'Value'));
    (preset.links || []).forEach((item) => addEntry(linksList, item.label, item.url, 'Label', 'URL'));
    (preset.rows || []).forEach((item) => addEntry(rowsList, item.label, item.value, 'Label', 'Value'));
  }

  async function loadPreset(widgetId) {
    const template = config.presetJsonUrlTemplate || '';
    const url = template.replace('PRESET_ID', encodeURIComponent(widgetId));
    const response = await fetch(url, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new Error(`Failed to load preset ${widgetId}`);
    const preset = await response.json();
    setFormFromPreset(preset);
    activeWidgetId = widgetId;
    widgetIdInput.value = widgetId;
    if (widgetIdDisplay) widgetIdDisplay.textContent = widgetId || '—';
    syncHiddenPayload();
    render();
    renderChooserSize();
  }

  async function loadCurrentWidget() {
    if (!activeWidgetId) return;
    await loadPreset(activeWidgetId);
    widgetIdInput.value = activeWidgetId;
  }

  function syncHiddenPayload() {
    const payload = {
      widget_id: widgetIdInput.value || '',
      label: form.label.value || '',
      description: form.description.value || '',
      area: form.area.value || '',
      category: form.category.value || '',
      width: form.width.value || '',
      height: form.height.value || '',
      stats: readEntries(statsList).map((item) => ({ label: item.left, value: item.right })),
      links: readEntries(linksList).map((item) => ({ label: item.left, url: item.right })),
      rows: readEntries(rowsList).map((item) => ({ label: item.left, value: item.right })),
    };
    const serialized = JSON.stringify(payload);
    if (payloadInput) payloadInput.value = serialized;
    form.dataset.payload = serialized;
  }

  function renderChooserSize() {
    if (!shellSizeChip) return;
    const width = form.width.value || '6';
    const height = form.height.value || '1';
    shellSizeChip.textContent = `${width}x${height}`;
  }

  async function saveShell(event) {
    event.preventDefault();
    if (!widgetIdInput.value && activeWidgetId) {
      widgetIdInput.value = activeWidgetId;
    }
    syncHiddenPayload();
    const serialized = payloadInput ? payloadInput.value : form.dataset.payload || '';
    const response = await fetch(config.saveUrl || form.action, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
        'X-CSRFToken': csrfTokenInput ? csrfTokenInput.value : '',
      },
      body: serialized,
    });
    if (!response.ok) throw new Error('Failed to save shell');
    const savedPreset = await response.json();
    activeWidgetId = savedPreset.widget_id || activeWidgetId;
    setFormFromPreset(savedPreset);
    syncHiddenPayload();
    renderChooserSize();
    render();
  }

  function wireAdd(buttonId, container, placeholderLeft, placeholderRight) {
    const button = root.querySelector(`#${buttonId}`);
    if (!button) return;
    button.addEventListener('click', (event) => {
      event.preventDefault();
      addEntry(container, '', '', placeholderLeft, placeholderRight);
      render();
    });
  }

  wireAdd('add-stat', statsList, 'Label', 'Value');
  wireAdd('add-link', linksList, 'Label', 'URL');
  wireAdd('add-row', rowsList, 'Label', 'Value');

  if (presetList) {
    presetList.addEventListener('click', async (event) => {
      const button = event.target.closest('[data-widget-id]');
      if (!button) return;
      const widgetId = button.dataset.widgetId;
      presetList.querySelectorAll('.shell-item').forEach((item) => item.classList.remove('is-active'));
      button.classList.add('is-active');
      await loadPreset(widgetId);
      widgetIdInput.value = widgetId;
    });
  }

  if (activeWidgetId) {
    loadCurrentWidget().catch(() => {});
  } else if (config.activePreset) {
    setFormFromPreset(config.activePreset);
    syncHiddenPayload();
    renderChooserSize();
    render();
  }

  if (savedFlag) {
    // noop: presence of the flag tells us the POST reached the server
  }

  if (saveButton) {
    saveButton.addEventListener('click', (event) => {
      saveShell(event).catch(() => {});
    });
  }

  form.addEventListener('input', render);
  form.addEventListener('change', render);
  form.addEventListener('input', syncHiddenPayload);
  form.addEventListener('change', syncHiddenPayload);
  form.addEventListener('input', renderChooserSize);
  form.addEventListener('change', renderChooserSize);
  syncHiddenPayload();
  renderChooserSize();
  render();
});
