from collections import defaultdict

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.views import View
from django.views.generic import TemplateView

from app.forms import CalculoModuloInputForm
from app.models import (
    CalculoModulo,
    CalculoQuantidade,
    Escola,
    EscolaModalidade,
    Modalidade,
    PeriodoProcessamento,
)
from app.services.calculo_modulo_service import CalculoModuloService


def _formato_cargos_calculados(quantidades):
    partes = []
    for cq in quantidades:
        rotulo = (cq.cargo.abreviacao or cq.cargo.nome).strip()
        partes.append(f"{cq.quantidade} {rotulo}")
    return ", ".join(partes)


def _tipos_modalidade_escola(escola: Escola) -> set[int]:
    return {int(em.modalidade_id) for em in escola.escolamodalidade_set.all()}


def _diferencas_quantidades(anterior_qs, novo_qs):
    """Lista de dicts com cargo, anterior, novo, delta (somente onde houve mudança)."""
    ant = {q.cargo_id: q for q in anterior_qs}
    nov = {q.cargo_id: q for q in novo_qs}
    ids = sorted(set(ant) | set(nov), key=lambda cid: (ant.get(cid) or nov.get(cid)).cargo.tipo)
    out = []
    for cid in ids:
        q_old = ant.get(cid)
        q_new = nov.get(cid)
        a = q_old.quantidade if q_old else 0
        n = q_new.quantidade if q_new else 0
        if a != n:
            cargo = (q_new or q_old).cargo
            out.append({"cargo": cargo, "anterior": a, "novo": n, "delta": n - a})
    return out


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
                if calc.escola_id not in ultimo_por_escola:
                    ultimo_por_escola[calc.escola_id] = calc

        calculo_ids = [c.pk for c in ultimo_por_escola.values()]
        quantidades_por_calculo = defaultdict(list)

        if calculo_ids:
            for cq in (
                CalculoQuantidade.objects.filter(calculo_modulo_id__in=calculo_ids)
                .select_related("cargo")
                .order_by("cargo__nome")
            ):
                quantidades_por_calculo[cq.calculo_modulo_id].append(cq)

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

        ctx.update(
            {
                "periodo_ativo": periodo_ativo,
                "busca": busca,
                "paginator": paginator,
                "page_obj": page_obj,
                "is_paginated": page_obj.has_other_pages(),
                "calculos": calculos,
            }
        )

        return ctx


class CalculoModuloView(View):
    """GET: formulário; POST: calcular/recalcular (pré-visualização) ou salvar no banco."""

    template_name = "calculo_modulo/form.html"

    def dispatch(self, request, *args, **kwargs):
        self.escola = get_object_or_404(
            Escola.objects.prefetch_related(
                Prefetch(
                    "escolamodalidade_set",
                    queryset=EscolaModalidade.objects.select_related("modalidade"),
                )
            ),
            pk=kwargs["escola_pk"],
        )
        self.tipos_modalidade = _tipos_modalidade_escola(self.escola)
        self.mostra_casa = Modalidade.TIPO_CASA in self.tipos_modalidade
        self.mostra_cel = Modalidade.TIPO_CEL in self.tipos_modalidade
        return super().dispatch(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        ultimo = (
            CalculoModulo.get_ultimo_calculo(self.escola, periodo_ativo)
            if periodo_ativo
            else None
        )
        initial = {}
        if ultimo:
            initial["matricula_ativa"] = ultimo.matricula_ativa
            if self.mostra_casa and ultimo.professores_dedicados is not None:
                initial["professores_dedicados"] = ultimo.professores_dedicados
            if self.mostra_cel and ultimo.matricula_cel is not None:
                initial["matricula_cel"] = ultimo.matricula_cel

        form = CalculoModuloInputForm(
            initial=initial,
            mostra_casa=self.mostra_casa,
            mostra_cel=self.mostra_cel,
        )
        ctx = self._base_context(
            form,
            periodo_ativo=periodo_ativo,
            tem_calculo_anterior=bool(ultimo),
            modo_resultado=False,
        )
        return TemplateResponse(self.request, self.template_name, ctx)

    def post(self, request, *args, **kwargs):
        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        if periodo_ativo is None:
            form = CalculoModuloInputForm(
                request.POST,
                mostra_casa=self.mostra_casa,
                mostra_cel=self.mostra_cel,
            )
            ctx = self._base_context(
                form,
                periodo_ativo=None,
                tem_calculo_anterior=False,
                modo_resultado=False,
            )
            return TemplateResponse(self.request, self.template_name, ctx)

        ultimo = CalculoModulo.get_ultimo_calculo(self.escola, periodo_ativo)
        form = CalculoModuloInputForm(
            request.POST,
            mostra_casa=self.mostra_casa,
            mostra_cel=self.mostra_cel,
        )
        acao = request.POST.get("acao") or "calcular"

        if not form.is_valid():
            ctx = self._base_context(
                form,
                periodo_ativo=periodo_ativo,
                tem_calculo_anterior=bool(ultimo),
                modo_resultado=False,
            )
            return TemplateResponse(self.request, self.template_name, ctx)

        prof = (
            form.cleaned_data.get("professores_dedicados")
            if self.mostra_casa
            else None
        )
        mat_cel = form.cleaned_data.get("matricula_cel") if self.mostra_cel else None

        service = CalculoModuloService()
        quantidades, explicacoes = service.calcular(
            self.escola,
            form.cleaned_data["matricula_ativa"],
            periodo_ativo,
            professores_dedicados=prof,
            matricula_cel=mat_cel,
        )

        if acao == "salvar":
            return self._salvar(
                periodo_ativo,
                form,
                quantidades,
                prof,
                mat_cel,
            )

        anterior_qs = []
        if ultimo:
            anterior_qs = list(
                CalculoQuantidade.objects.filter(calculo_modulo=ultimo).select_related(
                    "cargo"
                )
            )
        diferencas = (
            _diferencas_quantidades(anterior_qs, quantidades) if anterior_qs else []
        )

        ctx = self._base_context(
            form,
            periodo_ativo=periodo_ativo,
            tem_calculo_anterior=bool(ultimo),
            modo_resultado=True,
            quantidades=quantidades,
            explicacoes=explicacoes,
            diferencas_cargos=diferencas,
        )
        return TemplateResponse(self.request, self.template_name, ctx)

    def _salvar(self, periodo, form, quantidades, prof, mat_cel):
        with transaction.atomic():
            calculo = CalculoModulo.objects.create(
                escola=self.escola,
                periodo=periodo,
                matricula_ativa=form.cleaned_data["matricula_ativa"],
                professores_dedicados=prof,
                matricula_cel=mat_cel,
            )
            CalculoQuantidade.objects.bulk_create(
                [
                    CalculoQuantidade(
                        calculo_modulo=calculo,
                        cargo=q.cargo,
                        quantidade=q.quantidade,
                    )
                    for q in quantidades
                ]
            )
        messages.success(self.request, "Cálculo salvo com sucesso.")
        return redirect("calculo_modulo:form", escola_pk=self.escola.pk)

    def _base_context(
        self,
        form,
        *,
        periodo_ativo,
        tem_calculo_anterior,
        modo_resultado,
        quantidades=None,
        explicacoes=None,
        diferencas_cargos=None,
    ):
        nomes_modalidade = sorted(
            {
                (em.modalidade.nome or "").strip()
                for em in self.escola.escolamodalidade_set.all()
                if (em.modalidade.nome or "").strip()
            }
        )
        rotulos_pei_extra = []
        if Modalidade.TIPO_PEI in self.tipos_modalidade:
            if getattr(self.escola, "pei_turno_diverso_tempo_parcial", False):
                rotulos_pei_extra.append("PEI + Parcial")
            if getattr(self.escola, "pei_nove_horas", False):
                rotulos_pei_extra.append("PEI 9h")

        return {
            "escola": self.escola,
            "periodo_ativo": periodo_ativo,
            "form": form,
            "mostra_casa": self.mostra_casa,
            "mostra_cel": self.mostra_cel,
            "tem_calculo_anterior": tem_calculo_anterior,
            "modo_resultado": modo_resultado,
            "quantidades": quantidades or [],
            "explicacoes": explicacoes or [],
            "diferencas_cargos": diferencas_cargos or [],
            "modalidades_escola_nomes": nomes_modalidade,
            "rotulos_pei_extra_topo": rotulos_pei_extra,
        }
