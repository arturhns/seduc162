from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from app.forms import PeriodoProcessamentoForm
from app.models import PeriodoProcessamento


class PeriodoProcessamentoListView(ListView):
    model = PeriodoProcessamento
    template_name = "periodos_processamento/list.html"
    context_object_name = "periodos_processamento"
    paginate_by = 10

    def get_queryset(self):
        return super().get_queryset().order_by("-data_inicio")


class PeriodoProcessamentoCreateView(CreateView):
    model = PeriodoProcessamento
    form_class = PeriodoProcessamentoForm
    template_name = "periodos_processamento/form.html"
    success_url = reverse_lazy("periodos_processamento:list")


class PeriodoProcessamentoUpdateView(UpdateView):
    model = PeriodoProcessamento
    form_class = PeriodoProcessamentoForm
    template_name = "periodos_processamento/form.html"
    success_url = reverse_lazy("periodos_processamento:list")


class PeriodoProcessamentoDetailView(DetailView):
    model = PeriodoProcessamento
    template_name = "periodos_processamento/detail.html"
    context_object_name = "periodo_processamento"


class PeriodoProcessamentoDeleteView(DeleteView):
    model = PeriodoProcessamento
    template_name = "periodos_processamento/confirm_delete.html"
    success_url = reverse_lazy("periodos_processamento:list")
