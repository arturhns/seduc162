from django import forms


class CalculoModuloInputForm(forms.Form):
    """Entradas para simulação do cálculo do módulo (Resolução SEDUC 162/2025)."""

    matricula_ativa = forms.IntegerField(
        label="Matrícula ativa",
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control", "min": 1}),
    )

    def __init__(self, *args, mostra_casa: bool = False, mostra_cel: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        if mostra_casa:
            self.fields["professores_dedicados"] = forms.IntegerField(
                label="Professores dedicados",
                min_value=0,
                required=False,
                widget=forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            )
        if mostra_cel:
            self.fields["matricula_cel"] = forms.IntegerField(
                label="Matrícula CEL",
                min_value=0,
                required=False,
                widget=forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            )
