(() => {
  const payloadNode = document.getElementById("widget-preview-payload");
  const previewEl = document.getElementById("widget-preview");
  const itemButtons = document.querySelectorAll(".widget-list-item");
  if (!payloadNode || !previewEl || !itemButtons.length) {
    return;
  }

  const widgetPayload = JSON.parse(payloadNode.textContent || "[]");

  function renderPreview(widgetId) {
    const item = widgetPayload.find((entry) => entry.widget_id === widgetId) || widgetPayload[0];
    if (!item) {
      return;
    }

    const label = document.querySelector(`.widget-list-item[data-widget-id="${item.widget_id}"] strong`)?.textContent || item.widget_id;
    const rows = item.rows || [];
    const stats = item.stats || [];
    const links = item.links || [];
    const rowMarkup = rows.length
      ? `<table class="widget-preview-table"><tbody>${rows.map((row) => `<tr><th>${row.label}</th><td>${row.value}</td></tr>`).join("")}</tbody></table>`
      : "";
    const statMarkup = stats.length
      ? `<div class="widget-preview-stats">${stats.map((stat) => `<div class="db-preview-metric"><strong>${stat.label}:</strong> ${stat.value}</div>`).join("")}</div>`
      : "";
    const linkMarkup = links.length
      ? `<div class="widget-preview-links">${links.map((link) => `<a class="chip" href="${link.url}">${link.label}</a>`).join("")}</div>`
      : "";

    previewEl.innerHTML = `
      <div class="widget-preview-card">
        <div class="widget-preview-head">
          <span class="widget-preview-title">${label}</span>
          <span class="chip">${item.widget_id}</span>
        </div>
        <div class="widget-preview-body">
          ${statMarkup}
          ${rowMarkup}
          ${linkMarkup}
          <p>${item.description}</p>
        </div>
      </div>
    `;

    itemButtons.forEach((button) => {
      button.classList.toggle("is-active", button.dataset.widgetId === item.widget_id);
    });
  }

  itemButtons.forEach((button) => {
    button.addEventListener("click", () => renderPreview(button.dataset.widgetId));
  });

  if (widgetPayload.length) {
    renderPreview(widgetPayload[0].widget_id);
  }
})();
