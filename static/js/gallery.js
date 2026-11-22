(function () {
"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const links = Array.from(document.querySelectorAll("[data-gallery-item]"));
    if (!links.length || typeof HTMLDialogElement === "undefined") return;
    const dialog = document.createElement("dialog");
    dialog.className = "passport-lightbox";
    dialog.setAttribute("aria-label", "Rasmlarni to'liq ekranda ko'rish");
    dialog.innerHTML = '<div class="lightbox-toolbar"><span data-counter aria-live="polite"></span><a class="lightbox-original" target="_blank" rel="noopener noreferrer">Asl rasm</a><button type="button" class="lightbox-close" aria-label="Yopish">✕</button></div><div class="lightbox-stage"><button type="button" class="lightbox-prev" aria-label="Oldingi rasm">‹</button><img class="lightbox-photo" alt=""><button type="button" class="lightbox-next" aria-label="Keyingi rasm">›</button><p class="lightbox-status" role="status" aria-live="polite"></p></div><p class="lightbox-caption"></p>';
    document.body.append(dialog);
    const photo = dialog.querySelector(".lightbox-photo");
    const status = dialog.querySelector(".lightbox-status");
    const stage = dialog.querySelector(".lightbox-stage");
    const prev = dialog.querySelector(".lightbox-prev");
    const next = dialog.querySelector(".lightbox-next");
    const counter = dialog.querySelector("[data-counter]");
    const original = dialog.querySelector(".lightbox-original");
    let group = [], current = 0, trigger, oldOverflow = "", start = null;
    const pointers = new Set();
    function show(index) {
        current = (index + group.length) % group.length;
        const link = group[current];
        status.textContent = "Rasm yuklanmoqda…";
        photo.classList.add("is-loading");
        photo.src = link.href;
        photo.alt = link.dataset.caption || link.querySelector("img")?.alt || "Obyekt surati";
        dialog.querySelector(".lightbox-caption").textContent = photo.alt;
        counter.textContent = (current + 1) + " / " + group.length;
        original.href = link.dataset.original || link.href;
        prev.hidden = next.hidden = group.length < 2;
    }
    photo.addEventListener("load", () => { status.textContent = ""; photo.classList.remove("is-loading"); });
    photo.addEventListener("error", () => { status.textContent = "Rasm ochilmadi. Asl rasm havolasini sinab ko'ring."; photo.classList.remove("is-loading"); });
    links.forEach(link => link.addEventListener("click", event => {
        if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
        event.preventDefault();
        trigger = link;
        group = links.filter(item => item.dataset.galleryGroup === link.dataset.galleryGroup);
        oldOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        dialog.showModal();
        show(group.indexOf(link));
    }));
    dialog.querySelector(".lightbox-close").addEventListener("click", () => dialog.close());
    dialog.addEventListener("click", event => { if (event.target === dialog) dialog.close(); });
    dialog.addEventListener("close", () => {
        document.body.style.overflow = oldOverflow;
        photo.removeAttribute("src");
        pointers.clear(); start = null;
        trigger?.focus({ preventScroll: true });
    });
    prev.addEventListener("click", () => show(current - 1));
    next.addEventListener("click", () => show(current + 1));
    dialog.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            event.preventDefault();
            dialog.close();
            return;
        }
        if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
            event.preventDefault();
            show(current + (event.key === "ArrowLeft" ? -1 : 1));
        }
    });
    stage.addEventListener("pointerdown", event => {
        if (event.target.closest("button") || event.pointerType === "mouse") return;
        pointers.add(event.pointerId);
        if (pointers.size === 1) start = { x: event.clientX, y: event.clientY };
        else start = null;
    });
    stage.addEventListener("pointerup", event => {
        pointers.delete(event.pointerId);
        if (!start) return;
        const dx = event.clientX - start.x, dy = event.clientY - start.y;
        if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.3) show(current + (dx < 0 ? 1 : -1));
        start = null;
    });
    stage.addEventListener("pointercancel", event => { pointers.delete(event.pointerId); start = null; });
});
})();

