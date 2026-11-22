"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from apps.projects.views import dashboard_view, home_view
from apps.documents.views import protected_media_view

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url=f"{settings.STATIC_URL}favicon.svg", permanent=True)),
    path("media/projects/<path:path>", protected_media_view),
    path("media/electricians/payment-receipts/<path:path>", protected_media_view),
    path("admin/", admin.site.urls),
    path("", home_view, name="home"),
    path("dashboard/", dashboard_view, name="dashboard"),
    path("accounts/", include("apps.accounts.urls")),
    path("electricians/", include("apps.electricians.urls")),
    path("projects/", include("apps.projects.urls")),
    path("electrical/", include("apps.electrical.urls")),
    path("documents/", include("apps.documents.urls")),
    path("qr/", include("apps.qrcodes.urls")),
    path("maintenance/", include("apps.maintenance.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.BASE_DIR / "static")
