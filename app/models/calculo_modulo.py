from django.db import models


class CalculoModulo(models.Model):
    escola = models.ForeignKey("app.Escola", on_delete=models.PROTECT)
    periodo = models.ForeignKey("app.PeriodoProcessamento", on_delete=models.PROTECT)
    matricula_ativa = models.IntegerField()
    data_calculo = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "calculos_modulo"

    def __str__(self) -> str:
        return f"Cálculo {self.escola} ({self.periodo})"

    @classmethod
    def get_ultimo_calculo(cls, escola, periodo):
        """Retorna o cálculo mais recente (maior data_calculo) para a escola/período."""
        if periodo is None:
            return None
        return (
            cls.objects.filter(escola=escola, periodo=periodo)
            .order_by("-data_calculo")
            .first()
        )
