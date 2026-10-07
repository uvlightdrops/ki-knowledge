document.addEventListener("change", function (event) {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || !target.matches("[data-select-all]")) {
    return;
  }
  const form = target.form;
  if (!form) {
    return;
  }
  // form.elements also includes controls associated through a form attribute.
  Array.from(form.elements).forEach((checkbox) => {
    if (checkbox instanceof HTMLInputElement && checkbox.type === "checkbox" &&
        checkbox.name === target.dataset.selectAll && checkbox !== target) {
      checkbox.checked = target.checked;
    }
  });
});
