class DocumentBrowser {
  constructor(documents) {
    this.documents = documents;
    this.currentDoc = null;
    this.cache = {};
    this.filteredDocs = documents;
    this.setupEventListeners();
  }

  setupEventListeners() {
    const listEl = document.getElementById('documentList');
    const searchEl = document.getElementById('searchInput');
    listEl.addEventListener('click', (e) => {
      const row = e.target.closest('.doc-row');
      if (row && !e.target.classList.contains('action-btn')) {
        this.selectDocument(row.dataset.docId);
      }
    });
    searchEl.addEventListener('input', (e) => {
      this.filterDocuments(e.target.value.toLowerCase());
    });
    listEl.addEventListener('click', (e) => {
      if (e.target.classList.contains('download-btn')) {
        e.stopPropagation();
        const doc = this.documents.find(d => d.id === e.target.dataset.docId);
        if (doc) this.downloadDocument(doc);
      }
      if (e.target.classList.contains('view-btn')) {
        e.stopPropagation();
        const doc = this.documents.find(d => d.id === e.target.dataset.docId);
        if (doc) window.open(doc.url, '_blank');
      }
    });
  }

  filterDocuments(term) {
    this.filteredDocs = this.documents.filter(d => d.name.toLowerCase().includes(term));
    this.render();
  }

  render() {
    const listEl = document.getElementById('documentList');
    if (this.filteredDocs.length === 0) {
      listEl.innerHTML = '<div class="document-list-empty">No matching documents</div>';
      return;
    }
    // Document names and paths are data, not HTML.
    listEl.replaceChildren(...this.filteredDocs.map(doc => {
      const row = document.createElement('div');
      row.className = 'doc-row';
      row.dataset.docId = doc.id;
      row.dataset.docType = doc.type;
      row.dataset.docPath = doc.path;
      row.innerHTML = `
        <div class="doc-icon"></div>
        <div class="doc-name"></div>
        <div class="doc-size"></div>
        <div class="doc-actions">
          <button class="action-btn download-btn" title="Download">⬇️</button>
          <button class="action-btn view-btn" title="View fullscreen">🔗</button>
        </div>`;
      row.querySelector('.doc-icon').textContent = doc.type === 'pdf' ? '📕' : '📝';
      row.querySelector('.doc-name').textContent = doc.name;
      row.querySelector('.doc-name').title = doc.name;
      row.querySelector('.doc-size').textContent = doc.size_display;
      row.querySelectorAll('.action-btn').forEach(button => button.dataset.docId = doc.id);
      return row;
    }));
    // Delegated list listeners remain attached when its children change.
  }

  selectDocument(docId) {
    const doc = this.documents.find(d => d.id === docId);
    if (!doc) return;
    this.currentDoc = doc;
    document.querySelectorAll('.doc-row').forEach(row => {
      row.classList.toggle('active', row.dataset.docId === docId);
    });
    this.loadContent(doc);
  }

  loadContent(doc) {
    const contentEl = document.getElementById('previewContent');
    document.getElementById('previewTitle').textContent = doc.name;
    const downloadButton = document.getElementById('downloadMainBtn');
    downloadButton.hidden = false;
    downloadButton.onclick = () => this.downloadDocument(doc);
    if (this.cache[doc.id]) {
      this.displayContent(doc, this.cache[doc.id]);
      return;
    }
    contentEl.innerHTML = '<div class="loading-spinner"><div class="spinner"></div><p>Loading...</p></div>';
    fetch(doc.url)
      .then(r => r.json())
      .then(data => {
        this.cache[doc.id] = data;
        this.displayContent(doc, data);
      })
      .catch(e => {
        contentEl.innerHTML = '<div class="preview-empty"><div class="icon">❌</div><p></p></div>';
        contentEl.querySelector('p').textContent = `Failed to load: ${e.message}`;
      });
  }

  displayContent(doc, data) {
    const contentEl = document.getElementById('previewContent');
    if (doc.type === 'pdf') {
      contentEl.innerHTML = '<div class="preview-empty"><div class="icon">📕</div><p>PDF preview not yet supported</p><p class="document-preview-download-hint">Use the download button to open</p></div>';
    } else if (data.content) {
      const html = marked.parse(data.content);
      contentEl.innerHTML = `<div class="preview-markdown">${html}</div>`;
      contentEl.querySelectorAll('pre code').forEach(el => hljs.highlightElement(el));
    } else {
      contentEl.innerHTML = '<div class="preview-empty"><p>No content available</p></div>';
    }
  }

  downloadDocument(doc) {
    const a = document.createElement('a');
    a.href = doc.url;
    a.download = doc.name;
    a.click();
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const docs = JSON.parse(document.getElementById('document-preview-data').textContent);
  if (docs.length > 0) new DocumentBrowser(docs);
});
