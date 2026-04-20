from django.contrib import admin

from .models import (
    AgenteEscolar,
    CalculoModulo,
    CalculoQuantidade,
    Cargo,
    ContratacaoTerceiro,
    Designacao,
    Escola,
    EscolaModalidade,
    Modalidade,
    PeriodoProcessamento,
)


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ("codigo_inep", "nome", "numero_turnos", "ultimo_calculo_modulo")
    search_fields = ("codigo_inep", "nome")


@admin.register(Modalidade)
class ModalidadeAdmin(admin.ModelAdmin):
    list_display = ("nome",)


@admin.register(EscolaModalidade)
class EscolaModalidadeAdmin(admin.ModelAdmin):
    list_display = ("escola", "modalidade")
    list_select_related = ("escola", "modalidade")


@admin.register(PeriodoProcessamento)
class PeriodoProcessamentoAdmin(admin.ModelAdmin):
    list_display = ("data_inicio", "data_fim", "criado_em")


@admin.register(Cargo)
class CargoAdmin(admin.ModelAdmin):
    list_display = ("nome", "abreviacao", "tipo")
    list_filter = ("tipo",)
    search_fields = ("nome", "abreviacao")


@admin.register(CalculoModulo)
class CalculoModuloAdmin(admin.ModelAdmin):
    list_display = ("escola", "periodo", "matricula_ativa", "data_calculo")
    list_select_related = ("escola", "periodo")


@admin.register(CalculoQuantidade)
class CalculoQuantidadeAdmin(admin.ModelAdmin):
    list_display = ("calculo_modulo", "cargo", "quantidade")
    list_select_related = ("calculo_modulo", "cargo")


@admin.register(AgenteEscolar)
class AgenteEscolarAdmin(admin.ModelAdmin):
    list_display = ("nome_completo", "matricula_funcional", "status", "criado_em")
    search_fields = ("nome_completo", "matricula_funcional")
    list_filter = ("status",)


@admin.register(Designacao)
class DesignacaoAdmin(admin.ModelAdmin):
    list_display = ("calculo_modulo", "cargo", "agente", "data_designacao", "status")
    list_filter = ("status",)
    list_select_related = ("calculo_modulo", "cargo", "agente")


@admin.register(ContratacaoTerceiro)
class ContratacaoTerceiroAdmin(admin.ModelAdmin):
    list_display = ("calculo_modulo", "tipo", "situacao")
    list_filter = ("tipo", "situacao")
    list_select_related = ("calculo_modulo",)
