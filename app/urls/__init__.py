from django.urls import path, include


app_name = ""

urlpatterns = [
    path("escolas/", include("app.urls.escolas", namespace="escolas")),
    path("agentes-escolares/", include("app.urls.agentes_escolares", namespace="agentes_escolares")),
    path(
        "periodos-processamento/",
        include("app.urls.periodos_processamento", namespace="periodos_processamento"),
    ),
    path(
        "calculo-modulo/",
        include("app.urls.calculo_modulo", namespace="calculo_modulo"),
    ),
    path("designacao/", include("app.urls.designacao", namespace="designacao")),
]