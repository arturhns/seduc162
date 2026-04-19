from django.urls import path

from app.views.calculo_modulo import CalculoModuloListView, CalculoModuloView

app_name = "calculo_modulo"

urlpatterns = [
    path("", CalculoModuloListView.as_view(), name="list"),
    path("<int:escola_pk>/", CalculoModuloView.as_view(), name="form"),
]
