from __future__ import annotations
import random
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

# Servidor ANTT exige DataDeclaracao no fuso de Brasília (UTC-3) com offset
# explícito. Sem offset ou em UTC, rejeita com "fora do intervalo de tolerância".
_TZ_BRT = timezone(timedelta(hours=-3))

import requests

from ._auth import build_mtls_session
from .exceptions import CiotApiError, CiotAuthError, CiotValidationError
from .models import (
    CancelamentoInput, CancelamentoResponse,
    DeclaracaoInput, DeclaracaoResponse,
    EncerramentoInput, EncerramentoResponse,
    ExcecaoResponse,
    FrotaTransportadorResponse,
    CiotGeradoResponse,
    RetificacaoInput, RetificacaoResponse,
    SituacaoTransportadorResponse,
    VeiculoStatus,
)
from .storage import CiotStorage

_BASE_URLS = {
    "homologacao": "https://appservices-hml.antt.gov.br/pefServices/api",
    "producao": "https://appservices.antt.gov.br/pefServices/api",
}

_CODIGOS_SUCESSO = {"000000", "110", "111"}


class CiotClient:
    def __init__(
        self,
        cert_pfx: str,
        cert_password: str,
        cnpj_interessado: str,
        env: str = "homologacao",
        db_path: str = "ciot_operacoes.db",
        dll_geradorciot_dir: Optional[str] = None,
    ):
        if env not in _BASE_URLS:
            raise ValueError(f"env deve ser 'homologacao' ou 'producao', recebido: {env!r}")
        self._session = build_mtls_session(cert_pfx, cert_password)
        self._base_url = _BASE_URLS[env]
        self.cnpj_interessado = _validar_cpf_cnpj(cnpj_interessado)
        self.storage = CiotStorage(db_path)
        # Caminho opcional para a DLL GeradorCIOTShared.dll. Quando informado,
        # IdOperacaoTransporte é gerado via DLL (regra B16 da ANTT) em vez do
        # fallback timestamp.
        self.dll_geradorciot_dir = dll_geradorciot_dir

    # ── Utilitários internos ──────────────────────────────────────────────────

    def _post(self, endpoint: str, payload: dict) -> dict:
        url = f"{self._base_url}/{endpoint}"
        try:
            resp = self._session.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.SSLError as e:
            raise CiotAuthError(f"Falha mTLS — verifique certificado e cadastro na ANTT: {e}") from e
        except requests.exceptions.HTTPError as e:
            raise CiotApiError("HTTP_ERROR", str(e)) from e
        except requests.exceptions.RequestException as e:
            raise CiotApiError("CONNECTION_ERROR", str(e)) from e

        data = resp.json()
        return self._check_codigo(data)

    def _get(self, endpoint: str, params: dict) -> dict:
        url = f"{self._base_url}/{endpoint}"
        try:
            resp = self._session.get(url, params=params, timeout=30)
            resp.raise_for_status()
        except requests.exceptions.SSLError as e:
            raise CiotAuthError(f"Falha mTLS — verifique certificado e cadastro na ANTT: {e}") from e
        except requests.exceptions.HTTPError as e:
            raise CiotApiError("HTTP_ERROR", str(e)) from e
        except requests.exceptions.RequestException as e:
            raise CiotApiError("CONNECTION_ERROR", str(e)) from e

        data = resp.json()
        return self._check_codigo(data)

    @staticmethod
    def _check_codigo(data: dict) -> dict:
        # Codigo e Mensagem podem ser string ou list["000000"] conforme DCS
        raw_codigo = data.get("Codigo", data.get("codigo", ""))
        codigo = raw_codigo[0] if isinstance(raw_codigo, list) else str(raw_codigo)
        if codigo not in _CODIGOS_SUCESSO:
            raw_msg = data.get("Mensagem", data.get("mensagem", ""))
            mensagem = raw_msg[0] if isinstance(raw_msg, list) else str(raw_msg)
            protocolo = str(data.get("Protocolo", data.get("protocolo", "")))
            raise CiotApiError(codigo=codigo, mensagem=mensagem, protocolo=protocolo)
        return data

    # ── Gerador de IdOperacaoTransporte (endpoint /gerar) ─────────────────────

    def gerar_id_operacao_via_api(self, chave_api: str, cnpj: str) -> str:
        """Obtém um IdOperacaoTransporte válido via API ANTT.

        Descoberto na análise da DLL GeradorCIOTShared.dll v3.1:
            1) POST {base}/token  body {"chave": "..."}  → response {"token": "..."}
            2) POST {base}/gerar  Authorization: Bearer <token>  body {"cnpj": "..."}
               → response (caminho aninhado dados.ciot.Dados.CIOT)

        A "chave" é um identificador secreto distribuído pela ANTT às
        AMPEFs/IPEFs credenciadas. Sem ela, /token responde 401 "Acesso Negado".
        """
        # Base sem o /api final
        gen_base = self._base_url.rsplit("/api", 1)[0]

        try:
            r = self._session.post(
                f"{gen_base}/token",
                json={"chave": chave_api},
                timeout=20,
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise CiotApiError(
                codigo="TOKEN_ERROR",
                mensagem=f"Falha em /token: {e}. Resposta: {r.text[:200]}",
            ) from e

        token = r.json().get("token", "")
        if not token:
            raise CiotApiError(codigo="TOKEN_VAZIO",
                               mensagem=f"Token vazio na resposta: {r.text[:200]}")

        try:
            r = self._session.post(
                f"{gen_base}/gerar",
                json={"cnpj": _validar_cpf_cnpj(cnpj)},
                headers={"Authorization": f"Bearer {token}"},
                timeout=20,
            )
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            raise CiotApiError(
                codigo="GERAR_ERROR",
                mensagem=f"Falha em /gerar: {e}. Resposta: {r.text[:200]}",
            ) from e

        data = r.json()
        # Procura path aninhado: dados.ciot.Dados.CIOT (descoberto no binário)
        ciot = (
            data.get("dados", {}).get("ciot", {}).get("Dados", {}).get("CIOT")
            or data.get("Dados", {}).get("CIOT")
            or data.get("CIOT")
            or data.get("ciot")
        )
        if not ciot:
            raise CiotApiError(
                codigo="CIOT_NAO_EXTRAIDO",
                mensagem=f"Não foi possível extrair o CIOT da resposta: {r.text[:300]}",
            )
        return ciot

    # ── 1. ConsultarSituacaoTransportador ─────────────────────────────────────

    def consultar_situacao_transportador(
        self,
        cpf_cnpj_transportador: str,
        rntrc_transportador: str,
    ) -> SituacaoTransportadorResponse:
        payload = {
            "CpfCnpjInteressado": self.cnpj_interessado,
            "CpfCnpjTransportador": _validar_cpf_cnpj(cpf_cnpj_transportador),
            "RNTRCTransportador": _normalizar_rntrc(rntrc_transportador),
        }
        d = self._post("ConsultarSituacaoTransportador", payload)
        return SituacaoTransportadorResponse(
            cpf_cnpj_transportador=d.get("CpfCnpjTransportador", ""),
            rntrc_transportador=d.get("RNTRCTransportador", ""),
            nome_razao_social=d.get("NomeRazaoSocialTransportador", ""),
            rntrc_ativo=bool(d.get("RNTRCAtivo", False)),
            tipo_transportador=d.get("TipoTransportador", ""),
            equiparado_tac=bool(d.get("EquiparadoTAC", False)),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )

    # ── 2. ConsultarFrotaTransportador ────────────────────────────────────────

    def consultar_frota_transportador(
        self,
        cpf_cnpj_transportador: str,
        rntrc_transportador: str,
        placas: list[str],
    ) -> FrotaTransportadorResponse:
        payload = {
            "CpfCnpjInteressado": self.cnpj_interessado,
            "CpfCnpjTransportador": _validar_cpf_cnpj(cpf_cnpj_transportador),
            "RNTRCTransportador": _normalizar_rntrc(rntrc_transportador),
            "Placas": placas,
        }
        d = self._post("ConsultarFrotaTransportador", payload)
        frota = [
            VeiculoStatus(
                placa_veiculo=v.get("PlacaVeiculo", ""),
                situacao_veiculo_frota_transportador=v.get("SituacaoVeiculoFrotaTransportador", 0),
            )
            for v in d.get("Frota", [])
        ]
        return FrotaTransportadorResponse(
            cpf_cnpj_transportador=d.get("CpfCnpjTransportador", ""),
            rntrc_transportador=d.get("RNTRCTransportador", ""),
            nome_razao_social=d.get("NomeRazaoSocialTransportador", ""),
            rntrc_ativo=bool(d.get("RNTRCAtivo", False)),
            frota=frota,
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )

    # ── 3. DeclaracaoOperacaoTransporte ───────────────────────────────────────

    def declarar_operacao(self, dados: DeclaracaoInput) -> DeclaracaoResponse:
        if not dados.id_operacao:
            # Tenta gerar via DLL (regra B16) se configurada, senão fallback timestamp
            if self.dll_geradorciot_dir:
                try:
                    from ._dll_loader import gerar_id_via_dll
                    dados.id_operacao = gerar_id_via_dll(
                        dados.cpf_cnpj_contratante,
                        self.dll_geradorciot_dir,
                    )
                except Exception:
                    dados.id_operacao = _gerar_id_operacao()
            else:
                dados.id_operacao = _gerar_id_operacao()
        else:
            if len(dados.id_operacao) != 12:
                raise CiotValidationError("id_operacao deve ter exatamente 12 caracteres")

        if not dados.data_declaracao:
            # BRT com offset explícito (-03:00). UTC sem offset / UTC com Z /
            # hora local sem offset → rejeição 269 (fora da tolerância).
            dt = datetime.now(_TZ_BRT)
            dados.data_declaracao = dt.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"

        dados.rntrc_contratado = _normalizar_rntrc(dados.rntrc_contratado)
        dados.cpf_cnpj_contratado = _validar_cpf_cnpj(dados.cpf_cnpj_contratado)
        dados.cpf_cnpj_contratante = _validar_cpf_cnpj(dados.cpf_cnpj_contratante)

        payload = _declaracao_to_dict(dados, self.cnpj_interessado)
        d = self._post("DeclaracaoOperacaoTransporte", payload)

        resp = DeclaracaoResponse(
            codigo_identificacao_operacao=d.get("CodigoIdentificacaoOperacao", d.get("IdOperacaoTransporte", "")),
            codigo_verificador=d.get("CodigoVerificador", ""),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
            aviso_transportador=d.get("AvisoTransportador", ""),
        )
        self.storage.registrar_declaracao(dados, resp)
        return resp

    # ── 4. CancelamentoOperacaoTransporte ─────────────────────────────────────

    def cancelar_operacao(self, dados: CancelamentoInput) -> CancelamentoResponse:
        payload = {
            "CodigoIdentificacaoOperacao": dados.codigo_identificacao_operacao,
            "MotivoCancelamento": dados.motivo_cancelamento,
        }
        d = self._post("CancelamentoOperacaoTransporte", payload)
        resp = CancelamentoResponse(
            codigo_identificacao_operacao=d.get("CodigoIdentificacaoOperacao", ""),
            data_cancelamento=d.get("DataCancelamento", ""),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )
        id_op = dados.codigo_identificacao_operacao[:12]
        self.storage.atualizar_status(id_op, "cancelada", resp.protocolo)
        return resp

    # ── 5. RetificacaoOperacaoTransporte ──────────────────────────────────────

    def retificar_operacao(self, dados: RetificacaoInput) -> RetificacaoResponse:
        payload: dict = {"CodigoIdentificacaoOperacao": dados.codigo_identificacao_operacao}
        if dados.valor_frete is not None:
            payload["ValorFrete"] = dados.valor_frete
        if dados.data_fim_viagem:
            payload["DataFimViagem"] = dados.data_fim_viagem
        if dados.origem_destino:
            payload["OrigemDestino"] = [_od_to_dict(dados.origem_destino)]
        if dados.dados_carga:
            payload["DadosCarga"] = _carga_to_dict(dados.dados_carga)

        d = self._post("RetificacaoOperacaoTransporte", payload)
        resp = RetificacaoResponse(
            codigo_identificacao_operacao=d.get("CodigoIdentificacaoOperacao", ""),
            data_retificacao=d.get("DataRetificacao", ""),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )
        id_op = dados.codigo_identificacao_operacao[:12]
        self.storage.atualizar_status(id_op, "retificada", resp.protocolo)
        return resp

    # ── 6. EncerramentoOperacaoTransporte ─────────────────────────────────────

    def encerrar_operacao(self, dados: EncerramentoInput) -> EncerramentoResponse:
        payload: dict = {"CodigoIdentificacaoOperacao": dados.codigo_identificacao_operacao}
        if dados.origem_destino:
            payload["OrigemDestino"] = [_od_to_dict(od) for od in dados.origem_destino]
        if dados.peso_carga is not None:
            payload["DadosCarga"] = {"PesoTotalCarga": dados.peso_carga}

        d = self._post("EncerramentoOperacaoTransporte", payload)
        resp = EncerramentoResponse(
            codigo_identificacao_operacao=d.get("CodigoIdentificacaoOperacao", ""),
            data_encerramento=d.get("DataEncerramento", ""),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )
        id_op = dados.codigo_identificacao_operacao[:12]
        self.storage.atualizar_status(id_op, "encerrada", resp.protocolo)
        return resp

    # ── 7. ConsultarCIOTGerado ────────────────────────────────────────────────

    def consultar_ciot_gerado(self, id_operacao: str, ano_declaracao: Optional[int] = None) -> CiotGeradoResponse:
        # DCS v1.1: payload = { CodigoIdentificacaoOperacao (12), AnoDeclaracao (opc) }
        payload: dict = {"CodigoIdentificacaoOperacao": id_operacao}
        if ano_declaracao is not None:
            payload["AnoDeclaracao"] = ano_declaracao
        d = self._post("ConsultarCIOTGerado", payload)
        return CiotGeradoResponse(
            codigo_identificacao_operacao=d.get("CodigoIdentificacaoOperacao", ""),
            codigo_verificador=d.get("CodigoVerificador", ""),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )

    # ── 8. ConsultarExcecao ───────────────────────────────────────────────────

    def consultar_excecao(self, cpf_cnpj_transportador: str) -> ExcecaoResponse:
        # GET com query string conforme implementação de referência ANTT
        params = {"CPFCNPJTransportador": _validar_cpf_cnpj(cpf_cnpj_transportador)}
        d = self._get("ConsultarExcecao", params)
        retorno = d.get("Retorno", {})
        esta_na_excecao = retorno.get("Flag", d.get("EstaEmExcecao", d.get("EstaNaExcecao", False)))
        return ExcecaoResponse(
            esta_na_excecao=bool(esta_na_excecao),
            protocolo=d.get("Protocolo", ""),
            codigo=d.get("Codigo", ""),
            mensagem=d.get("Mensagem", ""),
        )


# ── Helpers de serialização ───────────────────────────────────────────────────

def _normalizar_rntrc(rntrc: str) -> str:
    rntrc = rntrc.strip()
    if len(rntrc) == 9:
        return rntrc
    if len(rntrc) == 8:
        return "0" + rntrc
    raise CiotValidationError(
        f"RNTRC inválido: {rntrc!r}. Deve ter 8 ou 9 dígitos."
    )


def _validar_cpf_cnpj(valor: str) -> str:
    valor = "".join(c for c in valor if c.isdigit())
    if len(valor) == 11:
        if not _cpf_valido(valor):
            raise CiotValidationError(f"CPF inválido: {valor}")
        return valor
    if len(valor) == 14:
        if not _cnpj_valido(valor):
            raise CiotValidationError(f"CNPJ inválido: {valor}")
        return valor
    raise CiotValidationError(
        f"CPF/CNPJ inválido: deve ter 11 (CPF) ou 14 (CNPJ) dígitos, recebido {len(valor)}"
    )


def _cpf_valido(cpf: str) -> bool:
    if len(set(cpf)) == 1:
        return False
    for i in range(9, 11):
        soma = sum(int(cpf[j]) * (i + 1 - j) for j in range(i))
        dv = (soma * 10 % 11) % 10
        if dv != int(cpf[i]):
            return False
    return True


def _cnpj_valido(cnpj: str) -> bool:
    if len(set(cnpj)) == 1:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for pesos, pos in [(pesos1, 12), (pesos2, 13)]:
        soma = sum(int(cnpj[i]) * pesos[i] for i in range(pos))
        resto = soma % 11
        dv = 0 if resto < 2 else 11 - resto
        if dv != int(cnpj[pos]):
            return False
    return True


def _gerar_id_operacao() -> str:
    # ATENÇÃO: este fallback gera 12 chars únicos por timestamp, mas a ANTT
    # NÃO aceita IDs arbitrários. Regra B16 do DCS v1.1 exige formato:
    # "ID da administradora + DV" (dígito verificador). Para gerar IDs aceitos
    # use a DLL oficial GeradorCIOT.exe da ANTT, ou passe seu próprio id_operacao
    # no DeclaracaoInput pré-gerado por sistema integrado.
    return datetime.now().strftime("%y%m%d%H%M%S")


def _od_to_dict(od) -> dict:
    result: dict = {}
    if od.origem:
        origem: dict = {}
        if od.origem.codigo_municipio:
            origem["CodigoMunicipioOrigem"] = od.origem.codigo_municipio
        if od.origem.cep:
            origem["CepOrigem"] = od.origem.cep
        if od.origem.latitude is not None:
            origem["LatitudeOrigem"] = od.origem.latitude
        if od.origem.longitude is not None:
            origem["LongitudeOrigem"] = od.origem.longitude
        result["Origem"] = origem
    if od.destino:
        destino: dict = {}
        if od.destino.codigo_municipio:
            destino["CodigoMunicipioDestino"] = od.destino.codigo_municipio
        if od.destino.cep:
            destino["CepDestino"] = od.destino.cep
        if od.destino.latitude is not None:
            destino["LatitudeDestino"] = od.destino.latitude
        if od.destino.longitude is not None:
            destino["LongitudeDestino"] = od.destino.longitude
        result["Destino"] = destino
    if od.distancia_percorrida is not None:
        # DCS tipo N (numérico INTEIRO) — float quebra o transformer .NET com NPE!
        result["DistanciaPercorrida"] = int(od.distancia_percorrida)
    if od.qtd_viagens is not None:
        result["QtdViagens"] = int(od.qtd_viagens)
    return result


def _carga_to_dict(carga) -> dict:
    d: dict = {}
    if carga.codigo_natureza_carga:
        d["CodigoNaturezaCarga"] = carga.codigo_natureza_carga
    if carga.peso_carga is not None:
        d["PesoCarga"] = float(carga.peso_carga)
    if carga.codigo_tipo_carga is not None:
        d["CodigoTipoCarga"] = int(carga.codigo_tipo_carga)
    # ContratantesCargFrac (typo do DCS, sem "a") — só envia se houver
    if carga.contratantes_carga_frac:
        d["ContratantesCargFrac"] = carga.contratantes_carga_frac
    return d


def _pagamento_to_dict(pag) -> dict:
    # DCS v1.1: parcelas são campos FLAT no InfPagamento (NumeroParcela,
    # DataVencimento, ValorParcela). NÃO existe array Parcelas[] aninhado.
    d: dict = {
        "TipoPagamento": int(pag.tipo_pagamento),
        "CpfCnpjCreditado": pag.cpf_cnpj_creditado,
        "IndPagamento": pag.ind_pagamento,
    }
    if pag.codigo_instituicao_financeira:
        d["CodigoInstituicaoFinanceira"] = pag.codigo_instituicao_financeira
    if pag.numero_agencia:
        d["NumeroAgencia"] = pag.numero_agencia
    if pag.numero_conta:
        d["NumeroConta"] = pag.numero_conta
    if pag.chave_pix:
        d["ChavePix"] = pag.chave_pix
    if pag.codigo_pagamento:
        d["CodigoPagamento"] = pag.codigo_pagamento
    if pag.identificador_pix:
        d["IdentificadorPix"] = pag.identificador_pix
    # Parcelas flat — só quando ind_pagamento==1 (a prazo)
    if pag.parcelas:
        p = pag.parcelas[0]  # DCS suporta uma parcela por estrutura flat
        d["NumeroParcela"] = p.numero_parcela
        d["DataVencimento"] = p.data_vencimento
        d["ValorParcela"] = p.valor_parcela
    return d


def _declaracao_to_dict(dados: DeclaracaoInput, cnpj_interessado: str) -> dict:
    # Estrutura DCS v1.1 oficial — APENAS campos preenchidos.
    # Campos opcionais vazios NÃO são enviados (transformer .NET pode crashar
    # ao ler `""` como objeto vinculado). Newtonsoft.Json defaults para null
    # quando ausente — comportamento esperado pelo transformer.
    payload: dict = {
        "IdOperacaoTransporte": dados.id_operacao,
        "TipoOperacao": int(dados.tipo_operacao),
        "CpfCnpjContratado": dados.cpf_cnpj_contratado,
        "RNTRCContratado": dados.rntrc_contratado,
        "CpfCnpjContratante": dados.cpf_cnpj_contratante,
        "ValorFrete": float(dados.valor_frete),
        "DataDeclaracao": dados.data_declaracao,
        "IndContingencia": bool(dados.ind_contingencia),
        "DataInicioViagem": dados.data_inicio_viagem,
        "DataFimViagem": dados.data_fim_viagem,
        "Veiculos": [_veiculo_to_dict(v) for v in dados.veiculos],
        "InfPagamento": [_pagamento_to_dict(p) for p in dados.inf_pagamento],
    }

    # Opcionais — só inclui se vier preenchido
    if dados.rntrc_contratante:
        payload["RNTRCContratante"] = _normalizar_rntrc(dados.rntrc_contratante)
    if dados.cpf_cnpj_destinatario:
        payload["CpfCnpjDestinatario"] = _validar_cpf_cnpj(dados.cpf_cnpj_destinatario)
    if dados.ind_contingencia and dados.justificativa_contingencia:
        payload["JustificativaContingencia"] = dados.justificativa_contingencia
    if dados.origem_destino:
        payload["OrigemDestino"] = [_od_to_dict(od) for od in dados.origem_destino]
    if dados.dados_carga:
        payload["DadosCarga"] = _carga_to_dict(dados.dados_carga)
    if dados.indicadores_operacionais:
        payload["InfIndicadoresOperacionais"] = {
            "IndAltoDesempenho": bool(dados.indicadores_operacionais.ind_alto_desempenho),
            "IndRetornoVazio":   bool(dados.indicadores_operacionais.ind_retorno_vazio),
            "ComposicaoVeicular":bool(dados.indicadores_operacionais.composicao_veicular),
        }

    return payload


def _veiculo_to_dict(v) -> dict:
    """Veiculo do payload — RNTRC opcional só vai se preenchido."""
    d = {"Placa": v.placa, "NumeroEixos": str(v.numero_eixos)}
    if v.rntrc_veiculo:
        d["RNTRC"] = _normalizar_rntrc(v.rntrc_veiculo)
    return d
