document.addEventListener('DOMContentLoaded', () => {
  const root = document.querySelector('[data-widget-shell-builder]');
  if (!root) return;

  const form = root.querySelector('#shell-form');
  const widgetIdInput = root.querySelector('#shell-widget-id');
  const previewLabel = root.querySelector('#preview-label');
  const previewArea = root.querySelector('#preview-area');
  const previewDescription = root.querySelector('#preview-description');
  const previewStats = root.querySelector('#preview-stats');
  const previewLinks = root.querySelector('#preview-links');
  const previewRows = root.querySelector('#preview-rows');
  const statsList = root.querySelector('#stats-list');
  const linksList = root.querySelector('#links-list');
  const rowsList = root.querySelector('#rows-list');
  const payloadInput = root.querySelector('#shell-payload');
  const presetList = root.querySelector('#preset-list');
  let presetState = {};
  const config = window.widgetShellBuilderConfig || {};

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
    previewLabel.textContent = data.label || 'Widget';
    previewArea.textContent = data.area || 'custom';
    previewDescription.textContent = data.description || '';
    const stats = readEntries(statsList);
    const links = readEntries(linksList);
    const rows = readEntries(rowsList);
    previewStats.innerHTML = stats.map((item) => `<div class="shell-metric"><strong>${item.left || 'Stat'}:</strong> ${item.right || ''}</div>`).join('');
    previewLinks.innerHTML = links.map((item) => `<a class="chip" href="${item.right || '#'}">${item.left || 'Link'}</a>`).join('');
    previewRows.innerHTML = rows.length ? `<table class="widget-preview-table"><tbody>${rows.map((item) => `<tr><th>${item.left || 'Field'}</th><td>${item.right || ''}</td></tr>`).join('')}</tbody></table>` : '';
  }

  function clearEntries(container) {
    container.innerHTML = '';
  }

  function setFormFromPreset(preset) {
    presetState = JSON.parse(JSON.stringify(preset));
    widgetIdInput.value = preset.widget_id || '';
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
    syncHiddenPayload();
    render();
    renderChooserSize();
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
    const chooser = root.querySelector('.shell-widget-chooser .chip');
    if (!chooser) return;
    const width = form.width.value || '6';
    const height = form.height.value || '1';
    chooser.textContent = `${width}x${height}`;
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

  form.addEventListener('input', render);
  form.addEventListener('input', syncHiddenPayload);
  form.addEventListener('input', renderChooserSize);
  syncHiddenPayload();
  renderChooserSize();
});
