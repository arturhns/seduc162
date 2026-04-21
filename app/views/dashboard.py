from __future__ import annotations

from django.db.models import Count, Exists, OuterRef, Subquery
from django.views.generic import TemplateView

from app.models import CalculoModulo, Cargo, Designacao, Escola, PeriodoProcessamento


def _ids_ultimos_calculos_no_periodo(periodo: PeriodoProcessamento) -> list[int]:
    # Cálculo vigente por escola no período (`ultimo_calculo`).
    return list(
        CalculoModulo.objects.filter(periodo=periodo, ultimo_calculo=True).values_list(
            "pk", flat=True
        )
    )


class DashboardView(TemplateView):
    template_name = "dashboard/index.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        tem_algum_periodo = PeriodoProcessamento.objects.exists()
        if not tem_algum_periodo:
            ctx.update(
                {
                    "sem_periodo_cadastrado": True,
                    "periodo_ref": None,
                    "periodo_eh_ativo": False,
                }
            )
            return ctx

        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        periodo_ref = periodo_ativo or PeriodoProcessamento.objects.order_by("-data_inicio").first()
        periodo_eh_ativo = periodo_ativo is not None and periodo_ref.pk == periodo_ativo.pk

        total_escolas = Escola.objects.count()

        calculo_no_periodo = CalculoModulo.objects.filter(
            escola_id=OuterRef("pk"),
            periodo=periodo_ref,
        )
        escolas_com_calculo = Escola.objects.filter(Exists(calculo_no_periodo)).count()
        modulos_pendentes = max(0, total_escolas - escolas_com_calculo)

        ultimo_status_sq = Subquery(
            CalculoModulo.objects.filter(
                escola_id=OuterRef("pk"),
                periodo=periodo_ref,
                ultimo_calculo=True,
            )
            .order_by("-pk")
            .values("status_designacao")[:1]
        )
        designacoes_pendentes = (
            Escola.objects.annotate(
                _ultimo_status_designacao=ultimo_status_sq,
                _tem_calculo_periodo=Exists(calculo_no_periodo),
            )
            .filter(_tem_calculo_periodo=True, _ultimo_status_designacao=0)
            .count()
        )

        ids_ultimos = _ids_ultimos_calculos_no_periodo(periodo_ref)
        tipos_chart = (
            Cargo.TIPO_DIRETOR,
            Cargo.TIPO_VICE_DIRETOR,
            Cargo.TIPO_CGP,
            Cargo.TIPO_CGPG,
        )
        rotulos_por_tipo = {
            Cargo.TIPO_DIRETOR: "Diretor",
            Cargo.TIPO_VICE_DIRETOR: "Vice-Diretor",
            Cargo.TIPO_CGP: "CGP",
            Cargo.TIPO_CGPG: "CGPG",
        }
        contagens_por_tipo = {t: 0 for t in tipos_chart}
        if ids_ultimos:
            rows = (
                Designacao.objects.filter(
                    calculo_modulo_id__in=ids_ultimos,
                    status=1,
                    cargo_id__in=tipos_chart,
                )
                .values("cargo_id")
                .annotate(total=Count("id"))
            )
            for row in rows:
                contagens_por_tipo[int(row["cargo_id"])] = int(row["total"])

        chart_labels = [rotulos_por_tipo[t] for t in tipos_chart]
        chart_values = [contagens_por_tipo[t] for t in tipos_chart]

        ctx.update(
            {
                "sem_periodo_cadastrado": False,
                "periodo_ref": periodo_ref,
                "periodo_eh_ativo": periodo_eh_ativo,
                "total_escolas": total_escolas,
                "modulos_calculados": escolas_com_calculo,
                "modulos_pendentes": modulos_pendentes,
                "designacoes_pendentes": designacoes_pendentes,
                "chart_labels": chart_labels,
                "chart_values": chart_values,
            }
        )
        return ctx
