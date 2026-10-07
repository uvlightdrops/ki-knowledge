(() => {
  const selectAll = document.getElementById("select-all");
  const selectedCount = document.getElementById("selected-count");
  if (!selectAll || !selectedCount) return;

  function updateSelectedCount() {
    const count = document.querySelectorAll(".file-checkbox:checked").length;
    selectedCount.textContent = `${count} file(s) selected`;
  }
  selectAll.addEventListener("change", function (event) {
    document.querySelectorAll(".file-checkbox").forEach(cb => cb.checked = event.target.checked);
    updateSelectedCount();
  });
  document.querySelectorAll(".file-checkbox").forEach(cb => {
    cb.addEventListener("change", updateSelectedCount);
  });
})();
