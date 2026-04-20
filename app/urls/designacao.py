from django.urls import path

from app.views.designacao import DesignacaoAgenteSearchView, DesignacaoView

app_name = "designacao"

urlpatterns = [
    path("<int:escola_id>/", DesignacaoView.as_view(), name="form"),
    path(
        "<int:escola_id>/buscar-agentes/",
        DesignacaoAgenteSearchView.as_view(),
        name="buscar_agentes",
    ),
]
