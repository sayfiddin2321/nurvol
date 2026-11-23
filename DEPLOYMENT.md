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

## Image uploads fail only in production

The message `Rasmlar saqlanmadi` comes from the Django save stage after form
validation. For this specific response, inspect the application traceback
`Image batch upload failed`; changing HTML form encoding or Nginx limits will
not resolve a filesystem write failure. New versions distinguish permissions,
read-only filesystems, disk/quota exhaustion and validation failures.

Run the diagnostic with the **same Python environment, settings, working
directory and user as Gunicorn**, using the ID from the failing upload URL:

```bash
# Replace the example user, paths and project ID with your deployment values.
sudo -u www-data /srv/nurvolt/venv/bin/python /srv/nurvolt/manage.py check_upload_storage --project-id 123
```

The command tests temporary files, image processing, and write/read/delete in
the actual project's original-image directory plus both shared preview
directories. It removes its diagnostic files without creating database rows.
Running as root can hide the permissions error. For a systemd service, inspect
its `User`, `Group`, `WorkingDirectory`, `EnvironmentFiles`, `ProtectSystem`,
`ReadWritePaths` and `DynamicUser` settings. If it has a filesystem sandbox,
the shell diagnostic must also be run within equivalent restrictions; a shell
success alone does not prove the service can write.

```bash
sudo systemctl show gunicorn -p User -p Group -p WorkingDirectory -p EnvironmentFiles -p ProtectSystem -p ReadWritePaths -p DynamicUser
sudo journalctl -u gunicorn -n 150 --no-pager
df -h
df -i
```

For `PermissionError`, grant the actual service user write and directory-traverse
access to the `MEDIA_ROOT` printed by the command, **including existing**
`projects/<id>/images`, `projects/thumbnails` and `projects/previews` directories.
For a read-only release directory, set an absolute persistent `MEDIA_ROOT` in
`.env` and allow that directory in the service's `ReadWritePaths` if applicable.
Copy existing uploads to that storage before switching paths. If configured,
`FILE_UPLOAD_TEMP_DIR` must exist and be writable too. Do not grant world-write
permissions or assume the service user is always `www-data`.

Example for a verified, dedicated media directory and a service running as
`www-data:www-data` (replace all example values first):

```bash
sudo chown -R www-data:www-data /srv/nurvolt/media
sudo find /srv/nurvolt/media -type d -exec chmod 750 {} +
sudo find /srv/nurvolt/media -type f -exec chmod 640 {} +
```

If the diagnostic reports no disk space, check both free blocks and inodes,
plus the service user's quota. Do not delete uploaded media to make room.
If WebP support is unavailable, JPEG/PNG uploads now generate PNG previews;
WebP input itself still requires a Pillow build that can decode WebP.

After deploying this fix, run migrations, collect static files, restart the
actual application service, rerun the diagnostic as its user, and upload a real
image through the site. For a separate **413** response, configure
`client_max_body_size 105M;` in the site's Nginx server block (100 MiB image
batch plus multipart overhead), then run `sudo nginx -t` before reloading Nginx.
Do not expose `/media/` with an Nginx alias; media uses permission-checked views.

## Project media uploader and panel galleries

Deploy the latest document migrations (including `0006` and `0007`) with `python manage.py
migrate`, run `collectstatic --noinput`, and restart the application. The migration
adds metadata/fingerprints and uniqueness constraints; existing images and documents
are preserved. The existing multi-image POST and document upload routes remain
available. The enhanced screen uses the new single-file `media_upload` route and
the same image/document storage services and permission checks.

The uploader supports JPG, PNG, WebP, MP4 and WebM, each up to 20 MB. Its queue
accepts up to 20 files and 100 MB in total. Each image/video has its own title and
optional description. Panel media uses the existing `panel` category and is shown
in a separate gallery on the project and its QR passport. Uploading follows the
existing automatic QR sharing behavior; private document flags and all ownership
checks continue to apply.

Saved image and video cards always show their category, including when the title
and optional comment are empty. Categories include `Simlar ulangan joylar` for
connections and junction boxes. Owners can correct an older upload's category in
the existing edit form without uploading the file again. Migration `0007` changes
choice metadata only and does not rewrite existing category values or files.

New uploads are deduplicated within a project by SHA-256 of the original bytes.
Their UUID upload token makes a retry safe even if the server saved the file but
the browser lost the response. PostgreSQL project row locks serialize simultaneous
uploads and database constraints enforce unique content and tokens. Older media
without fingerprints is compared on demand, preserving its name and description.
An identical file is returned as already uploaded; edit that existing item to
change its metadata. Identical bytes in different projects are allowed.

The native form remains usable without JavaScript, with metadata editable after
upload. Enhanced clients keep failed files in the current page for per-file retry;
they do not resend successful files. A page refresh clears unsaved browser file
selections, so the browser prompts before leaving with pending files.

Verification: `python manage.py test --settings=scripts.qa_settings --noinput`.
For browser checks, run the isolated QA server on port 8765 and a disposable Chrome
CDP session on localhost:9222, then `python -m scripts.media_browser_check`. That
script creates only QA fixtures and verifies both galleries, independent metadata,
responsive layouts, real WebM playback and a lost-response retry after commit.
Do not use `scripts.qa_settings` in production.

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
