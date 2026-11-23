(function () {
"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const form = document.querySelector("[data-upload-form]");
    if (!form) return;
    const submit = form.querySelector('[type="submit"]');
    if (!form.matches("[data-media-form]")) {
        form.addEventListener("submit", () => { submit.disabled = true; submit.textContent = "Yuklanmoqda…"; });
        return;
    }
    if (!window.FormData || !window.XMLHttpRequest || !window.URL?.createObjectURL) return;
    form.classList.add("media-enhanced");
    const entries = [];
    const summary = form.querySelector("[data-upload-summary]");
    const total = form.querySelector("[data-total-progress]");
    const submitLabel = form.querySelector("[data-submit-label]");
    const groups = new Map();
    let busy = false;
    const accept = ".jpg,.jpeg,.png,.webp,.mp4,.webm,image/jpeg,image/png,image/webp,video/mp4,video/webm";
    const sizeText = bytes => bytes < 1024 * 1024 ? Math.max(1, Math.round(bytes / 1024)) + " KB" : (bytes / 1024 / 1024).toFixed(1) + " MB";
    const token = () => {
        if (window.crypto?.randomUUID) return crypto.randomUUID();
        return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, letter => {
            const number = window.crypto?.getRandomValues ? crypto.getRandomValues(new Uint8Array(1))[0] % 16 : Math.floor(Math.random() * 16);
            return (letter === "x" ? number : (number & 3) | 8).toString(16);
        });
    };
    function icons() { window.lucide?.createIcons(); }
    function announce(message, error = false) {
        summary.hidden = false;
        summary.textContent = message;
        summary.classList.toggle("is-error", error);
    }
    function updateCounts() {
        groups.forEach((group, key) => {
            const count = entries.filter(entry => entry.group === key).length;
            group.root.querySelector("[data-section-count]").textContent = count;
            group.root.querySelector("[data-queue-empty]").hidden = count > 0;
        });
        const pending = entries.filter(entry => entry.state !== "success");
        form.querySelector("[data-queue-count]").textContent = entries.length
            ? entries.length + " ta fayl · " + sizeText(entries.reduce((sum, entry) => sum + entry.file.size, 0))
            : "Fayllar tanlanmagan";
        submitLabel.textContent = busy ? "Yuklanmoqda…" : pending.some(entry => entry.state === "error") ? "Qayta yuklash" : "Fayllarni yuklash";
        submit.disabled = busy || !pending.length;
    }
    function lockControls() {
        form.querySelectorAll("[data-pick], [data-camera-trigger], .media-native-picker input, [name=general_category]").forEach(control => { control.disabled = busy; });
        entries.forEach(entry => {
            entry.card.querySelectorAll("input, textarea, select, button").forEach(control => {
                control.disabled = busy || (entry.state === "success" && !control.matches("[data-remove]"));
            });
        });
        updateCounts();
    }
    function state(entry, next, message) {
        entry.state = next;
        entry.card.dataset.state = next;
        const status = entry.card.querySelector("[data-file-status]");
        status.textContent = message;
        status.classList.toggle("field-error", next === "error");
        entry.card.querySelector("[data-retry]").hidden = next !== "error";
        entry.card.querySelector("[data-file-progress]").hidden = !["uploading", "saving", "success"].includes(next);
        if (next === "success") {
            entry.card.querySelector("[data-replace]").hidden = true;
            entry.card.querySelector("[data-remove]").textContent = "Ro'yxatdan olib tashlash";
        }
    }
    function preview(entry) {
        if (entry.url) URL.revokeObjectURL(entry.url);
        entry.url = URL.createObjectURL(entry.file);
        const slot = entry.card.querySelector("[data-file-preview]");
        const video = /\.(mp4|webm)$/i.test(entry.file.name);
        const media = document.createElement(video ? "video" : "img");
        media.src = entry.url;
        if (video) { media.controls = true; media.preload = "metadata"; media.playsInline = true; media.setAttribute("aria-label", entry.file.name); }
        else media.alt = entry.file.name;
        slot.replaceChildren(media);
        entry.card.querySelector("[data-file-name]").textContent = entry.file.name;
        entry.card.querySelector("[data-file-size]").textContent = (video ? "VIDEO · " : "RASM · ") + sizeText(entry.file.size);
    }
    function validation(file, replaced = null) {
        if (!/\.(jpe?g|png|webp|mp4|webm)$/i.test(file.name)) return "JPG, PNG, WebP, MP4 yoki WebM faylini tanlang.";
        if (!file.size) return "Fayl bo'sh. Boshqa faylni tanlang.";
        if (file.size > 20 * 1024 * 1024) return "Fayl hajmi 20 MB dan oshmasligi kerak.";
        const others = entries.filter(entry => entry !== replaced);
        if (others.length >= 20 || others.reduce((sum, entry) => sum + entry.file.size, 0) + file.size > 100 * 1024 * 1024) return "Bir martada 20 ta fayl, jami 100 MB gacha tanlang.";
        return "";
    }
    function createCard(file, key) {
        const entry = { file, group: key, token: token(), state: "queued", url: null };
        const card = document.createElement("article");
        entry.card = card;
        card.className = "media-file-card";
        card.dataset.entry = entry.token;
        card.innerHTML = '<div class="media-file-preview" data-file-preview></div><div class="media-file-body"><p class="media-file-name" data-file-name></p><p class="media-file-size" data-file-size></p><label class="form-label" data-title-label></label><input type="text" maxlength="150" data-file-title><label class="form-label" data-description-label>Izoh <span class="muted">(ixtiyoriy)</span></label><textarea rows="2" maxlength="255" data-file-description placeholder="Qo‘shimcha ma’lumot yozishingiz mumkin"></textarea><div data-category-field><label class="form-label" data-category-label>Rasm turi</label><select data-file-category><option value="other">Boshqa loyiha rasmlari</option><option value="room">Xonalar</option><option value="cables">Kabel yo‘nalishlari</option><option value="connections">Simlar ulangan joylar</option><option value="device">Elektr nuqtalari</option></select></div><progress max="100" value="0" data-file-progress hidden aria-label="Fayl yuklash jarayoni"></progress><p class="media-file-status" data-file-status role="status" aria-live="polite"></p><a class="media-saved-link" data-saved-link hidden>Galereyada ko‘rish</a><div class="media-file-actions"><button type="button" class="btn btn--secondary btn--sm" data-replace>Almashtirish</button><button type="button" class="btn btn--secondary btn--sm" data-retry hidden>Qayta urinish</button><button type="button" class="btn btn--ghost btn--sm field-error" data-remove>Olib tashlash</button></div></div>';
        const title = card.querySelector("[data-file-title]");
        const description = card.querySelector("[data-file-description]");
        const category = card.querySelector("[data-file-category]");
        category.value = form.querySelector('[name="general_category"]:checked')?.value || "other";
        [[title, "title"], [description, "description"], [category, "category"]].forEach(([control, name]) => {
            control.id = entry.token + "-" + name;
            card.querySelector("[data-" + name + "-label]").htmlFor = control.id;
        });
        card.querySelector("[data-title-label]").textContent = key === "panel" ? "Shit nomi yoki raqami" : "Rasm yoki video nomi";
        title.value = key === "panel" ? (entries.filter(item => item.group === key).length + 1) + "-shit" : file.name.replace(/\.[^.]+$/, "").slice(0, 150);
        title.placeholder = key === "panel" ? "Masalan: 1-shit, Qavat shitlari" : "Faylga nom bering";
        if (key === "panel") card.querySelector("[data-category-field]").hidden = true;
        const replacement = document.createElement("input");
        replacement.type = "file"; replacement.accept = accept; replacement.hidden = true;
        card.append(replacement);
        card.querySelector("[data-replace]").addEventListener("click", () => replacement.click());
        replacement.addEventListener("change", () => {
            if (!replacement.files.length || busy) return;
            const next = replacement.files[0];
            const error = validation(next, entry);
            if (error) { announce(error, true); replacement.value = ""; return; }
            entry.file = next; entry.token = token();
            preview(entry);
            state(entry, "queued", "Yuklashga tayyor");
            summary.hidden = true; total.hidden = true;
            replacement.value = "";
            updateCounts();
        });
        card.querySelector("[data-remove]").addEventListener("click", () => {
            if (busy) return;
            URL.revokeObjectURL(entry.url);
            entries.splice(entries.indexOf(entry), 1);
            card.remove(); updateCounts();
            groups.get(key).root.querySelector("[data-pick]").focus();
        });
        card.querySelector("[data-retry]").addEventListener("click", () => run([entry]));
        entries.push(entry);
        groups.get(key).grid.append(card);
        preview(entry);
        state(entry, "queued", "Yuklashga tayyor");
        return entry;
    }
    function addFiles(files, key) {
        if (busy) return;
        summary.hidden = true; total.hidden = true;
        const errors = [];
        Array.from(files).forEach(file => {
            const error = validation(file);
            if (error) { errors.push(file.name + ": " + error); return; }
            if (entries.some(entry => entry.file.name === file.name && entry.file.size === file.size && entry.file.lastModified === file.lastModified)) {
                errors.push(file.name + ": bu fayl ro'yxatda bor."); return;
            }
            createCard(file, key);
        });
        const box = groups.get(key).root.querySelector("[data-selection-error]");
        box.textContent = errors.join(" "); box.hidden = !errors.length;
        updateCounts();
    }
    form.querySelectorAll("[data-media-section]").forEach(root => {
        const key = root.dataset.mediaSection;
        const input = root.querySelector(".media-native-picker input");
        const zone = root.querySelector("[data-drop-zone]");
        const camera = root.querySelector("[data-camera-input]");
        const cameraButton = root.querySelector("[data-camera-trigger]");
        const pick = root.querySelector("[data-pick]");
        groups.set(key, { root, grid: root.querySelector("[data-upload-previews]") });
        pick.hidden = false;
        cameraButton.hidden = root.dataset.videoOnly === "true";
        pick.addEventListener("click", () => input.click());
        input.addEventListener("change", () => { addFiles(input.files, key); input.value = ""; });
        cameraButton.addEventListener("click", () => camera.click());
        camera.addEventListener("change", () => { addFiles(camera.files, key); camera.value = ""; });
        let dragDepth = 0;
        ["dragenter", "dragover"].forEach(type => zone.addEventListener(type, event => {
            event.preventDefault();
            if (type === "dragenter") dragDepth++;
            if (!busy) zone.classList.add("is-dragging");
        }));
        zone.addEventListener("dragleave", event => { event.preventDefault(); if (--dragDepth <= 0) zone.classList.remove("is-dragging"); });
        zone.addEventListener("drop", event => { event.preventDefault(); dragDepth = 0; zone.classList.remove("is-dragging"); addFiles(event.dataTransfer.files, key); });
    });
    function upload(entry, onProgress) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            const data = new FormData();
            data.append("csrfmiddlewaretoken", form.querySelector('[name="csrfmiddlewaretoken"]').value);
            data.append("file", entry.file);
            data.append("title", entry.card.querySelector("[data-file-title]").value);
            data.append("description", entry.card.querySelector("[data-file-description]").value);
            data.append("category", entry.group === "panel" ? "panel" : entry.card.querySelector("[data-file-category]").value);
            data.append("upload_token", entry.token);
            xhr.open("POST", form.dataset.mediaEndpoint);
            xhr.setRequestHeader("Accept", "application/json");
            xhr.responseType = "json";
            xhr.timeout = 120000;
            xhr.upload.onprogress = event => {
                if (!event.lengthComputable) return;
                const ratio = event.loaded / event.total;
                entry.card.querySelector("[data-file-progress]").value = Math.round(ratio * 100);
                onProgress(ratio);
                if (ratio === 1) state(entry, "saving", "Serverda saqlanmoqda…");
            };
            xhr.onload = () => {
                const result = xhr.response;
                if (xhr.status >= 200 && xhr.status < 300 && result?.ok) return resolve(result);
                const error = result?.error || (xhr.status === 413 ? "Server yuklash hajmini cheklagan (413). Administratorga murojaat qiling."
                    : xhr.status === 403 ? "Yuklashga ruxsat yo'q yoki sessiya muddati tugagan. Sahifani yangilab, qayta kiring."
                    : xhr.status === 200 ? "Sessiya muddati tugagan. Saytga qayta kirib, urinib ko'ring."
                    : "Server faylni saqlamadi (" + xhr.status + "). Qayta urinib ko'ring.");
                reject(new Error(error));
            };
            xhr.onerror = () => reject(new Error("Server bilan aloqa uzildi. Internetni tekshirib, qayta urinib ko'ring."));
            xhr.ontimeout = () => reject(new Error("Serverdan javob kutilganidan uzoq davom etdi. Qayta urinib ko'ring."));
            xhr.onabort = () => reject(new Error("Yuklash to'xtatildi. Qayta urinib ko'ring."));
            xhr.send(data);
        });
    }
    async function run(list) {
        if (busy || !list.length) return;
        busy = true; lockControls();
        total.hidden = false; summary.hidden = true;
        const bytes = list.reduce((sum, entry) => sum + entry.file.size, 0);
        let completed = 0;
        let failed = 0;
        for (const [index, entry] of list.entries()) {
            state(entry, "uploading", "Yuklanmoqda…");
            entry.card.querySelector("[data-file-progress]").value = 0;
            total.querySelector("[data-total-label]").textContent = (index + 1) + " / " + list.length + " fayl yuklanmoqda";
            const progress = ratio => {
                const value = Math.round((completed + entry.file.size * ratio) / bytes * 100);
                total.querySelector("progress").value = value;
                total.querySelector("[data-total-percent]").textContent = value + "%";
            };
            try {
                const result = await upload(entry, progress);
                entry.card.querySelector("[data-file-title]").value = result.title;
                entry.card.querySelector("[data-file-description]").value = result.description;
                state(entry, "success", "✓ " + result.message);
                entry.card.querySelector("[data-file-progress]").value = 100;
                const link = entry.card.querySelector("[data-saved-link]");
                link.href = result.gallery_url; link.hidden = false;
                form.querySelector("[data-gallery-link]").href = result.gallery_url;
            } catch (error) {
                failed++;
                state(entry, "error", error.message);
            }
            progress(1); completed += entry.file.size;
        }
        busy = false; lockControls();
        total.querySelector("[data-total-label]").textContent = "Yuklash yakunlandi";
        announce(failed ? failed + " ta fayl yuklanmadi. Sababini tekshirib, «Qayta urinish» tugmasini bosing. Saqlangan fayllar qayta yuborilmaydi."
            : "✓ Muvaffaqiyatli yuklandi. Fayllarni galereyada ko'rishingiz mumkin.", failed > 0);
    }
    form.addEventListener("submit", event => {
        event.preventDefault();
        const pending = entries.filter(entry => entry.state !== "success");
        if (!pending.length) { announce("Kamida bitta rasm yoki video tanlang.", true); return; }
        run(pending);
    });
    window.addEventListener("beforeunload", event => {
        if (busy || entries.some(entry => entry.state !== "success")) { event.preventDefault(); event.returnValue = ""; }
    });
    window.addEventListener("pagehide", event => { if (!event.persisted) entries.forEach(entry => URL.revokeObjectURL(entry.url)); });
    updateCounts(); icons();
});
})();
