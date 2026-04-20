from django import forms


class ContratacaoDesignacaoForm(forms.Form):
    situacao_aoe = forms.TypedChoiceField(
        label="Situação de Contratação de AOE",
        coerce=int,
        choices=((0, "Pendente"), (1, "Concluído")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    situacao_ase = forms.TypedChoiceField(
        label="Situação de Contratação de ASE",
        coerce=int,
        choices=((0, "Pendente"), (1, "Concluído")),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
