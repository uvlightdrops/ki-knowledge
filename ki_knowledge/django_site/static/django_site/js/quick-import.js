// Drag & drop + auto-submit for the quick import widget (event delegation, works for swapped fragments too).
(function () {
  const zoneOf = (event) => event.target.closest && event.target.closest('[data-quick-import-drop]');
  ['dragenter', 'dragover'].forEach((type) => document.addEventListener(type, (event) => {
    const zone = zoneOf(event);
    if (!zone) return;
    event.preventDefault();
    zone.classList.add('qi-drop--over');
  }));
  document.addEventListener('dragleave', (event) => {
    const zone = zoneOf(event);
    if (zone && !zone.contains(event.relatedTarget)) zone.classList.remove('qi-drop--over');
  });
  document.addEventListener('drop', (event) => {
    const zone = zoneOf(event);
    if (!zone) return;
    event.preventDefault();
    zone.classList.remove('qi-drop--over');
    if (!event.dataTransfer || !event.dataTransfer.files.length) return;
    zone.querySelector('input[type=file]').files = event.dataTransfer.files;
    zone.classList.add('qi-drop--ready');
  });
  document.addEventListener('change', (event) => {
    const zone = zoneOf(event);
    if (zone && event.target.type === 'file' && event.target.files.length) zone.classList.add('qi-drop--ready');
  });
})();
