"""Chrome CDP checks against the isolated QA server; fixtures use scripts.qa_settings."""
import base64
import json
from pathlib import Path
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".qa" / "deps"))
import websocket


class Browser:
    def __init__(self):
        pages = json.load(urllib.request.urlopen("http://127.0.0.1:9222/json"))
        page = next(item for item in pages if item["type"] == "page")
        self.socket = websocket.create_connection(page["webSocketDebuggerUrl"], origin="http://127.0.0.1:9222", timeout=25)
        self.id = 0
        self.errors = []
        self.bad_responses = []
        self.call("Page.enable")
        self.call("Runtime.enable")
        self.call("Network.enable")
        self.call("Network.setCacheDisabled", {"cacheDisabled": True})

    def call(self, method, params=None):
        self.id += 1
        call_id = self.id
        self.socket.send(json.dumps({"id": call_id, "method": method, "params": params or {}}))
        while True:
            message = json.loads(self.socket.recv())
            if message.get("method") == "Runtime.exceptionThrown":
                self.errors.append(message["params"]["exceptionDetails"])
            if message.get("method") == "Runtime.consoleAPICalled" and message["params"]["type"] == "error":
                self.errors.append(message["params"])
            if message.get("method") == "Network.responseReceived":
                response = message["params"]["response"]
                if response["status"] >= 400:
                    self.bad_responses.append({"url": response["url"], "status": response["status"]})
            if message.get("id") == call_id:
                if "error" in message:
                    raise AssertionError(message["error"])
                return message.get("result", {})

    def evaluate(self, code):
        result = self.call("Runtime.evaluate", {"expression": code, "returnByValue": True, "awaitPromise": True, "userGesture": True})
        if "exceptionDetails" in result:
            raise AssertionError(result["exceptionDetails"])
        return result.get("result", {}).get("value")

    def wait(self, expression, seconds=15):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            try:
                if self.evaluate(expression):
                    return
            except AssertionError:
                pass
            time.sleep(.1)
        raise AssertionError("Browser wait timed out: " + expression)

    def navigate(self, url):
        self.call("Page.navigate", {"url": url})
        self.wait("document.readyState === 'complete' && location.href === " + json.dumps(url))

    def viewport(self, width, height, mobile=False):
        self.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": height, "deviceScaleFactor": 1, "mobile": mobile})
        self.call("Emulation.setTouchEmulationEnabled", {"enabled": mobile, "maxTouchPoints": 5})

    def files(self, selector, paths):
        doc = self.call("DOM.getDocument")
        node = self.call("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": selector})
        self.call("DOM.setFileInputFiles", {"nodeId": node["nodeId"], "files": paths})

    def screenshot(self, name):
        self.evaluate("document.fonts.ready")
        result = self.call("Page.captureScreenshot", {"format": "png", "captureBeyondViewport": False})
        (ROOT / ".qa" / name).write_bytes(base64.b64decode(result["data"]))


def run():
    fixture = json.loads((ROOT / ".qa" / "fixture.json").read_text())
    base = fixture["base"]
    browser = Browser()
    browser.call("Network.clearBrowserCookies")
    checks = []
    def passed(label):
        checks.append(label)
        print("PASS:", label, flush=True)
    def no_overflow():
        return browser.evaluate("document.documentElement.scrollWidth <= innerWidth + 1")

    browser.viewport(1440, 1000)
    public_url = base + "/qr/" + fixture["qr"] + "/"
    browser.navigate(public_url)
    browser.wait("Array.from(document.querySelectorAll('.passport-gallery img')).every(img => img.complete && img.naturalWidth > 0)")
    assert no_overflow()
    assert browser.evaluate("document.querySelectorAll('[data-gallery-item]').length") == 3
    assert browser.evaluate("document.querySelectorAll('.contact-actions a').length") == 3
    assert browser.evaluate("document.querySelector('.contact-actions a').getAttribute('href')") == "tel:+998901234567"
    browser.screenshot("public-desktop.png")
    passed("Public passport, protected thumbnails, three real contact links, desktop layout")

    browser.evaluate("document.querySelector('[data-gallery-item]').click()")
    browser.wait("document.querySelector('dialog').open && document.querySelector('.lightbox-photo').complete && document.querySelector('.lightbox-photo').naturalWidth > 0")
    assert browser.evaluate("document.querySelector('.lightbox-photo').src.includes('/display/')")
    assert browser.evaluate("document.querySelector('[data-counter]').textContent") == "1 / 3"
    browser.evaluate("document.querySelector('.lightbox-next').click()")
    assert browser.evaluate("document.querySelector('[data-counter]').textContent") == "2 / 3"
    browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "ArrowLeft", "code": "ArrowLeft"})
    assert browser.evaluate("document.querySelector('[data-counter]').textContent") == "1 / 3"
    browser.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Escape", "code": "Escape"})
    browser.wait("!document.querySelector('dialog').open")
    browser.wait("document.activeElement.hasAttribute('data-gallery-item')")
    passed("Lightbox uses optimized full image; next/previous, keyboard, Escape and focus restoration")

    for width in [320, 390, 768]:
        browser.viewport(width, 844, True)
        assert no_overflow(), "Public overflow at " + str(width)
    browser.viewport(390, 844, True)
    browser.screenshot("public-mobile.png")
    browser.evaluate("document.querySelector('[data-gallery-item]').click()")
    browser.wait("document.querySelector('.lightbox-photo').complete")
    for event_type, x in [("touchStart", 300), ("touchMove", 180), ("touchMove", 80), ("touchEnd", 80)]:
        points = [] if event_type == "touchEnd" else [{"x": x, "y": 400, "id": 1, "radiusX": 4, "radiusY": 4}]
        browser.call("Input.dispatchTouchEvent", {"type": event_type, "touchPoints": points})
    browser.wait("document.querySelector('[data-counter]').textContent === '2 / 3'")
    browser.screenshot("lightbox-mobile.png")
    browser.evaluate("document.querySelector('.lightbox-close').click()")
    passed("Mobile 320/390/768 widths and real emulated touch swipe")

    browser.viewport(1440, 1000)
    browser.navigate(base + "/accounts/login/")
    browser.evaluate("document.querySelector('[name=username]').value='browser-electrician'; document.querySelector('[name=password]').value='Browser-QA-927!'; document.querySelector('form[method=post]').requestSubmit()")
    browser.wait("location.pathname === '/dashboard/' && document.readyState === 'complete'")
    passed("Browser login")
    browser.navigate(base + "/projects/create/")
    assert "status" in browser.evaluate("Array.from(document.querySelectorAll('.simple-form [name]')).map(el=>el.name).filter(name=>name!=='csrfmiddlewaretoken')")
    browser.evaluate("document.querySelector('[name=name]').value='Brauzer sinovi';  document.querySelector('.simple-form').requestSubmit()")
    browser.wait("/^\\/projects\\/\\d+\\/$/.test(location.pathname) && document.readyState === 'complete'")
    project_path = browser.evaluate("location.pathname")
    project_id = project_path.strip("/").split("/")[-1]
    assert browser.evaluate("document.querySelectorAll('.tab-btn').length") == 0
    assert browser.evaluate("getComputedStyle(document.querySelector('#tab-images')).display !== 'none'")
    assert browser.evaluate("!!document.querySelector('[data-qr-share]')")
    assert browser.evaluate("!document.querySelector('form[action*=\"toggle-public\"]')")
    passed("Create using only name; gallery and QR are immediately available without tabs or visibility controls")

    browser.navigate(base + project_path + "edit/")
    browser.evaluate("document.querySelector('[name=name]').value='Brauzer sinovi tahrirlandi'; document.querySelector('[name=description]').value='Brauzerda tahrirlangan izoh'; document.querySelector('.simple-form').requestSubmit()")
    browser.wait("location.pathname === " + json.dumps(project_path) + " && document.readyState === 'complete'")
    assert browser.evaluate("document.querySelector('h1').textContent") == "Brauzer sinovi tahrirlandi"
    passed("Edit object and persist updated data")

    upload_url = base + "/documents/projects/" + project_id + "/images/upload/"
    browser.navigate(upload_url)
    assert browser.evaluate("document.querySelector('[name=images]').getAttribute('capture')") is None
    assert browser.evaluate("document.querySelector('[data-camera-input]').getAttribute('capture')") == "environment"
    browser.files("[name=images]", fixture["fixtures"][:2])
    browser.wait("document.querySelectorAll('.upload-preview').length === 2")
    browser.evaluate("document.querySelector('.upload-preview button').click()")
    assert browser.evaluate("document.querySelector('[name=images]').files.length") == 1
    browser.files("[data-camera-input]", fixture["fixtures"][2:])
    browser.wait("document.querySelectorAll('.upload-preview').length === 2")
    # A desktop drop is represented by a browser File and the native DataTransfer API.
    browser.evaluate("""(async()=>{const blob=await (await fetch('/static/favicon.svg')).blob();const img=new Image();img.src=URL.createObjectURL(blob);await img.decode();const canvas=document.createElement('canvas');canvas.width=80;canvas.height=80;canvas.getContext('2d').drawImage(img,0,0,80,80);const png=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));const transfer=new DataTransfer();transfer.items.add(new File([png],'drag-drop.png',{type:'image/png'}));document.querySelector('[data-drop-zone]').dispatchEvent(new DragEvent('drop',{bubbles:true,cancelable:true,dataTransfer:transfer}));URL.revokeObjectURL(img.src)})()""")
    assert browser.evaluate("document.querySelector('[name=images]').files.length") == 3
    assert browser.evaluate("!document.querySelector('[name=is_public]') && !document.querySelector('[name=category]')")
    browser.evaluate("document.querySelector('[name=description]').value='Montaj rasmlari'")
    browser.viewport(390, 844, True)
    assert no_overflow()
    browser.screenshot("upload-mobile.png")
    browser.evaluate("document.querySelector('[data-upload-form]').requestSubmit()")
    browser.wait("location.pathname === " + json.dumps(project_path) + " && location.hash === '#tab-images' && document.readyState === 'complete'")
    assert browser.evaluate("document.querySelectorAll('[data-gallery-item]').length") == 3
    assert browser.evaluate("document.body.textContent.includes('Montaj rasmlari')")
    passed("Multi-image picker, preview removal, separate camera input, drag/drop, optional description, upload and mobile layout")

    for width in [320, 390, 768, 1440]:
        browser.viewport(width, 1000, width < 800)
        assert no_overflow(), "Object overflow at " + str(width)
    browser.viewport(390, 844, True)
    browser.screenshot("workspace-mobile.png")
    share_url = browser.evaluate("document.querySelector('[data-qr-share]').getAttribute('data-qr-share')")
    assert browser.evaluate("!document.querySelector('#share-url')")
    assert browser.evaluate("!!document.querySelector('a[href*=\\\"/qr/image/\\\"]')")
    browser.evaluate("Object.defineProperty(navigator,'share',{value:undefined,configurable:true});navigator.clipboard.writeText=async url=>{window.__copiedURL=url};document.querySelector('[data-qr-share]').click()")
    browser.wait("window.__copiedURL === " + json.dumps(share_url))
    cookies = browser.call("Network.getCookies")["cookies"]
    browser.call("Network.clearBrowserCookies")
    browser.navigate(share_url)
    browser.wait("Array.from(document.querySelectorAll('.passport-gallery img')).every(img => img.complete && img.naturalWidth > 0)")
    assert browser.evaluate("document.querySelectorAll('[data-gallery-item]').length") == 3
    assert browser.evaluate("!document.querySelector('form[action*=\"delete\"]')")
    assert no_overflow()
    browser.screenshot("new-gallery-public-mobile.png")
    passed("QR share copies stable link; all uploaded images open anonymously without permission steps")
    browser.call("Network.setCookies", {"cookies": cookies})

    browser.navigate(base + project_path + "#tab-images")
    browser.evaluate("window.confirm=()=>true;document.querySelector('form[action*=\\\"/delete/\\\"] button').click()")
    browser.wait("document.readyState === 'complete' && document.querySelectorAll('[data-gallery-item]').length === 2")
    passed("Delete uploaded image through browser and return to visible gallery")
    browser.call("Network.clearBrowserCookies")
    browser.navigate(share_url)
    browser.wait("Array.from(document.querySelectorAll('.passport-gallery img')).every(img => img.complete && img.naturalWidth > 0)")
    assert browser.evaluate("document.querySelectorAll('[data-gallery-item]').length") == 2
    passed("Same QR link reflects image deletion for anonymous visitors")
    browser.call("Network.setCookies", {"cookies": cookies})

    browser.navigate(base + "/projects/" + str(fixture["project"]) + "/passport/")
    browser.wait("Array.from(document.images).every(img=>img.complete && img.naturalWidth>0)")
    browser.call("Emulation.setEmulatedMedia", {"media": "print"})
    pdf = browser.call("Page.printToPDF", {"printBackground": True, "preferCSSPageSize": True})
    pdf_bytes = base64.b64decode(pdf["data"])
    assert pdf_bytes.startswith(b"%PDF") and len(pdf_bytes) > 5000
    (ROOT / ".qa" / "passport-a4.pdf").write_bytes(pdf_bytes)
    browser.screenshot("passport-print.png")
    browser.call("Emulation.setEmulatedMedia", {"media": "screen"})
    passed("A4 print rendered by Chrome and PDF generated with real QR and images")

    assert not browser.errors, browser.errors
    assert not browser.bad_responses, browser.bad_responses
    passed("No JavaScript console errors or HTTP 404/500 responses during browser workflows")
    result = {"checks": checks, "console_errors": browser.errors, "failed_responses": browser.bad_responses}
    (ROOT / ".qa" / "browser-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    browser.socket.close()
    print("Browser checks complete:", len(checks), flush=True)


if __name__ == "__main__":
    run()
