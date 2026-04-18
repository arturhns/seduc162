from django.db import models
from django.utils import timezone


class PeriodoProcessamento(models.Model):
    data_inicio = models.DateField()
    data_fim = models.DateField()
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "periodos_processamento"
        ordering = ["-data_inicio"]

    def __str__(self) -> str:
        return f"{self.data_inicio} a {self.data_fim}"

    @property
    def esta_ativo(self) -> bool:
        hoje = timezone.now().date()
        return self.data_inicio <= hoje <= self.data_fim

    @classmethod
    def get_periodo_ativo(self):
        """Retorna o período ativo atual ou None."""
        hoje = timezone.now().date()
        return (
            self.objects.filter(data_inicio__lte=hoje, data_fim__gte=hoje)
            .order_by("data_inicio")
            .first()
        )
