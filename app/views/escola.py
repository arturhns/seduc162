from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from app.forms import EscolaForm
from app.models import Escola


class EscolaListView(ListView):
    model = Escola
    template_name = "escolas/list.html"
    context_object_name = "escolas"
    paginate_by = 15

    def get_queryset(self):
        queryset = (
            super()
            .get_queryset()
            .prefetch_related("escolamodalidade_set__modalidade")
            .order_by("nome")
        )
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(
                Q(nome__icontains=search) | Q(codigo_inep__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("q", "").strip()
        return context


class EscolaCreateView(CreateView):
    model = Escola
    form_class = EscolaForm
    template_name = "escolas/form.html"
    success_url = reverse_lazy("escolas:list")


class EscolaUpdateView(UpdateView):
    model = Escola
    form_class = EscolaForm
    template_name = "escolas/form.html"
    success_url = reverse_lazy("escolas:list")


class EscolaDetailView(DetailView):
    model = Escola
    template_name = "escolas/detail.html"
    context_object_name = "escola"

    def get_queryset(self):
        return super().get_queryset().prefetch_related("escolamodalidade_set__modalidade")


class EscolaDeleteView(DeleteView):
    model = Escola
    template_name = "escolas/confirm_delete.html"
    success_url = reverse_lazy("escolas:list")
