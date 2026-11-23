"""Exercise the media uploader against the isolated QA server on localhost:8765."""
import json
import os
from uuid import uuid4

os.environ.setdefault("SECRET_KEY", "isolated-media-browser-check-only")
os.environ["DJANGO_SETTINGS_MODULE"] = "scripts.qa_settings"
import django
django.setup()

from django.conf import settings
from django.test import Client
from PIL import Image, ImageDraw
from apps.accounts.models import User
from apps.projects.models import Project
from apps.documents.models import ProjectImage
from apps.qrcodes.models import QRCode
from scripts.browser_check import Browser


def run():
    root = settings.QA_ROOT
    fixtures = root / "media-fixtures"
    fixtures.mkdir(exist_ok=True)
    paths = []
    for index, (name, color, label) in enumerate([
        ("xona.jpg", "#e2e8f0", "XONA"), ("kabel.jpg", "#075985", "KABEL"),
        ("shit.jpg", "#172033", "SH-1"), ("yangi-xona.jpg", "#334155", "YANGI XONA"),
    ]):
        image = Image.new("RGB", (1000, 650), color)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((160, 90, 840, 560), radius=25, fill="#cbd5e1", outline="#64748b", width=8)
        for offset in range(220, 810, 85):
            draw.rounded_rectangle((offset, 150, offset + 45, 470), radius=8, fill="#f8fafc", outline="#2563eb", width=5)
        draw.text((40, 30), label, fill="#2563eb" if index == 0 else "white")
        path = fixtures / name
        image.save(path, "JPEG")
        paths.append(str(path.resolve()))
    owner = User.objects.create_user(username="media-browser-" + uuid4().hex[:10], role="electrician")
    project = Project.objects.create(electrician=owner, name="Chilonzor · Elektr montaj", is_public=True)
    client = Client()
    client.force_login(owner)
    browser = Browser()
    browser.call("Network.clearBrowserCookies")
    browser.call("Network.setCookie", {"name": settings.SESSION_COOKIE_NAME, "value": client.cookies[settings.SESSION_COOKIE_NAME].value, "url": "http://127.0.0.1:8765"})
    base = "http://127.0.0.1:8765"
    upload_url = f"{base}/documents/projects/{project.pk}/images/upload/"
    detail_url = f"{base}/projects/{project.pk}/"
    checks = []

    def passed(message):
        checks.append(message)
        print("PASS:", message, flush=True)

    def no_overflow():
        assert browser.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")

    browser.viewport(1440, 1100)
    browser.navigate(detail_url)
    browser.wait("document.querySelectorAll('.media-action-card').length === 7")
    no_overflow()
    browser.screenshot("media-category-actions-desktop.png")
    for width in [768, 390, 320]:
        browser.viewport(width, 1000, width < 768)
        no_overflow()
    browser.viewport(1440, 1100)
    browser.navigate(upload_url + "?media=video#general-uploads")
    browser.wait("document.querySelector('.media-enhanced')")
    assert browser.evaluate("document.querySelector('[data-media-section=general] [data-pick]').textContent") == "Video tanlash"
    assert browser.evaluate("document.querySelector('[data-media-section=general] [data-camera-trigger]').hidden")
    browser.navigate(upload_url + "?category=room#general-uploads")
    browser.wait("document.querySelector('.media-enhanced')")
    assert browser.evaluate("document.querySelector('[name=general_category]:checked').value") == "room"
    assert browser.evaluate("Array.from(document.querySelectorAll('.media-category-option')).every(label => label.offsetWidth > 0)")
    browser.evaluate("window.scrollTo(0,0)")
    assert browser.evaluate("document.querySelectorAll('[data-media-section]').length") == 2
    browser.screenshot("media-upload-desktop.png")
    no_overflow()
    passed("Seven visible project shortcuts; categories appear before file selection and the chosen shortcut preselects the type")
    browser.files('input[name="general_files"]', [paths[0], paths[1]])
    browser.files('input[name="panel_files"]', [paths[2]])
    browser.wait("document.querySelectorAll('.media-file-card').length === 3")
    assert browser.evaluate("document.querySelector('[data-file-category]').value") == "room"
    browser.evaluate("document.querySelectorAll('[data-media-section=general] [data-file-title]')[0].value = 'Mehmonxona'; document.querySelectorAll('[data-media-section=general] [data-file-description]')[0].value = 'Rozetkalar joylashuvi'; document.querySelector('[data-file-category]').value = 'room'; document.querySelector('[data-media-section=panel] [data-file-title]').value = '1-shit'; document.querySelector('[data-media-section=panel] [data-file-description]').value = 'Asosiy kirish shiti';")
    browser.files('[data-media-section=general] .media-file-card input[type=file]', [paths[3]])
    assert browser.evaluate("document.querySelector('[data-file-title]').value") == "Mehmonxona"
    assert browser.evaluate("document.querySelector('[data-file-description]').value") == "Rozetkalar joylashuvi"
    browser.evaluate("document.querySelectorAll('[data-media-section=general] [data-remove]')[1].click()")
    assert browser.evaluate("document.querySelectorAll('.media-file-card').length") == 2
    passed("Immediate previews, per-file names and optional comments, replacement retains metadata, removal")
    browser.evaluate("""(async () => {
        const canvas = document.createElement('canvas'); canvas.width = 320; canvas.height = 180;
        const ctx = canvas.getContext('2d'); const stream = canvas.captureStream(10);
        const recorder = new MediaRecorder(stream, {mimeType:'video/webm'}); const chunks = [];
        recorder.ondataavailable = event => chunks.push(event.data);
        const stopped = new Promise(resolve => recorder.onstop = resolve);
        recorder.start();
        for (let frame = 0; frame < 12; frame++) { ctx.fillStyle = frame % 2 ? '#2563eb' : '#172033'; ctx.fillRect(0,0,320,180); await new Promise(resolve => setTimeout(resolve, 100)); }
        recorder.stop(); await stopped; stream.getTracks().forEach(track => track.stop());
        const file = new File(chunks, 'shit-jarayoni.webm', {type:'video/webm'});
        const transfer = new DataTransfer(); transfer.items.add(file);
        document.querySelector('[data-media-section=panel] [data-drop-zone]').dispatchEvent(new DragEvent('drop', {bubbles:true, cancelable:true, dataTransfer:transfer}));
    })()""")
    browser.wait("document.querySelectorAll('.media-file-card').length === 3")
    assert browser.evaluate("!!document.querySelector('.media-file-preview video')")
    passed("Real WebM video selection and preview through drag and drop")
    for width in [1024, 768, 390, 320]:
        browser.viewport(width, 1000, width < 768)
        no_overflow()
    browser.viewport(390, 1000, True)
    browser.screenshot("media-upload-mobile.png")
    browser.viewport(1440, 1100)
    browser.screenshot("media-upload-cards.png")
    passed("Responsive layouts at 1440, 1024, 768, 390 and 320 pixels")
    browser.evaluate("document.querySelector('[data-media-form]').requestSubmit()")
    browser.wait("document.querySelectorAll('[data-state=success]').length === 3", seconds=30)
    assert browser.evaluate("document.querySelector('[data-total-percent]').textContent") == "100%"
    assert project.images.count() == 2
    assert project.documents.count() == 1
    panel = project.images.get(category="panel")
    assert (panel.title, panel.description) == ("1-shit", "Asosiy kirish shiti")
    assert project.documents.get().description == ""
    passed("All images and a playable video saved with independent metadata and success indicators")

    browser.evaluate("document.querySelector('[name=general_category][value=connections]').click()")
    browser.files('input[name="general_files"]', [paths[1]])
    assert browser.evaluate("Array.from(document.querySelectorAll('[data-media-section=general] [data-file-category]')).at(-1).value") == "connections"
    browser.evaluate("""window.__requests = []; const originalSend = XMLHttpRequest.prototype.send;
        XMLHttpRequest.prototype.send = function(data) {
            window.__requests.push(data.get('upload_token'));
            const xhr = this; const callback = this.onload;
            this.onload = () => { XMLHttpRequest.prototype.send = function(next) { window.__requests.push(next.get('upload_token')); return originalSend.call(this,next); }; xhr.onerror(); };
            return originalSend.call(this,data);
        };""")
    browser.evaluate("document.querySelector('[data-media-form]').requestSubmit()")
    browser.wait("document.querySelectorAll('[data-state=error]').length === 1")
    assert project.images.count() == 3
    browser.evaluate("document.querySelector('[data-state=error] [data-retry]').click()")
    browser.wait("document.querySelectorAll('[data-state=success]').length === 4")
    requests = browser.evaluate("window.__requests")
    assert len(requests) == 2 and requests[0] == requests[1]
    assert project.images.count() == 3
    browser.screenshot("media-upload-success.png")
    passed("Lost response after commit: per-file retry reuses its token and creates no duplicate or repeat uploads")

    browser.navigate(detail_url)
    browser.wait("document.querySelectorAll('[data-gallery-item]').length === 3")
    assert browser.evaluate("document.querySelectorAll('#tab-panels [data-gallery-item]').length") == 1
    assert browser.evaluate("document.querySelectorAll('#tab-images [data-gallery-item]').length") == 2
    labels = browser.evaluate("Array.from(document.querySelectorAll('.media-category-label')).map(label => label.textContent)")
    assert all(label in labels for label in ["Xonalar rasmlari", "Simlar ulangan joylar", "Elektr shitlari"]), labels
    browser.evaluate("document.querySelector('#tab-panels [data-gallery-item]').click()")
    browser.wait("document.querySelector('.passport-lightbox[open] .lightbox-photo').naturalWidth > 0")
    assert browser.evaluate("document.querySelector('[data-counter]').textContent") == "1 / 1"
    browser.evaluate("document.querySelector('.lightbox-close').click()")
    browser.screenshot("media-gallery-desktop.png")
    passed("Saved categories, titles and comments are visible; panel gallery and lightbox remain separate")
    browser.navigate(f"{base}/documents/images/{panel.pk}/edit/")
    browser.evaluate("document.querySelector('[name=title]').value = 'Qavat shiti'; document.querySelector('[name=description]').value = ''; document.querySelector('form.simple-form').requestSubmit()")
    browser.wait("document.readyState === 'complete' && location.pathname === '/projects/" + str(project.pk) + "/'")
    panel.refresh_from_db()
    assert panel.title == "Qavat shiti" and panel.description == ""
    browser.evaluate("document.querySelector('#tab-panels [data-media-delete]').click()")
    browser.wait("document.querySelector('[data-media-delete-dialog]').open")
    browser.screenshot("media-delete-confirmation.png")
    browser.evaluate("document.querySelector('[data-delete-cancel]').click()")
    assert ProjectImage.objects.filter(pk=panel.pk).exists()
    browser.evaluate("document.querySelector('#tab-images [data-media-delete]').click()")
    browser.wait("document.querySelector('[data-media-delete-dialog]').open")
    browser.evaluate("document.querySelector('[data-media-delete-dialog] form').requestSubmit()")
    browser.wait("document.readyState === 'complete' && !document.querySelector('[data-media-delete-dialog]').open")
    assert project.images.count() == 2
    passed("Saved metadata can be edited; deletion requires an accessible confirmation dialog, cancellation preserves media")
    browser.call("Network.clearBrowserCookies")
    qr = QRCode.objects.get(project=project, panel=None)
    browser.navigate(f"{base}/qr/{qr.token}/")
    browser.wait("document.querySelector('#tab-panels video').readyState >= 1")
    browser.evaluate("document.querySelector('#tab-panels video').play()")
    browser.wait("document.querySelector('#tab-panels video').currentTime > 0")
    browser.viewport(390, 1000, True)
    no_overflow()
    browser.screenshot("media-gallery-public-mobile.png")
    assert browser.evaluate("document.querySelectorAll('.gallery-item-actions').length") == 0
    passed("Public QR displays both galleries and plays the uploaded video without exposing edit controls")
    assert not browser.errors, browser.errors
    (root / "media-browser-results.json").write_text(json.dumps({"checks": checks, "console_errors": browser.errors, "project_id": project.pk}, ensure_ascii=False, indent=2), encoding="utf-8")
    browser.socket.close()
    print(f"Browser checks complete: {len(checks)}", flush=True)


if __name__ == "__main__":
    run()
