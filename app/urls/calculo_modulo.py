from django.urls import path

from app.views.calculo_modulo import CalculoModuloListView

app_name = "calculo_modulo"

urlpatterns = [
    path("", CalculoModuloListView.as_view(), name="list"),
]
