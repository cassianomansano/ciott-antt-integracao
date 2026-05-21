import json
import pytest
from unittest.mock import MagicMock, patch

from ciot_antt import (
    CiotClient,
    CiotApiError,
    CiotValidationError,
    TipoOperacao,
    TipoPagamento,
    DeclaracaoInput,
    CancelamentoInput,
    EncerramentoInput,
    VeiculoInput,
    InfPagamentoInput,
)


CNPJ_INTERESSADO = "11222333000181"
CPF_TRANSPORTADOR = "52998224725"
RNTRC = "123456789"


def _make_client(tmp_path) -> CiotClient:
    with patch("ciot_antt.client.build_mtls_session") as mock_build:
        mock_session = MagicMock()
        mock_build.return_value = mock_session
        client = CiotClient(
            cert_pfx="fake.pfx",
            cert_password="senha",
            cnpj_interessado=CNPJ_INTERESSADO,
            env="homologacao",
            db_path=str(tmp_path / "test.db"),
        )
        client._session = mock_session
        return client


def _mock_response(client: CiotClient, data: dict):
    resp = MagicMock()
    resp.json.return_value = data
    resp.raise_for_status.return_value = None
    client._session.post.return_value = resp


# ── Testes ConsultarSituacaoTransportador ─────────────────────────────────────

def test_consultar_situacao_transportador_sucesso(tmp_path):
    client = _make_client(tmp_path)
    _mock_response(client, {
        "CpfCnpjTransportador": CPF_TRANSPORTADOR,
        "RNTRCTransportador": RNTRC,
        "NomeRazaoSocialTransportador": "João Silva",
        "RNTRCAtivo": True,
        "TipoTransportador": "TAC",
        "EquiparadoTAC": False,
        "Protocolo": "PROT001",
        "Codigo": "000000",
        "Mensagem": "Sucesso",
    })
    resultado = client.consultar_situacao_transportador(CPF_TRANSPORTADOR, RNTRC)
    assert resultado.rntrc_ativo is True
    assert resultado.tipo_transportador == "TAC"
    assert resultado.codigo == "000000"


# ── Testes DeclaracaoOperacaoTransporte ───────────────────────────────────────

def _make_declaracao_input():
    return DeclaracaoInput(
        tipo_operacao=TipoOperacao.LOTACAO,
        cpf_cnpj_contratado=CPF_TRANSPORTADOR,
        rntrc_contratado=RNTRC,
        cpf_cnpj_contratante=CNPJ_INTERESSADO,
        valor_frete=3500.00,
        data_inicio_viagem="2026-05-24",
        data_fim_viagem="2026-05-25",
        veiculos=[VeiculoInput(placa="ABC1234", numero_eixos="2")],
        inf_pagamento=[
            InfPagamentoInput(
                tipo_pagamento=TipoPagamento.PIX,
                cpf_cnpj_creditado=CPF_TRANSPORTADOR,
                ind_pagamento=0,
                chave_pix="98765432100",
            )
        ],
    )


def test_declarar_operacao_sucesso(tmp_path):
    client = _make_client(tmp_path)
    _mock_response(client, {
        "CodigoIdentificacaoOperacao": "202605241001",
        "CodigoVerificador": "1234",
        "Protocolo": "PROT002",
        "Codigo": "000000",
        "Mensagem": "Dados inseridos com sucesso!",
        "AvisoTransportador": "",
    })
    dados = _make_declaracao_input()
    resp = client.declarar_operacao(dados)

    assert resp.codigo_identificacao_operacao == "202605241001"
    assert resp.codigo_verificador == "1234"
    assert resp.ciot_completo == "2026052410011234"

    # Verifica persistência no SQLite
    registro = client.storage.buscar_por_ciot("202605241001")
    assert registro is not None
    assert registro["status"] == "declarada"
    assert registro["valor_frete"] == 3500.00


def test_declarar_operacao_frete_rejeitado(tmp_path):
    client = _make_client(tmp_path)
    _mock_response(client, {
        "Codigo": "291",
        "Mensagem": "O valor do frete informado é menor do que o valor mínimo de frete estabelecido.",
        "Protocolo": "PROT003",
    })
    dados = _make_declaracao_input()
    dados.valor_frete = 10.00

    with pytest.raises(CiotApiError) as exc_info:
        client.declarar_operacao(dados)
    assert exc_info.value.codigo == "291"
    assert "mínimo" in exc_info.value.mensagem


# ── Testes RNTRC ──────────────────────────────────────────────────────────────

def test_rntrc_8_digitos_normalizado(tmp_path):
    client = _make_client(tmp_path)
    _mock_response(client, {
        "CpfCnpjTransportador": CPF_TRANSPORTADOR,
        "RNTRCTransportador": "012345678",
        "NomeRazaoSocialTransportador": "Test",
        "RNTRCAtivo": True,
        "TipoTransportador": "TAC",
        "EquiparadoTAC": False,
        "Protocolo": "PROT",
        "Codigo": "000000",
        "Mensagem": "OK",
    })
    client.consultar_situacao_transportador(CPF_TRANSPORTADOR, "12345678")
    chamada = client._session.post.call_args
    payload = chamada[1]["json"]
    assert payload["RNTRCTransportador"] == "012345678"


def test_rntrc_7_digitos_raise(tmp_path):
    client = _make_client(tmp_path)
    with pytest.raises(CiotValidationError, match="RNTRC inválido"):
        client.consultar_situacao_transportador(CPF_TRANSPORTADOR, "1234567")


# ── Testes Cancelamento ───────────────────────────────────────────────────────

def test_cancelar_operacao_atualiza_status(tmp_path):
    client = _make_client(tmp_path)

    # Primeiro declara para ter registro no storage
    _mock_response(client, {
        "CodigoIdentificacaoOperacao": "202605241001",
        "CodigoVerificador": "9999",
        "Protocolo": "P1",
        "Codigo": "000000",
        "Mensagem": "OK",
        "AvisoTransportador": "",
    })
    dados = _make_declaracao_input()
    dados.id_operacao = "202605241001"
    client.declarar_operacao(dados)

    # Agora cancela
    _mock_response(client, {
        "CodigoIdentificacaoOperacao": "2026052410019999",
        "DataCancelamento": "2026-05-24T10:00:00",
        "Protocolo": "P2",
        "Codigo": "000000",
        "Mensagem": "Cancelado",
    })
    resp = client.cancelar_operacao(
        CancelamentoInput(
            codigo_identificacao_operacao="2026052410019999",
            motivo_cancelamento="Teste",
        )
    )
    assert resp.codigo == "000000"

    registro = client.storage.buscar_por_id_operacao("202605241001")
    assert registro["status"] == "cancelada"


# ── Testes Alerta de Encerramento ─────────────────────────────────────────────

def test_listar_pendentes_encerramento(tmp_path):
    client = _make_client(tmp_path)
    _mock_response(client, {
        "CodigoIdentificacaoOperacao": "202605141001",
        "CodigoVerificador": "0001",
        "Protocolo": "P1",
        "Codigo": "000000",
        "Mensagem": "OK",
        "AvisoTransportador": "",
    })
    dados = _make_declaracao_input()
    dados.id_operacao = "202605141001"
    dados.data_inicio_viagem = "2026-05-14"  # 6 dias atrás → já venceu
    dados.data_fim_viagem = "2026-05-15"
    client.declarar_operacao(dados)

    pendentes = client.storage.listar_pendentes_encerramento(dias_aviso=1)
    assert len(pendentes) >= 1
    assert pendentes[0]["id_operacao"] == "202605141001"
