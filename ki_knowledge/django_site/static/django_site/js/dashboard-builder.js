document.addEventListener('DOMContentLoaded', () => {
  function initDashboardBuilder() {
    const root = document.querySelector('[data-dashboard-builder]');
    if (!root) return;

    const grid = root.querySelector('#layout-grid');
    const stash = root.querySelector('#unused-stash');
    const orderInput = document.getElementById('widget-order');
    const sizesInput = document.getElementById('widget-sizes');
    const saveOrderForm = document.getElementById('save-order-form');
    const configNode = document.getElementById('dashboard-builder-config');
    const config = configNode ? JSON.parse(configNode.textContent) : {};
    const saveUrl = saveOrderForm.dataset.saveUrl || '/settings/layout/builder/';
    const dragState = { type: null, widgetId: null };

    if (!grid || !stash || !orderInput || !sizesInput || !saveOrderForm) return;

    function currentOrder() {
      return Array.from(grid.querySelectorAll('.db-widget-card')).map((card) => card.dataset.widgetId);
    }

    function currentWidths() {
      const widths = {};
      document.querySelectorAll('.db-width-select').forEach((select) => {
        widths[select.dataset.widgetId] = Number(select.value || 6);
      });
      grid.querySelectorAll('.db-widget-card[data-resizable="false"]').forEach((card) => {
        widths[card.dataset.widgetId] = Number(card.style.getPropertyValue('--w') || 6);
      });
      return widths;
    }

    function syncOrderInput() {
      orderInput.value = JSON.stringify(currentOrder());
      sizesInput.value = JSON.stringify(currentWidths());
    }

    async function submitWidgetAction(form, url = null) {
      const response = await fetch(url || form.action, {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest' },
        body: new FormData(form),
        credentials: 'same-origin',
      });
      if (!response.ok) {
        window.location.reload();
        return null;
      }
      return response.json();
    }

    function submitSaveOrder() {
      syncOrderInput();
      submitWidgetAction(saveOrderForm, saveUrl);
    }

    function onDragStart(event) {
      const card = event.currentTarget;
      dragState.widgetId = card.dataset.widgetId;
      dragState.type = card.closest('#unused-stash') ? 'unused' : 'grid';
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', dragState.widgetId);
      card.classList.add('dragging');
    }

    function onDragEnd(event) {
      event.currentTarget.classList.remove('dragging');
      grid.classList.remove('is-over');
      stash.querySelectorAll('.db-unused-item').forEach((item) => item.classList.remove('drop-target'));
    }

    function bindWidgetCard(card) {
      card.setAttribute('draggable', 'true');
      card.addEventListener('dragstart', onDragStart);
      card.addEventListener('dragend', onDragEnd);

      const widthSelect = card.querySelector('.db-width-select');
      if (widthSelect) {
        widthSelect.addEventListener('change', (event) => {
          card.style.setProperty('--w', Number(event.target.value || widthSelect.value || 6));
          submitSaveOrder();
        });
      }
    }

    function bindUnusedItem(item) {
      item.setAttribute('draggable', 'true');
      item.addEventListener('dragstart', onDragStart);
      item.addEventListener('dragend', onDragEnd);
    }

    function moveWidgetToGrid(widgetId) {
      const currentIds = currentOrder();
      if (currentIds.includes(widgetId)) {
        syncOrderInput();
        return;
      }
      const widgetItem = stash.querySelector(`.db-unused-item[data-widget-id="${widgetId}"]`);
      if (!widgetItem) return;
      const form = widgetItem.querySelector('form');
      if (!form) return;
      form.requestSubmit();
    }

    function arrangeGridFromDrop(event) {
      event.preventDefault();
      const widgetId = event.dataTransfer.getData('text/plain') || dragState.widgetId;
      if (!widgetId) return;
      const cards = Array.from(grid.querySelectorAll('.db-widget-card'));
      const sourceCard = cards.find((card) => card.dataset.widgetId === widgetId);
      if (!sourceCard) {
        moveWidgetToGrid(widgetId);
        return;
      }
      const beforeTarget = event.target.closest('.db-widget-card');
      if (beforeTarget) {
        const targetIndex = cards.indexOf(beforeTarget);
        const current = cards.indexOf(sourceCard);
        const nextCards = [...cards];
        nextCards.splice(current, 1);
        nextCards.splice(targetIndex, 0, sourceCard);
        const fragment = document.createDocumentFragment();
        nextCards.forEach((card) => fragment.appendChild(card));
        grid.appendChild(fragment);
      }
      submitSaveOrder();
    }

    grid.querySelectorAll('.db-widget-card').forEach(bindWidgetCard);
    stash.querySelectorAll('.db-unused-item').forEach(bindUnusedItem);

    grid.addEventListener('dragover', (event) => {
      event.preventDefault();
      grid.classList.add('is-over');
    });
    grid.addEventListener('drop', arrangeGridFromDrop);

    stash.addEventListener('dragover', (event) => {
      event.preventDefault();
      stash.querySelectorAll('.db-unused-item').forEach((item) => item.classList.add('drop-target'));
    });
    stash.addEventListener('dragleave', () => {
      stash.querySelectorAll('.db-unused-item').forEach((item) => item.classList.remove('drop-target'));
    });
    stash.addEventListener('drop', (event) => {
      event.preventDefault();
      const widgetId = event.dataTransfer.getData('text/plain') || dragState.widgetId;
      if (!widgetId) return;
      const card = grid.querySelector(`.db-widget-card[data-widget-id="${widgetId}"]`);
      const form = card ? card.querySelector('form') : null;
      if (!form) return;
      form.requestSubmit();
    });

    syncOrderInput();
  }

  initDashboardBuilder();
  document.body.addEventListener('htmx:afterSwap', (event) => {
    if (event.target && event.target.id === 'dashboard-builder-shell') {
      initDashboardBuilder();
    }
  });
});
