from django.urls import path

from app.views import (
    PeriodoProcessamentoCreateView,
    PeriodoProcessamentoDeleteView,
    PeriodoProcessamentoDetailView,
    PeriodoProcessamentoListView,
    PeriodoProcessamentoUpdateView,
)


app_name = "periodos_processamento"

urlpatterns = [
    path("", PeriodoProcessamentoListView.as_view(), name="list"),
    path("novo/", PeriodoProcessamentoCreateView.as_view(), name="create"),
    path("<int:pk>/", PeriodoProcessamentoDetailView.as_view(), name="detail"),
    path("<int:pk>/editar/", PeriodoProcessamentoUpdateView.as_view(), name="update"),
    path("<int:pk>/excluir/", PeriodoProcessamentoDeleteView.as_view(), name="delete"),
]
