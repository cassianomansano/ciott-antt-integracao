from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Optional


class TipoOperacao(IntEnum):
    LOTACAO = 1
    FRACIONADA = 2
    TAC_AGREGADO = 3


class TipoPagamento(IntEnum):
    IP = 1
    CONTA_CORRENTE = 2
    CONTA_POUPANCA = 3
    CONTA_PAGAMENTO = 4
    OUTROS = 5
    PIX = 6


class CodigoTipoCarga(IntEnum):
    GRANEL_SOLIDO = 1
    GRANEL_LIQUIDO = 2
    FRIGORIFICADA_AQUECIDA = 3
    CONTEINERIZADA = 4
    CARGA_GERAL = 5
    NEOGRANEL = 6
    PERIGOSA_GRANEL_SOLIDO = 7
    PERIGOSA_GRANEL_LIQUIDO = 8
    PERIGOSA_FRIGORIFICADA = 9
    PERIGOSA_CONTEINERIZADA = 10
    PERIGOSA_CARGA_GERAL = 11
    GRANEL_PRESSURIZADO = 12


# ── Inputs ────────────────────────────────────────────────────────────────────

@dataclass
class VeiculoInput:
    placa: str
    numero_eixos: str
    rntrc_veiculo: Optional[str] = None


@dataclass
class OrigemInput:
    codigo_municipio: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class DestinoInput:
    codigo_municipio: Optional[str] = None
    cep: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


@dataclass
class OrigemDestinoInput:
    origem: OrigemInput
    destino: DestinoInput
    distancia_percorrida: Optional[float] = None
    qtd_viagens: Optional[int] = None


@dataclass
class DadosCargaInput:
    codigo_natureza_carga: Optional[str] = None
    peso_carga: Optional[float] = None
    codigo_tipo_carga: Optional[int] = None
    contratantes_carga_frac: list[str] = field(default_factory=list)


@dataclass
class ParcelaInput:
    numero_parcela: int
    data_vencimento: str
    valor_parcela: float


@dataclass
class InfPagamentoInput:
    tipo_pagamento: TipoPagamento
    cpf_cnpj_creditado: str
    ind_pagamento: int
    codigo_instituicao_financeira: Optional[str] = None
    numero_agencia: Optional[str] = None
    numero_conta: Optional[str] = None
    chave_pix: Optional[str] = None
    codigo_pagamento: Optional[str] = None
    identificador_pix: Optional[str] = None
    parcelas: list[ParcelaInput] = field(default_factory=list)


@dataclass
class IndicadoresOperacionaisInput:
    ind_alto_desempenho: bool
    ind_retorno_vazio: bool
    composicao_veicular: bool


@dataclass
class DeclaracaoInput:
    tipo_operacao: TipoOperacao
    cpf_cnpj_contratado: str
    rntrc_contratado: str
    cpf_cnpj_contratante: str
    valor_frete: float
    data_inicio_viagem: str
    data_fim_viagem: str
    veiculos: list[VeiculoInput]
    inf_pagamento: list[InfPagamentoInput]
    id_operacao: Optional[str] = None
    rntrc_contratante: Optional[str] = None
    cpf_cnpj_destinatario: Optional[str] = None
    data_declaracao: Optional[str] = None
    ind_contingencia: bool = False
    justificativa_contingencia: Optional[str] = None
    origem_destino: list[OrigemDestinoInput] = field(default_factory=list)
    dados_carga: Optional[DadosCargaInput] = None
    indicadores_operacionais: Optional[IndicadoresOperacionaisInput] = None


@dataclass
class CancelamentoInput:
    codigo_identificacao_operacao: str
    motivo_cancelamento: str


@dataclass
class RetificacaoInput:
    codigo_identificacao_operacao: str
    valor_frete: Optional[float] = None
    data_fim_viagem: Optional[str] = None
    origem_destino: Optional[OrigemDestinoInput] = None
    dados_carga: Optional[DadosCargaInput] = None


@dataclass
class EncerramentoInput:
    codigo_identificacao_operacao: str
    origem_destino: list[OrigemDestinoInput] = field(default_factory=list)
    peso_carga: Optional[float] = None


# ── Outputs ───────────────────────────────────────────────────────────────────

@dataclass
class VeiculoStatus:
    placa_veiculo: str
    situacao_veiculo_frota_transportador: int


@dataclass
class SituacaoTransportadorResponse:
    cpf_cnpj_transportador: str
    rntrc_transportador: str
    nome_razao_social: str
    rntrc_ativo: bool
    tipo_transportador: str
    equiparado_tac: bool
    protocolo: str
    codigo: str
    mensagem: str


@dataclass
class FrotaTransportadorResponse:
    cpf_cnpj_transportador: str
    rntrc_transportador: str
    nome_razao_social: str
    rntrc_ativo: bool
    frota: list[VeiculoStatus]
    protocolo: str
    codigo: str
    mensagem: str


@dataclass
class DeclaracaoResponse:
    codigo_identificacao_operacao: str
    codigo_verificador: str
    protocolo: str
    codigo: str
    mensagem: str
    aviso_transportador: str = ""

    @property
    def ciot_completo(self) -> str:
        return self.codigo_identificacao_operacao + self.codigo_verificador


@dataclass
class CancelamentoResponse:
    codigo_identificacao_operacao: str
    data_cancelamento: str
    protocolo: str
    codigo: str
    mensagem: str


@dataclass
class RetificacaoResponse:
    codigo_identificacao_operacao: str
    data_retificacao: str
    protocolo: str
    codigo: str
    mensagem: str


@dataclass
class EncerramentoResponse:
    codigo_identificacao_operacao: str
    data_encerramento: str
    protocolo: str
    codigo: str
    mensagem: str


@dataclass
class CiotGeradoResponse:
    codigo_identificacao_operacao: str
    codigo_verificador: str
    protocolo: str
    codigo: str
    mensagem: str

    @property
    def ciot_completo(self) -> str:
        return self.codigo_identificacao_operacao + self.codigo_verificador


@dataclass
class ExcecaoResponse:
    esta_na_excecao: bool
    protocolo: str
    codigo: str
    mensagem: str
