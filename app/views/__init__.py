from .agente_escolar import (
    AgenteEscolarCreateView,
    AgenteEscolarDeleteView,
    AgenteEscolarDetailView,
    AgenteEscolarListView,
    AgenteEscolarUpdateView,
)
from .escola import (
    EscolaCreateView,
    EscolaDeleteView,
    EscolaDetailView,
    EscolaListView,
    EscolaUpdateView,
)
from .calculo_modulo import CalculoModuloListView, CalculoModuloView
from .periodo_processamento import (
    PeriodoProcessamentoCreateView,
    PeriodoProcessamentoDeleteView,
    PeriodoProcessamentoDetailView,
    PeriodoProcessamentoListView,
    PeriodoProcessamentoUpdateView,
)

__all__ = [
    "AgenteEscolarListView",
    "AgenteEscolarCreateView",
    "AgenteEscolarUpdateView",
    "AgenteEscolarDetailView",
    "AgenteEscolarDeleteView",
    "EscolaListView",
    "EscolaCreateView",
    "EscolaUpdateView",
    "EscolaDetailView",
    "EscolaDeleteView",
    "PeriodoProcessamentoListView",
    "PeriodoProcessamentoCreateView",
    "PeriodoProcessamentoUpdateView",
    "PeriodoProcessamentoDetailView",
    "PeriodoProcessamentoDeleteView",
    "CalculoModuloListView",
    "CalculoModuloView",
]
