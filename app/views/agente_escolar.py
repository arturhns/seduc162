from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from app.models import AgenteEscolar

from app.forms import AgenteEscolarForm


class AgenteEscolarListView(ListView):
    model = AgenteEscolar
    template_name = "agentes_escolares/list.html"
    context_object_name = "agentes"
    paginate_by = 15

    def get_queryset(self):
        queryset = super().get_queryset().order_by("nome_completo")
        search = self.request.GET.get("q", "").strip()
        if search:
            queryset = queryset.filter(nome_completo__icontains=search)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["search"] = self.request.GET.get("q", "").strip()
        return context


class AgenteEscolarCreateView(CreateView):
    model = AgenteEscolar
    form_class = AgenteEscolarForm
    template_name = "agentes_escolares/form.html"
    success_url = reverse_lazy("agentes_escolares:list")


class AgenteEscolarUpdateView(UpdateView):
    model = AgenteEscolar
    form_class = AgenteEscolarForm
    template_name = "agentes_escolares/form.html"
    success_url = reverse_lazy("agentes_escolares:list")


class AgenteEscolarDetailView(DetailView):
    model = AgenteEscolar
    template_name = "agentes_escolares/detail.html"
    context_object_name = "agente"


class AgenteEscolarDeleteView(DeleteView):
    model = AgenteEscolar
    template_name = "agentes_escolares/confirm_delete.html"
    success_url = reverse_lazy("agentes_escolares:list")
