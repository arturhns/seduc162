from __future__ import annotations

from django import forms
from django.utils import timezone

from app.models import PeriodoProcessamento


class RelatorioDesignacaoFiltroForm(forms.Form):
    """Validação do período selecionado no relatório (apenas períodos já iniciados)."""

    periodo = forms.ModelChoiceField(
        queryset=PeriodoProcessamento.objects.none(),
        label="Período",
        required=True,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        hoje = timezone.now().date()
        self.fields["periodo"].queryset = PeriodoProcessamento.objects.filter(
            data_inicio__lte=hoje
        ).order_by("-data_inicio")
