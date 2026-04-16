from django.db import models


class AgenteEscolar(models.Model):
    nome_completo = models.CharField(max_length=150)
    matricula_funcional = models.CharField(max_length=30, unique=True)
    status = models.PositiveSmallIntegerField(default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "agentes_escolares"
        verbose_name = "Agente escolar"
        verbose_name_plural = "Agentes escolares"

    def __str__(self) -> str:
        return f"{self.nome_completo} ({self.matricula_funcional})"
