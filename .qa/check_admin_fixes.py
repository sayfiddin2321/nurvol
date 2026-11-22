import base64
import json
from pathlib import Path
import sys
from uuid import uuid4

root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root))
from scripts.browser_check import Browser

fixture = json.loads((root / '.qa/fixture.json').read_text())
base = fixture['base']
browser = Browser()
checks = []


def passed(label):
    checks.append(label)
    print('PASS:', label, flush=True)


def login_admin():
    browser.call('Network.clearBrowserCookies')
    browser.navigate(base + '/accounts/login/')
    browser.evaluate("document.querySelector('[name=username]').value='browser-admin';document.querySelector('[name=password]').value='Browser-QA-927!';document.querySelector('form[method=post]').requestSubmit()")
    browser.wait("location.pathname==='/dashboard/' && document.readyState==='complete'")


def no_overflow():
    return browser.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


browser.viewport(1440, 1000)
login_admin()
paths = ['/accounts/manage/electricians/', '/accounts/manage/payment-settings/', '/projects/manage/showcase/', '/electricians/me/', '/electricians/me/clients/', '/electricians/inquiries/', '/accounts/settings/']
for path in paths:
    assert browser.evaluate('!!document.querySelector(' + json.dumps('a[href="' + path + '"]') + ')'), path
browser.screenshot('admin-restored-menu-desktop.png')
passed('All seven administrator and electrician workspace links are visible together')
for path in paths:
    browser.navigate(base + path)
    assert no_overflow(), path
passed('Every restored menu destination opens successfully')

browser.navigate(base + '/accounts/manage/payment-settings/')
assert browser.evaluate("document.querySelector('[name=card_number]').value") == '8600 0000 0000 0000'
browser.evaluate("document.documentElement.dataset.qaSubmit='pending';document.querySelector('[name=cardholder_name]').value='QA EXAMPLE UPDATED';document.querySelector('.page-container form[method=post]').requestSubmit()")
browser.wait("document.readyState==='complete' && !document.documentElement.dataset.qaSubmit")
assert browser.evaluate("document.querySelector('[name=cardholder_name]').value") == 'QA EXAMPLE UPDATED'
passed('Administrator can edit and save payment details')

browser.call('Network.clearBrowserCookies')
browser.navigate(base + '/accounts/register/')
username = 'browser-request-' + uuid4().hex[:8]
values = {'username': username, 'first_name': 'QA', 'last_name': 'Electrician', 'email': username + '@example.com', 'password1': 'Browser-QA-927!', 'password2': 'Browser-QA-927!'}
browser.evaluate('(function(){const values=' + json.dumps(values) + ';for(const [name,value] of Object.entries(values)){document.querySelector("[name="+name+"]").value=value;}document.querySelector("[name=role][value=electrician]").checked=true;document.querySelector("[name=accepted_terms]").checked=true;document.querySelector("#regForm").requestSubmit();})()')
browser.wait("location.pathname==='/accounts/electrician/access/' && document.readyState==='complete'")
assert browser.evaluate("document.body.textContent.includes('QA EXAMPLE UPDATED')")
passed('New electrician sees the saved administrator payment details')

browser.files('[name=receipt]', fixture['fixtures'][:1])
browser.evaluate("document.querySelector('[name=payment_reference]').value='BROWSER-PAYMENT-CHECK';document.querySelector('form[action$=\"/electrician/payment/\"]').requestSubmit()")
browser.wait("document.readyState==='complete' && !document.querySelector('[name=receipt]')")
passed('Electrician can upload a receipt and submit the payment request')
login_admin()
browser.navigate(base + '/accounts/manage/electricians/?status=payment_submitted')
assert browser.evaluate('document.body.textContent.includes(' + json.dumps(username) + ')')
assert browser.evaluate("document.body.textContent.includes('BROWSER-PAYMENT-CHECK')")
browser.screenshot('admin-payment-request.png')
browser.evaluate('(function(){const row=Array.from(document.querySelectorAll("tbody tr")).find(row=>row.textContent.includes(' + json.dumps(username) + '));row.querySelector("input[value=approve]").form.requestSubmit();})()')
browser.wait("location.pathname==='/accounts/manage/electricians/' && location.search==='' && document.readyState==='complete'")
assert browser.evaluate('(function(){const row=Array.from(document.querySelectorAll("tbody tr")).find(row=>row.textContent.includes(' + json.dumps(username) + '));return row.querySelector(".badge").textContent.trim()==="Faol";})()')
passed('Admin receives the payment request and approval activates the electrician')

browser.navigate(base + '/qr/projects/' + str(fixture['project']) + '/print/')
browser.wait("document.querySelector('.qr-sticker img').complete && document.querySelector('.qr-sticker img').naturalWidth>0")
assert browser.evaluate("document.querySelectorAll('.qr-sticker').length") == 1
browser.call('Emulation.setEmulatedMedia', {'media': 'print'})
assert browser.evaluate("document.querySelectorAll('.qr-sticker').length") == 1
assert browser.evaluate("getComputedStyle(document.querySelector('.mobile-bottom-nav')).display==='none'")
browser.screenshot('single-qr-print.png')
pdf = browser.call('Page.printToPDF', {'printBackground': True, 'preferCSSPageSize': True})
(root / '.qa/single-qr-print.pdf').write_bytes(base64.b64decode(pdf['data']))
browser.call('Emulation.setEmulatedMedia', {'media': 'screen'})
passed('Screen and A4 print show exactly one QR sticker')

browser.viewport(390, 844, True)
for path in ['/accounts/manage/payment-settings/', '/electricians/me/', '/electricians/me/clients/', '/electricians/inquiries/', '/accounts/settings/']:
    browser.navigate(base + path)
    assert no_overflow(), path
browser.navigate(base + '/dashboard/')
browser.evaluate("document.querySelector('.header-mobile-toggle').click()")
browser.screenshot('admin-restored-menu-mobile.png')
passed('Restored workspace and payment settings fit mobile screens')
assert not browser.errors, browser.errors
assert not browser.bad_responses, browser.bad_responses
passed('No JavaScript errors or failed HTTP responses')
(root / '.qa/admin-restoration-browser-results.json').write_text(json.dumps({'checks': checks, 'errors': browser.errors, 'failed_responses': browser.bad_responses}, indent=2), encoding='utf-8')
browser.socket.close()
print('Browser verification complete:', len(checks), flush=True)
