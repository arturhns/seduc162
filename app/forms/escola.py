from django import forms

from app.models import Escola, EscolaModalidade, Modalidade
from django.db.models import Case, When, IntegerField


class EscolaForm(forms.ModelForm):
    TIPO_CHOICES = (
        (0, "Centralizada"),
        (1, "Terceirizada"),
        (2, "Descentralizada"),
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
            "professores_dedicados",
        ]
        labels = {
            "codigo_inep": "Código INEP",
            "nome": "Nome",
            "numero_turnos": "Número de turnos",
            "tipo_merenda": "Tipo de merenda",
            "tipo_limpeza": "Tipo de limpeza",
            "professores_dedicados": "Professores dedicados",
        }
        widgets = {
            "codigo_inep": forms.TextInput(attrs={"class": "form-control"}),
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "professores_dedicados": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["numero_turnos"] = forms.TypedChoiceField(
            label="Número de turnos",
            choices=self.NUMERO_TURNOS_CHOICES,
            coerce=int,
            initial=1,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        self.fields["tipo_merenda"] = forms.TypedChoiceField(
            label="Tipo de merenda",
            choices=self.TIPO_CHOICES,
            coerce=int,
            initial=0,
            widget=forms.Select(attrs={"class": "form-select"}),
        )

        self.fields["tipo_limpeza"] = forms.TypedChoiceField(
            label="Tipo de limpeza",
            choices=self.TIPO_CHOICES,
            coerce=int,
            initial=0,
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
            self.fields["tipo_merenda"].initial = self.instance.tipo_merenda
            self.fields["tipo_limpeza"].initial = self.instance.tipo_limpeza

    def save(self, commit=True):
        escola = super().save(commit=commit)
        if commit:
            modalidades = self.cleaned_data.get("modalidades") or []
            EscolaModalidade.objects.filter(escola=escola).delete()
            EscolaModalidade.objects.bulk_create(
                [EscolaModalidade(escola=escola, modalidade=m) for m in modalidades]
            )
        return escola
