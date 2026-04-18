from collections import defaultdict

from django.core.paginator import Paginator
from django.db.models import Q
from django.views.generic import TemplateView

from app.models import CalculoModulo, CalculoQuantidade, Escola, PeriodoProcessamento


def _formato_cargos_calculados(quantidades):
    partes = []
    for cq in quantidades:
        rotulo = (cq.cargo.abreviacao or cq.cargo.nome).strip()
        partes.append(f"{cq.quantidade} {rotulo}")
    return ", ".join(partes)


class CalculoModuloListView(TemplateView):
    template_name = "calculo_modulo/list.html"
    paginate_by = 15

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        busca = (self.request.GET.get("q") or "").strip()

        escolas_qs = Escola.objects.order_by("nome")

        if busca:
            escolas_qs = escolas_qs.filter(
                Q(nome__icontains=busca) | Q(codigo_inep__icontains=busca)
            )

        paginator = Paginator(escolas_qs, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        escolas_pagina = page_obj.object_list  
        
        escola_ids = list(escolas_pagina.values_list("pk", flat=True))

        ultimo_por_escola = {}

        if periodo_ativo is not None and escolas_pagina:
            for calc in (
                CalculoModulo.objects.filter(
                    periodo=periodo_ativo,
                    escola__in=escola_ids, 
                )
                .order_by("escola_id", "-data_calculo")
                .iterator()
            ):
                # Pega apenas o mais recente por escola
                if calc.escola_id not in ultimo_por_escola:
                    ultimo_por_escola[calc.escola_id] = calc

        # Busca as quantidades apenas dos cálculos necessários
        calculo_ids = [c.pk for c in ultimo_por_escola.values()]
        quantidades_por_calculo = defaultdict(list)

        if calculo_ids:
            for cq in (
                CalculoQuantidade.objects.filter(calculo_modulo_id__in=calculo_ids)
                .select_related("cargo")
                .order_by("cargo__nome")
            ):
                quantidades_por_calculo[cq.calculo_modulo_id].append(cq)

        # Monta as linhas
        calculos = []

        for escola in escolas_pagina:
            ultimo = ultimo_por_escola.get(escola.pk)

            if ultimo:
                qts = quantidades_por_calculo.get(ultimo.pk, [])
                cargos_txt = _formato_cargos_calculados(qts) if qts else "--"
                matricula = ultimo.matricula_ativa
                processado = True
            else:
                cargos_txt = "--"
                matricula = None
                processado = False

            calculos.append(
                {
                    "escola": escola,
                    "matricula_ativa": matricula,
                    "cargos_calculados": cargos_txt,
                    "processado": processado,
                }
            )

        ctx.update({
            "periodo_ativo": periodo_ativo,
            "busca": busca,
            "paginator": paginator,
            "page_obj": page_obj,
            "is_paginated": page_obj.has_other_pages(),
            "calculos": calculos,
        })
        
        return ctx