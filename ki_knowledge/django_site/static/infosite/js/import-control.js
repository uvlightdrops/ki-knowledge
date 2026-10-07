document.addEventListener('DOMContentLoaded', function() {
  const selectAll = document.getElementById('select-all');
  const checkboxes = document.querySelectorAll('.file-checkbox');
  const selectedCount = document.getElementById('selected-count');
  const rows = Array.from(document.querySelectorAll('.doc-row'));
  const previewTitle = document.getElementById('preview-title');
  const previewBody = document.getElementById('preview-body');

  function updateCount() {
    const count = document.querySelectorAll('.file-checkbox:checked').length;
    selectedCount.textContent = count + ' Datei' + (count !== 1 ? 'en' : '') + ' ausgewählt';
  }
  if (selectAll) {
    selectAll.addEventListener('change', function() {
      checkboxes.forEach(cb => cb.checked = this.checked);
      updateCount();
    });
  }
  checkboxes.forEach(cb => cb.addEventListener('change', updateCount));

  let activeRow = null;
  let hoverTimer = null;
  const previewCache = new Map();
  function setActiveRow(row) {
    if (!row) return;
    if (activeRow) activeRow.classList.remove('active-preview');
    activeRow = row;
    activeRow.classList.add('active-preview');
    loadPreview(row);
  }
  async function loadPreview(row) {
    const url = row.dataset.previewUrl;
    previewTitle.textContent = row.dataset.name;
    if (previewCache.has(url)) {
      renderPreview(previewCache.get(url));
      return;
    }
    previewBody.innerHTML = '<div class="preview-empty">⏳ Lade Vorschau…</div>';
    try {
      const resp = await fetch(url);
      const data = await resp.json();
      previewCache.set(url, data);
      renderPreview(data);
    } catch (e) {
      previewBody.innerHTML = '<div class="preview-empty">⚠️ Vorschau konnte nicht geladen werden.</div>';
    }
  }
  function renderPreview(data) {
    if (data.error) {
      previewBody.innerHTML = '<div class="preview-empty"></div>';
      previewBody.firstElementChild.textContent = '⚠️ ' + data.error;
      return;
    }
    const content = (data.content || '').replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const truncatedNote = data.truncated ? '<p class="muted">… gekürzt</p>' : '';
    previewBody.innerHTML = '<pre>' + content + '</pre>' + truncatedNote;
  }
  rows.forEach((row, idx) => {
    row.addEventListener('mouseenter', function() {
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => setActiveRow(row), 150);
    });
    row.addEventListener('mouseleave', () => clearTimeout(hoverTimer));
    row.addEventListener('click', function(e) {
      if (e.target.tagName === 'INPUT') return;
      setActiveRow(row);
    });
    row.addEventListener('focus', () => setActiveRow(row));
    row.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        const next = rows[idx + 1];
        if (next) next.focus();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        const prev = rows[idx - 1];
        if (prev) prev.focus();
      }
    });
  });
});
