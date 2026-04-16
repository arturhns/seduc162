from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="app:list", permanent=False)),
    path(
        "agentes-escolares/",
        include(("app.urls", "app"), namespace="app"),
    ),
]
