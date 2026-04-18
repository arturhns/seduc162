from django.urls import path

from app.views import (
    EscolaCreateView,
    EscolaDeleteView,
    EscolaDetailView,
    EscolaListView,
    EscolaUpdateView,
)


app_name = "escolas"

urlpatterns = [
    path("", EscolaListView.as_view(), name="list"),
    path("novo/", EscolaCreateView.as_view(), name="create"),
    path("<int:pk>/", EscolaDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", EscolaUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", EscolaDeleteView.as_view(), name="delete"),
]
