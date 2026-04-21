from django.urls import path

from app.views.relatorio import (
    PeriodoRelatorioAutocompleteView,
    RelatorioDesignacaoExportCsvView,
    RelatorioDesignacaoExportPdfView,
    RelatorioDesignacaoView,
)

app_name = "relatorios"

urlpatterns = [
    path("designacao/", RelatorioDesignacaoView.as_view(), name="designacao"),
    path(
        "designacao/periodos/autocomplete/",
        PeriodoRelatorioAutocompleteView.as_view(),
        name="designacao_periodo_autocomplete",
    ),
    path(
        "designacao/exportar/csv/",
        RelatorioDesignacaoExportCsvView.as_view(),
        name="designacao_export_csv",
    ),
    path(
        "designacao/exportar/pdf/",
        RelatorioDesignacaoExportPdfView.as_view(),
        name="designacao_export_pdf",
    ),
]
