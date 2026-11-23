(function () {
"use strict";
const dialog = document.querySelector("[data-media-delete-dialog]");
if (!dialog || typeof dialog.showModal !== "function") return;
let trigger = null;
const form = dialog.querySelector("form");
document.addEventListener("click", event => {
    const link = event.target.closest("[data-media-delete]");
    if (!link || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    trigger = link;
    form.action = link.dataset.deleteAction;
    dialog.querySelector("[data-delete-item-name]").textContent = link.dataset.deleteName;
    dialog.showModal();
});
dialog.querySelector("[data-delete-cancel]").addEventListener("click", () => dialog.close());
dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
dialog.addEventListener("close", () => trigger?.focus());
form.addEventListener("submit", () => { form.querySelector('[type="submit"]').disabled = true; });
})();
