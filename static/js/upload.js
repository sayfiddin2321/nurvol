(function () {
"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-upload-form]");
    if (!form) return;
    const input = form.querySelector('input[name="images"]');
    const submit = form.querySelector('[type="submit"]');
    if (!input) {
        form.addEventListener("submit", () => { submit.disabled = true; submit.textContent = "Yuklanmoqda…"; });
        return;
    }
    const zone = form.querySelector("[data-drop-zone]");
    const previews = form.querySelector("[data-upload-previews]");
    const status = form.querySelector("[data-upload-status]");
    const camera = form.querySelector("[data-camera-input]");
    const cameraButton = form.querySelector("[data-camera-trigger]");
    let entries = [];
    let urls = [];
    let canMerge = false;
    try { canMerge = typeof DataTransfer === "function" && !!new DataTransfer().items; } catch (_) {}
    const formatSize = size => (size / 1024 / 1024).toFixed(1) + " MB";
    function sync() {
        if (!canMerge) return;
        const transfer = new DataTransfer();
        entries.forEach(entry => transfer.items.add(entry.file));
        input.files = transfer.files;
    }
    function release() { urls.forEach(url => URL.revokeObjectURL(url)); urls = []; }
    function render() {
        release();
        previews.replaceChildren();
        entries.forEach((entry, index) => {
            const row = document.createElement("div");
            row.className = "upload-preview";
            const img = document.createElement("img");
            img.alt = entry.file.name;
            img.loading = "lazy";
            img.src = URL.createObjectURL(entry.file);
            urls.push(img.src);
            const fields = document.createElement("div");
            const name = document.createElement("p");
            name.className = "upload-preview__filename";
            name.textContent = entry.file.name + " · " + formatSize(entry.file.size);
            fields.append(name);
            row.append(img, fields);
            if (canMerge) {
                const remove = document.createElement("button");
                remove.type = "button";
                remove.className = "btn btn--secondary btn--sm";
                remove.textContent = "Olib tashlash";
                remove.setAttribute("aria-label", entry.file.name + " rasmini olib tashlash");
                remove.addEventListener("click", () => {
                    entries.splice(index, 1);
                    sync();
                    render();
                    status.textContent = entries.length + " ta rasm tanlandi.";
                    input.focus();
                });
                row.append(remove);
            }
            previews.append(row);
        });
    }
    function addFiles(files, append) {
        const next = append ? entries.slice() : [];
        const errors = [];
        Array.from(files).forEach(file => {
            if (!/\.(jpe?g|png|webp)$/i.test(file.name) || (file.type && !["image/jpeg", "image/png", "image/webp"].includes(file.type))) {
                errors.push(file.name + ": JPG, PNG yoki WebP tanlang.");
            } else if (file.size > 20 * 1024 * 1024) {
                errors.push(file.name + ": 20 MB dan katta.");
            } else if (next.length >= 20 || next.reduce((sum, item) => sum + item.file.size, 0) + file.size > 100 * 1024 * 1024) {
                errors.push("Bir martada 20 ta rasm, jami 100 MB gacha tanlash mumkin.");
            } else if (!next.some(entry => entry.file.name === file.name && entry.file.size === file.size && entry.file.lastModified === file.lastModified)) {
                next.push({ file });
            }
        });
        entries = next;
        sync();
        render();
        status.textContent = errors.length ? errors.join(" ") : entries.length + " ta rasm tayyor. Yuklash tugmasini bosing.";
        status.classList.toggle("field-error", errors.length > 0);
        // Native picker remains usable even on browsers without DataTransfer.
        submit.disabled = !canMerge && errors.length > 0;
    }
    input.addEventListener("change", () => addFiles(input.files, canMerge));
    if (canMerge) {
        cameraButton.hidden = false;
        cameraButton.addEventListener("click", () => camera.click());
        camera.addEventListener("change", () => { addFiles(camera.files, true); camera.value = ""; });
        ["dragenter", "dragover"].forEach(type => zone.addEventListener(type, event => {
            event.preventDefault(); zone.classList.add("is-dragging");
        }));
        ["dragleave", "drop"].forEach(type => zone.addEventListener(type, event => {
            event.preventDefault(); zone.classList.remove("is-dragging");
        }));
        zone.addEventListener("drop", event => addFiles(event.dataTransfer.files, true));
    }
    form.addEventListener("submit", event => {
        if (!input.files.length) {
            event.preventDefault();
            status.textContent = "Kamida bitta rasm tanlang.";
            input.focus();
            return;
        }
        submit.disabled = true;
        submit.textContent = "Yuklanmoqda…";
        status.textContent = "Rasmlar saqlanmoqda. Sahifani yopmang.";
    });
    window.addEventListener("pagehide", release);
    window.addEventListener("pageshow", () => { submit.disabled = false; submit.textContent = "Yuklash"; });
});
})();

