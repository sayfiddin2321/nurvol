/* ============================================================
   NURVOLT — QR Management
   ============================================================ */
(function () {
    "use strict";

    // ---------- Print QR sticker ----------
    function initPrint() {
        document.querySelectorAll("[data-print-page]").forEach((btn) => {
            btn.addEventListener("click", () => window.print());
        });

        document.querySelectorAll("[data-print]").forEach((btn) => {
            btn.addEventListener("click", (e) => {
                e.preventDefault();
                const targetId = btn.getAttribute("data-print");
                const target = document.getElementById(targetId);
                if (!target) return;

                const printWin = window.open("", "_blank", "width=600,height=800");
                printWin.document.write(`
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <title>NURVOLT QR</title>
                        <style>
                            body { font-family: Arial, sans-serif; text-align: center; padding: 40px; }
                            .card { border: 3px solid #071426; border-radius: 12px; padding: 30px; max-width: 400px; margin: 0 auto; }
                            .logo { font-size: 24px; font-weight: 700; color: #0076E8; margin-bottom: 8px; }
                            .subtitle { font-size: 12px; color: #666; margin-bottom: 20px; }
                            img { max-width: 280px; margin: 20px auto; display: block; }
                            .id { font-family: monospace; font-size: 11px; color: #666; margin-top: 16px; word-break: break-all; }
                            .hint { font-size: 12px; margin-top: 20px; color: #071426; }
                        </style>
                    </head>
                    <body>
                        <div class="card">
                            <div class="logo">⚡ NURVOLT</div>
                            <div class="subtitle">Elektr pasporti</div>
                            ${target.innerHTML}
                            <div class="hint">📱 Telefon kamerasi bilan skanerlang</div>
                        </div>
                        <script>window.onload = () => { window.print(); setTimeout(() => window.close(), 500); };<\/script>
                    </body>
                    </html>
                `);
                printWin.document.close();
            });
        });
    }

    // ---------- QR image URL copy ----------
    function initQRShare() {
        document.querySelectorAll("[data-qr-share]").forEach((btn) => {
            btn.addEventListener("click", async (e) => {
                e.preventDefault();
                const url = btn.getAttribute("data-qr-share");
                if (!url) return;

                if (navigator.share) {
                    try {
                        await navigator.share({
                            title: "VoltPass rasmlari",
                            text: "Obyekt rasmlari",
                            url: url,
                        });
                        return;
                    } catch (err) {
                        if (err.name === "AbortError") return;
                    }
                }

                // fallback: copy
                try {
                    await navigator.clipboard.writeText(url);
                    const original = btn.textContent;
                    btn.textContent = "✓ Havola nusxalandi";
                    setTimeout(() => (btn.textContent = original), 1500);
                } catch {
                    window.prompt("Havolani nusxalang:", url);
                }
            });
        });
    }

    // ---------- QR image regenerate ----------
    function initQRRegenerate() {
        document.querySelectorAll("form[data-qr-regen]").forEach((form) => {
            form.addEventListener("submit", (event) => {
                if (!window.confirm("QR kodni qayta yaratishni tasdiqlaysizmi? Eski QR ishlamay qoladi.")) {
                    event.preventDefault();
                }
            });
        });
    }

    document.addEventListener("DOMContentLoaded", () => {
        initPrint();
        initQRShare();
        initQRRegenerate();
    });
})();