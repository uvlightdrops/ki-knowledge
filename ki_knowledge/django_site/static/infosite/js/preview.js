document.addEventListener('DOMContentLoaded', function () {
  const select = document.getElementById('preview-file-select');
  const fileButtons = Array.from(document.querySelectorAll('.infosite-file-row[data-preview-url]'));
  const previewContent = document.getElementById('preview-content');
  const previewFileName = document.getElementById('preview-file-name');
  if (!select || !previewContent || !previewFileName || fileButtons.length === 0) return;

  function setActiveButton(activeButton) {
    fileButtons.forEach(function (button) {
      button.classList.toggle('is-active', button === activeButton);
    });
  }
  async function loadPreview(button) {
    setActiveButton(button);
    previewFileName.textContent = button.dataset.filePath;
    previewContent.value = 'Lade Datei...';
    try {
      const response = await fetch(button.dataset.previewUrl);
      const data = await response.json();
      if (!response.ok || data.error) {
        previewContent.value = data.error || 'Datei konnte nicht geladen werden.';
        return;
      }
      previewContent.value = data.content || '';
    } catch (error) {
      previewContent.value = 'Datei konnte nicht geladen werden.';
    }
  }
  fileButtons.forEach(function (button) {
    button.addEventListener('click', function () {
      select.value = encodeURIComponent(button.dataset.filePath);
      loadPreview(button);
    });
  });
  select.addEventListener('change', function () {
    if (!this.value) return;
    const decodedPath = decodeURIComponent(this.value);
    const target = fileButtons.find(button => button.dataset.filePath === decodedPath);
    if (target) {
      target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      loadPreview(target);
    }
  });
  loadPreview(fileButtons[0]);
});
