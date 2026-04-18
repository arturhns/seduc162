from django import forms

from app.models import Escola, EscolaModalidade, Modalidade
from django.db.models import Case, When, IntegerField


class EscolaForm(forms.ModelForm):
    MERENDA_CHOICES = (
        (Escola.MERENDA_CENTRALIZADA, "Centralizada"),
        (Escola.MERENDA_TERCEIRIZADA, "Terceirizada"),
        (Escola.MERENDA_DESCENTRALIZADA, "Descentralizada"),
    )

    LIMPEZA_CHOICES = (
        (Escola.LIMPEZA_CENTRALIZADA, "Centralizada"),
        (Escola.LIMPEZA_TERCEIRIZADA, "Terceirizada"),
        (Escola.LIMPEZA_DESCENTRALIZADA, "Descentralizada"),
    )

    NUMERO_TURNOS_CHOICES = (
        (1, "1"),
        (2, "2"),
        (3, "3"),
    )

    modalidades = forms.ModelMultipleChoiceField(
        label="Modalidades",
        queryset=Modalidade.objects.all().order_by("nome"),
        required=False,
        widget=forms.CheckboxSelectMultiple(attrs={"class": "form-check-input"}),
    )

    class Meta:
        model = Escola
        fields = [
            "codigo_inep",
            "nome",
            "numero_turnos",
            "tipo_merenda",
            "tipo_limpeza",
            "pei_turno_diverso_tempo_parcial",
            "pei_nove_horas",
        ]
        labels = {
            "codigo_inep": "Código INEP",
            "nome": "Nome",
            "numero_turnos": "Número de turnos",
            "tipo_merenda": "Tipo de merenda",
            "tipo_limpeza": "Tipo de limpeza",
            "pei_turno_diverso_tempo_parcial": "PEI - Turno diverso / Tempo parcial",
            "pei_nove_horas": "PEI - 9 horas",
        }
        widgets = {
            "codigo_inep": forms.TextInput(attrs={"class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "pei_turno_diverso_tempo_parcial": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
            "pei_nove_horas": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.pei_modalidade_id = Modalidade.TIPO_PEI

        self.fields["numero_turnos"] = forms.TypedChoiceField(
            label="Número de turnos",
            choices=self.NUMERO_TURNOS_CHOICES,
            coerce=int,
            initial=1,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        self.fields["tipo_merenda"] = forms.TypedChoiceField(
            label="Tipo de merenda",
            choices=self.MERENDA_CHOICES,
            coerce=int,
            initial=Escola.MERENDA_CENTRALIZADA,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        self.fields["tipo_limpeza"] = forms.TypedChoiceField(
            label="Tipo de limpeza",
            choices=self.LIMPEZA_CHOICES,
            coerce=int,
            initial=Escola.LIMPEZA_CENTRALIZADA,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        # Força "Regular" sempre no topo
        self.fields['modalidades'].queryset = Modalidade.objects.annotate(
            ordem=Case(
                When(id=Modalidade.TIPO_REGULAR, then=0),
                default=1,
                output_field=IntegerField(),
            )
        ).order_by('ordem', 'nome')

        if self.instance.pk:
            self.fields["modalidades"].initial = Modalidade.objects.filter(
                escolamodalidade__escola=self.instance
            ).distinct()

            self.fields["numero_turnos"].initial = self.instance.numero_turnos
            merenda = int(self.instance.tipo_merenda or 0)
            limpeza = int(self.instance.tipo_limpeza or 0)
            self.fields["tipo_merenda"].initial = (
                merenda if merenda in dict(self.MERENDA_CHOICES) else Escola.MERENDA_CENTRALIZADA
            )
            self.fields["tipo_limpeza"].initial = (
                limpeza if limpeza in dict(self.LIMPEZA_CHOICES) else Escola.LIMPEZA_CENTRALIZADA
            )

    def save(self, commit=True):
        escola = super().save(commit=commit)
        if commit:
            modalidades = self.cleaned_data.get("modalidades") or []
            EscolaModalidade.objects.filter(escola=escola).delete()
            EscolaModalidade.objects.bulk_create(
                [EscolaModalidade(escola=escola, modalidade=m) for m in modalidades]
            )
        return escola
