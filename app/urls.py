from django.urls import path

from .views import (
    AgenteEscolarCreateView,
    AgenteEscolarDeleteView,
    AgenteEscolarDetailView,
    AgenteEscolarListView,
    AgenteEscolarUpdateView,
)

app_name = "app"

urlpatterns = [
    path("", AgenteEscolarListView.as_view(), name="list"),
    path("novo/", AgenteEscolarCreateView.as_view(), name="create"),
    path("<int:pk>/", AgenteEscolarDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", AgenteEscolarUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", AgenteEscolarDeleteView.as_view(), name="delete"),
]
