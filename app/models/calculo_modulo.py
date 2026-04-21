from django.db import models


class CalculoModulo(models.Model):
    escola = models.ForeignKey("app.Escola", on_delete=models.PROTECT)
    periodo = models.ForeignKey("app.PeriodoProcessamento", on_delete=models.PROTECT)
    matricula_ativa = models.IntegerField()
    professores_dedicados = models.PositiveSmallIntegerField(null=True, blank=True, default=None)
    matricula_cel = models.PositiveIntegerField(null=True, blank=True, default=None)
    data_calculo = models.DateTimeField(auto_now_add=True)
    status_designacao = models.PositiveSmallIntegerField(
        choices=[
            (0, "Pendente"),
            (1, "Em andamento"),
            (2, "Concluído"),
        ],
        default=0,
        verbose_name="Status da Designação",
    )
    # Um único True por (escola, período): marca o cálculo vigente; recálculos zeram os demais da mesma escola no período.
    ultimo_calculo = models.BooleanField(default=False, verbose_name="Último Cálculo")

    class Meta:
        db_table = "calculos_modulo"

    def __str__(self) -> str:
        return f"Cálculo {self.escola} ({self.periodo})"

    @classmethod
    def get_ultimo_calculo_periodo(cls, escola, periodo):
        """Retorna o cálculo vigente da escola no período (campo `ultimo_calculo=True`)."""
        if periodo is None:
            return None
        return (
            cls.objects.filter(escola=escola, periodo=periodo, ultimo_calculo=True)
            .order_by("-pk")
            .first()
        )
