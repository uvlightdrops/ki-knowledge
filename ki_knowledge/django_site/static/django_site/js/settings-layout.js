(() => {
  const layoutSizeMap = { compact: 'compact', balanced: 'balanced', wide: 'wide', full: 'full' };
  document.querySelectorAll('[data-layout-control]').forEach((select) => {
    const box = select.dataset.layoutControl;
    const storageKey = `kicli-layout-box-${box}`;
    const restore = localStorage.getItem(storageKey) || select.value || 'balanced';
    const safe = layoutSizeMap[restore] || 'balanced';
    select.value = safe;
    localStorage.setItem(storageKey, safe);
    select.addEventListener('change', (event) => {
      const value = layoutSizeMap[event.target.value] || 'balanced';
      localStorage.setItem(storageKey, value);
      event.target.value = value;
    });
  });
})();
