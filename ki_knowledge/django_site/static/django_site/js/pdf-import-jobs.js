(() => {
  const config = document.getElementById("pdf-job-refresh-config").dataset;
  const { endpoint, domain, status } = config;
  let current = config.current;
  window.setInterval(async () => {
    try {
      const response = await fetch(`${endpoint}?domain=${encodeURIComponent(domain)}&status=${encodeURIComponent(status)}`, {
        headers: { Accept: "application/json" }
      });
      if (!response.ok) return;
      const data = await response.json();
      const worker = data.worker || {};
      const next = `${data.summary.pending}:${data.summary.processing}:${data.summary.done}:${data.summary.failed}:${worker.token || ""}:${worker.status || ""}`;
      if (next !== current || data.summary.processing > 0 || ["starting", "running"].includes(worker.status)) {
        current = next;
        window.location.reload();
      }
    } catch (error) {
      console.error("Failed to refresh PDF job status", error);
    }
  }, 10000);
})();
