from collections import defaultdict

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Prefetch, Q, Exists, OuterRef, Subquery
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
from app.services.calculo_modulo import CalculoModuloService


def _formato_cargos_calculados(quantidades):
    partes = []
    for cq in quantidades:
        rotulo = (cq.cargo.abreviacao or cq.cargo.nome).strip()
        partes.append(f"{cq.quantidade} {rotulo}")
    return ", ".join(partes)


def _tipos_modalidade_escola(escola: Escola) -> set[int]:
    return {int(em.modalidade_id) for em in escola.escolamodalidade_set.all()}


def _ultimo_calculo_para_exibicao(escola, periodo_ativo):
    """
    Retorna (último cálculo para prefill/resultados, cálculo salvo no período ativo).

    Prioridade do último exibido: (1) período ativo; (2) entre os marcados como
    vigentes (`ultimo_calculo`), o de `data_calculo` mais recente.
    """
    if periodo_ativo:
        calc_ativo = CalculoModulo.get_ultimo_calculo_periodo(escola, periodo_ativo)
        if calc_ativo:
            return calc_ativo

    return (
        CalculoModulo.objects.filter(escola=escola, ultimo_calculo=True)
        .order_by("-data_calculo")
        .first()
    )


def _botao_principal_label(escola, periodo_ativo) -> str:
    if periodo_ativo and CalculoModulo.get_ultimo_calculo_periodo(escola, periodo_ativo):
        return "Recalcular Módulo"
    return "Calcular Módulo"


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

    _STATUS_PROCESSAMENTO_TODOS = ""
    _STATUS_PROCESSAMENTO_PROCESSADO = "1"
    _STATUS_PROCESSAMENTO_PENDENTE = "0"
    _STATUS_PROCESSAMENTO_CHOICES = frozenset(
        {
            _STATUS_PROCESSAMENTO_TODOS,
            _STATUS_PROCESSAMENTO_PROCESSADO,
            _STATUS_PROCESSAMENTO_PENDENTE,
        }
    )

    _STATUS_DESIGNACAO_TODOS = ""
    _STATUS_DESIGNACAO_PENDENTE = "0"
    _STATUS_DESIGNACAO_EM_ANDAMENTO = "1"
    _STATUS_DESIGNACAO_CONCLUIDO = "2"
    _STATUS_DESIGNACAO_CHOICES = frozenset(
        {
            _STATUS_DESIGNACAO_TODOS,
            _STATUS_DESIGNACAO_PENDENTE,
            _STATUS_DESIGNACAO_EM_ANDAMENTO,
            _STATUS_DESIGNACAO_CONCLUIDO,
        }
    )

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()

        busca_escola_ou_inep = (self.request.GET.get("q") or "").strip()
        busca_status_processamento = (self.request.GET.get("status") or "").strip()
        busca_status_designacao = (self.request.GET.get("status_designacao") or "").strip()

        if busca_status_processamento not in self._STATUS_PROCESSAMENTO_CHOICES:
            busca_status_processamento = self._STATUS_PROCESSAMENTO_TODOS

        if busca_status_designacao not in self._STATUS_DESIGNACAO_CHOICES:
            busca_status_designacao = self._STATUS_DESIGNACAO_TODOS

        if periodo_ativo is None:
            escolas_qs = Escola.objects.none()
        else:
            escolas_qs = Escola.objects.order_by("nome")

            if busca_escola_ou_inep:
                escolas_qs = escolas_qs.filter(
                    Q(nome__icontains=busca_escola_ou_inep) | Q(codigo_inep__icontains=busca_escola_ou_inep)
                )

            if busca_status_processamento in (
                self._STATUS_PROCESSAMENTO_PROCESSADO,
                self._STATUS_PROCESSAMENTO_PENDENTE,
            ):
                calculo_existe = CalculoModulo.objects.filter(
                    escola_id=OuterRef("pk"), 
                    periodo=periodo_ativo,
                )

                if busca_status_processamento == self._STATUS_PROCESSAMENTO_PROCESSADO:
                    escolas_qs = escolas_qs.filter(Exists(calculo_existe))
                else:  
                    escolas_qs = escolas_qs.filter(~Exists(calculo_existe))

            if busca_status_designacao in (
                self._STATUS_DESIGNACAO_PENDENTE,
                self._STATUS_DESIGNACAO_EM_ANDAMENTO,
                self._STATUS_DESIGNACAO_CONCLUIDO,
            ):
                ultimo_status_sq = Subquery(
                    CalculoModulo.objects.filter(
                        escola_id=OuterRef("pk"),
                        periodo=periodo_ativo,
                        ultimo_calculo=True,
                    )
                    .order_by("-pk")
                    .values("status_designacao")[:1]
                )
                escolas_qs = escolas_qs.annotate(
                    _ultimo_status_designacao=ultimo_status_sq,
                ).filter(
                    _ultimo_status_designacao=busca_status_designacao,
                )

        paginator = Paginator(escolas_qs, self.paginate_by)
        page_obj = paginator.get_page(self.request.GET.get("page"))
        escolas_pagina = page_obj.object_list

        escola_ids = list(escolas_pagina.values_list("pk", flat=True))

        ultimo_por_escola = {}

        if periodo_ativo is not None and escolas_pagina:
            for calc in CalculoModulo.objects.filter(
                periodo=periodo_ativo,
                escola__in=escola_ids,
                ultimo_calculo=True,
            ):
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
                status_designacao = {
                    "label": ultimo.get_status_designacao_display(),
                    "value": ultimo.status_designacao,
                }
            else:
                cargos_txt = "--"
                matricula = None
                processado = False
                status_designacao = None

            calculos.append(
                {
                    "escola": escola,
                    "matricula_ativa": matricula,
                    "cargos_calculados": cargos_txt,
                    "processado": processado,
                    "status_designacao": status_designacao,
                }
            )

        ctx.update(
            {
                "periodo_ativo": periodo_ativo,
                "busca_escola_ou_inep": busca_escola_ou_inep,
                "busca_status_processamento": busca_status_processamento,
                "busca_status_designacao": busca_status_designacao,
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
        self.mostra_casa = Modalidade.TIPO_CASA in self.tipos_modalidade or Modalidade.TIPO_SISTEMA_PRISIONAL in self.tipos_modalidade
        self.mostra_cel = Modalidade.TIPO_CEL in self.tipos_modalidade
        return super().dispatch(request, *args, **kwargs)

    def _quantidades_e_explicacoes_para_ultimo(self, ultimo_calculo):
        if not ultimo_calculo:
            return [], []
        quantidades = list(
            CalculoQuantidade.objects.filter(calculo_modulo=ultimo_calculo)
            .select_related("cargo")
            .order_by("cargo__nome")
        )
        prof = ultimo_calculo.professores_dedicados if self.mostra_casa else None
        mat_cel = ultimo_calculo.matricula_cel if self.mostra_cel else None
        _, explicacoes = CalculoModuloService().calcular(
            self.escola,
            ultimo_calculo.matricula_ativa,
            ultimo_calculo.periodo,
            professores_dedicados=prof,
            matricula_cel=mat_cel,
        )
        return quantidades, explicacoes

    def get(self, request, *args, **kwargs):
        periodo_ativo = PeriodoProcessamento.get_periodo_ativo()
        ultimo_exibicao = _ultimo_calculo_para_exibicao(self.escola, periodo_ativo)
        initial = {}
        if ultimo_exibicao:
            initial["matricula_ativa"] = ultimo_exibicao.matricula_ativa
            if self.mostra_casa and ultimo_exibicao.professores_dedicados is not None:
                initial["professores_dedicados"] = ultimo_exibicao.professores_dedicados
            if self.mostra_cel and ultimo_exibicao.matricula_cel is not None:
                initial["matricula_cel"] = ultimo_exibicao.matricula_cel

        form = CalculoModuloInputForm(
            initial=initial,
            mostra_casa=self.mostra_casa,
            mostra_cel=self.mostra_cel,
        )
        quantidades, explicacoes = self._quantidades_e_explicacoes_para_ultimo(
            ultimo_exibicao
        )
        ctx = self._base_context(
            form,
            periodo_ativo=periodo_ativo,
            modo_resultado=False,
            quantidades=quantidades,
            explicacoes=explicacoes,
            diferencas_cargos=[],
            ultimo_calculo=ultimo_exibicao,
            botao_principal_label=_botao_principal_label(self.escola, periodo_ativo),
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
            ultimo_exibicao = _ultimo_calculo_para_exibicao(self.escola, None)
            q, ex = self._quantidades_e_explicacoes_para_ultimo(ultimo_exibicao)
            ctx = self._base_context(
                form,
                periodo_ativo=None,
                modo_resultado=False,
                quantidades=q,
                explicacoes=ex,
                diferencas_cargos=[],
                ultimo_calculo=ultimo_exibicao,
                botao_principal_label=_botao_principal_label(self.escola, None),
            )
            return TemplateResponse(self.request, self.template_name, ctx)

        ultimo = CalculoModulo.get_ultimo_calculo_periodo(self.escola, periodo_ativo)
        form = CalculoModuloInputForm(
            request.POST,
            mostra_casa=self.mostra_casa,
            mostra_cel=self.mostra_cel,
        )
        acao = request.POST.get("acao") or "calcular"

        if not form.is_valid():
            ultimo_exibicao = _ultimo_calculo_para_exibicao(
                self.escola, periodo_ativo
            )
            q, ex = self._quantidades_e_explicacoes_para_ultimo(ultimo_exibicao)
            ctx = self._base_context(
                form,
                periodo_ativo=periodo_ativo,
                modo_resultado=False,
                quantidades=q,
                explicacoes=ex,
                diferencas_cargos=[],
                ultimo_calculo=ultimo_exibicao,
                botao_principal_label=_botao_principal_label(
                    self.escola, periodo_ativo
                ),
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

        ultimo_exibicao = _ultimo_calculo_para_exibicao(self.escola, periodo_ativo)
        ctx = self._base_context(
            form,
            periodo_ativo=periodo_ativo,
            modo_resultado=True,
            quantidades=quantidades,
            explicacoes=explicacoes,
            diferencas_cargos=diferencas,
            ultimo_calculo=ultimo_exibicao,
            botao_principal_label=_botao_principal_label(self.escola, periodo_ativo),
        )
        return TemplateResponse(self.request, self.template_name, ctx)

    def _salvar(self, periodo, form, quantidades, prof, mat_cel):
        with transaction.atomic():
            # Recálculo: só um cálculo vigente por escola no período (demais perdem a marca).
            CalculoModulo.objects.filter(escola=self.escola, periodo=periodo).update(
                ultimo_calculo=False
            )
            calculo = CalculoModulo.objects.create(
                escola=self.escola,
                periodo=periodo,
                matricula_ativa=form.cleaned_data["matricula_ativa"],
                professores_dedicados=prof,
                matricula_cel=mat_cel,
                ultimo_calculo=True,
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
        return redirect("designacao:form", escola_id=self.escola.pk)

    def _base_context(
        self,
        form,
        *,
        periodo_ativo,
        modo_resultado,
        quantidades=None,
        explicacoes=None,
        diferencas_cargos=None,
        ultimo_calculo=None,
        botao_principal_label="Calcular Módulo",
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

        tem_calculo_salvo_periodo_ativo = False
        if periodo_ativo is not None:
            tem_calculo_salvo_periodo_ativo = (
                CalculoModulo.get_ultimo_calculo_periodo(self.escola, periodo_ativo)
                is not None
            )

        return {
            "escola": self.escola,
            "periodo_ativo": periodo_ativo,
            "form": form,
            "mostra_casa": self.mostra_casa,
            "mostra_cel": self.mostra_cel,
            "modo_resultado": modo_resultado,
            "ultimo_calculo": ultimo_calculo,
            "botao_principal_label": botao_principal_label,
            "quantidades": quantidades or [],
            "explicacoes": explicacoes or [],
            "diferencas_cargos": diferencas_cargos or [],
            "modalidades_escola_nomes": nomes_modalidade,
            "rotulos_pei_extra_topo": rotulos_pei_extra,
            "tem_calculo_salvo_periodo_ativo": tem_calculo_salvo_periodo_ativo,
        }
