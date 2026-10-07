(() => {
  const hiddenInput = document.getElementById('site-structure-hidden');
  const saveBtn = document.getElementById('hierarchy-save-btn');
  const resetBtn = document.getElementById('hierarchy-reset-btn');
  const expandBtn = document.getElementById('hierarchy-expand-btn');
  const collapseBtn = document.getElementById('hierarchy-collapse-btn');
  const rawTree = document.getElementById('initial-site-structure-json');
  const sourceTree = document.getElementById('source-tree-json');
  if (!hiddenInput || !saveBtn || !resetBtn || !expandBtn || !collapseBtn) return;

  function persistCurrentTree() {
    const tree = $('#hierarchy-tree').jstree(true);
    const raw = tree.get_json('#', { flat: false });
    const payload = Array.isArray(raw) ? raw.map(serializeTree) : [];
    hiddenInput.value = JSON.stringify(payload, null, 2);
  }
  function toJsTree(node) {
    if (typeof node === 'string') return { text: node, children: [] };
    if (!node || typeof node !== 'object') return { text: 'Untitled', children: [] };
    const title = node.title || node.name || node.slug || 'Untitled';
    const result = {
      text: title,
      children: Array.isArray(node.children) ? node.children.map(toJsTree) : [],
      icon: node.type === 'document' ? 'fa fa-file-alt' : 'fa fa-folder'
    };
    if (node.type) result.type = node.type;
    if (node.path) result.li_attr = { 'data-path': node.path };
    return result;
  }
  function serializeTree(node) {
    if (!node || typeof node !== 'object') {
      return { title: String(node || 'Untitled'), children: [] };
    }
    const payload = {
      title: node.text || node.title || 'Untitled',
      children: Array.isArray(node.children) ? node.children.map(serializeTree) : []
    };
    if (node.type) payload.type = node.type;
    if (node.li_attr && node.li_attr['data-path']) payload.path = node.li_attr['data-path'];
    return payload;
  }
  function buildTreeData(valueElement) {
    const parsed = valueElement ? JSON.parse(valueElement.textContent || '[]') : [];
    const value = Array.isArray(parsed) ? parsed : [parsed];
    return value.map(toJsTree);
  }
  function refreshTree() {
    const $tree = $('#hierarchy-tree');
    if ($tree.data('jstree')) $tree.jstree('destroy');
    $tree.jstree({
      core: {
        data: buildTreeData(rawTree),
        check_callback: true,
        multiple: false,
        themes: { dots: true, stripes: true, responsive: true },
        expand_selected_onload: true
      },
      plugins: ['wholerow', 'dnd', 'types'],
      types: {
        default: { icon: 'fa-solid fa-folder' },
        folder: { icon: 'fa-solid fa-folder' },
        document: { icon: 'fa-solid fa-file-alt' }
      }
    });
    $tree.jstree('open_all');
  }
  saveBtn.addEventListener('click', () => {
    persistCurrentTree();
    document.getElementById('hierarchy-form').submit();
  });
  resetBtn.addEventListener('click', () => {
    const baseline = sourceTree ? JSON.parse(sourceTree.textContent || '[]') : [];
    rawTree.textContent = JSON.stringify(baseline, null, 2);
    refreshTree();
    persistCurrentTree();
  });
  expandBtn.addEventListener('click', () => $('#hierarchy-tree').jstree('open_all'));
  collapseBtn.addEventListener('click', () => $('#hierarchy-tree').jstree('close_all'));
  $('#hierarchy-tree').on('move_node.jstree', function (event, data) {
    const parentId = data.parent;
    if (parentId && parentId !== '#') $('#hierarchy-tree').jstree('open_node', parentId);
    persistCurrentTree();
  });
  $('#hierarchy-tree').on('changed.jstree', () => persistCurrentTree());
  refreshTree();
  persistCurrentTree();
})();
