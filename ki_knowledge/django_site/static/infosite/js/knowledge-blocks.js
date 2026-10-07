document.addEventListener('DOMContentLoaded', function () {
  const actions = document.getElementById('knowledge-block-actions');
  const config = actions.dataset;
  const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
    document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];

  actions.querySelector('[data-publish-blocks]').addEventListener('click', async function (event) {
    if (!confirm('Publish all extracted blocks to the Knowledge Store?')) return;
    const btn = event.currentTarget;
    const originalText = btn.textContent;
    btn.disabled = true;
    btn.textContent = '⏳ Publishing...';
    try {
      const response = await fetch(config.publishUrl, {
        method: 'POST',
        headers: {
          'X-CSRFToken': csrftoken,
          'Content-Type': 'application/json',
        },
      });
      const data = await response.json();
      if (response.ok) {
        alert(`✅ Published ${data.blocks_stored} blocks from ${data.files_processed} files!\n\nSource: ${data.source_id}`);
        setTimeout(() => location.reload(), 1000);
      } else {
        alert(`❌ Error: ${data.error}`);
      }
    } catch (error) {
      alert(`❌ Failed to publish: ${error.message}`);
    } finally {
      btn.disabled = false;
      btn.textContent = originalText;
    }
  });
  actions.querySelector('[data-export-blocks]').addEventListener('click', function () {
    const data = {
      project: config.projectTitle,
      domain: config.domain,
      working_title: config.workingTitle,
      stats: JSON.parse(document.getElementById('knowledge-block-stats').textContent),
      exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `knowledge-blocks-${config.projectId}.json`;
    a.click();
    URL.revokeObjectURL(url);
  });
  document.querySelectorAll('[data-file-section]').forEach(function (section) {
    const blocks = section.querySelectorAll('.block-item');
    section.querySelector('[data-expand-blocks]')?.addEventListener('click', function (event) {
      event.preventDefault();
      blocks.forEach(block => block.open = true);
    });
    section.querySelector('[data-collapse-blocks]')?.addEventListener('click', function (event) {
      event.preventDefault();
      blocks.forEach(block => block.open = false);
    });
  });
});
