from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("favicon.ico", RedirectView.as_view(url="/static/favicon.svg", permanent=True)),
    path("django-admin/", admin.site.urls),
    path("", include("pricing.urls")),
]
