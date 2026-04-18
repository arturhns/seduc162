from datetime import timedelta

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from app.models import PeriodoProcessamento


class PeriodoProcessamentoForm(forms.ModelForm):
    class Meta:
        model = PeriodoProcessamento
        fields = ["data_inicio", "data_fim"]
        labels = {
            "data_inicio": "Data de início",
            "data_fim": "Data de fim",
        }
        widgets = {
            "data_inicio": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
            "data_fim": forms.DateInput(attrs={"class": "form-control", "type": "date"}, format="%Y-%m-%d"),
        }

    def clean_data_inicio(self):
        data_inicio = self.cleaned_data.get("data_inicio")
        if data_inicio is None:
            return data_inicio
        hoje = timezone.now().date()
        if data_inicio < hoje:
            raise ValidationError("A data de início não pode ser anterior à data atual.")
        return data_inicio

    def clean_data_fim(self):
        data_fim = self.cleaned_data.get("data_fim")
        data_inicio = self.cleaned_data.get("data_inicio")
        if data_fim is None or data_inicio is None:
            return data_fim
        if data_fim < data_inicio + timedelta(days=1):
            raise ValidationError(
                "A data de fim deve ser pelo menos um dia posterior à data de início."
            )
        return data_fim

    def clean(self):
        cleaned = super().clean()
        data_inicio = cleaned.get("data_inicio")
        data_fim = cleaned.get("data_fim")
        if data_inicio is None or data_fim is None:
            return cleaned

        qs = PeriodoProcessamento.objects.filter(
            data_inicio__lte=data_fim, data_fim__gte=data_inicio
        )
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError(
                "Este intervalo se sobrepõe a outro período de processamento já cadastrado."
            )
        return cleaned
