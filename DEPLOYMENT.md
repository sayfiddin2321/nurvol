# Production deployment

## Required environment

Copy `.env.example` to `.env` on the server and set a unique `SECRET_KEY`,
the real `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, and HTTPS `SITE_URL`.
Keep `.env` private and do not commit it. Generate a key with:

```text
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Set `DEBUG=False` in production. HTTPS redirect, HSTS, and secure session/CSRF
cookies default to enabled when `DEBUG=False`. If HTTPS ends at a reverse
proxy, configure `USE_X_FORWARDED_PROTO=True` only when that trusted proxy
always sets `X-Forwarded-Proto: https`; otherwise redirect loops or insecure
request detection can result. Do not enable HSTS until HTTPS works for every
host served by the application.

Set the SMTP variables so password-reset emails can be delivered. The console
email backend is used only when `DEBUG=True`.

## Deploying a new version

From the project directory, activate the deployment virtual environment and
run:

```text
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Restart/reload the web application after deploying. Configure the platform's
media storage and web server separately; Django's development server is not a
production static/media server. Back up the database and uploaded media before
applying migrations.

Payment receipt images contain private user information. Keep the
`electricians/payment-receipts/` media path private in production storage; serve
receipts through the authenticated `/accounts/electrician/payment-receipt/<user_id>/`
view rather than exposing the upload directory as public static media.

## Homepage project showcase

After migrations, an administrator can choose the featured active electrician
at `/projects/manage/showcase/`. Only that electrician's completed projects
marked public are shown under “Biz qilgan ishlar”; the displayed client count
is calculated from distinct client accounts linked to those projects. Assign
clients to projects and mark only work approved for public display as public.

Electricians can create and manage only their own customer accounts at
`/electricians/me/clients/`; the initial password is displayed once after
creation. Project assignment choices are limited to that electrician's linked
customers. Regular customers can browse active electrician profiles and send
requests; submitting a request links that customer to the requested electrician.
