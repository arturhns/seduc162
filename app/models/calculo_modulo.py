from django.db import models


class CalculoModulo(models.Model):
    escola = models.ForeignKey("app.Escola", on_delete=models.PROTECT)
    periodo = models.ForeignKey("app.PeriodoProcessamento", on_delete=models.PROTECT)
    matricula_ativa = models.IntegerField()
    data_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "calculos_modulo"
        constraints = [
            models.UniqueConstraint(fields=["escola", "periodo"], name="uk_escola_periodo"),
        ]

    def __str__(self) -> str:
        return f"Cálculo {self.escola} ({self.periodo})"
