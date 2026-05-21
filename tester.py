"""
Tester visual para a API PEF/CIOT da ANTT.
Uso: python tester.py
"""
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, font, scrolledtext, ttk
from typing import Optional

_CONFIG_FILE = Path(__file__).parent / ".tester_config.json"
_LOG_FILE    = Path(__file__).parent / "ciot_antt_tester.log"

logging.basicConfig(
    filename=_LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s %(message)s",
    encoding="utf-8",
)
_log = logging.getLogger("ciot_tester")


def _save_config(data: dict):
    _CONFIG_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_config() -> dict:
    if _CONFIG_FILE.exists():
        try:
            return json.loads(_CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _strip_doc(value: str) -> str:
    """Remove pontuação de CPF/CNPJ (. - / espaços)."""
    return re.sub(r"[\.\-/\s]", "", value)


def _strip_rntrc(value: str) -> str:
    """Remove pontuação de RNTRC (. - espaços)."""
    return re.sub(r"[\.\-\s]", "", value)


def _norm_field(key: str, value: str) -> str:
    if "cpf_cnpj" in key:
        return _strip_doc(value)
    if "rntrc" in key:
        return _strip_rntrc(value)
    return value


_SENSITIVE_PATTERNS = ("cpf", "cnpj", "rntrc", "pix", "conta", "agencia", "creditado",
                        "destinatario", "contratado", "contratante", "interessado")


def _mask_value(v: str) -> str:
    if not v or len(v) <= 4:
        return "***"
    return v[:2] + "*" * (len(v) - 4) + v[-2:]


def _mask_obj(obj):
    if isinstance(obj, dict):
        for k in list(obj.keys()):
            kl = k.lower()
            if any(p in kl for p in _SENSITIVE_PATTERNS):
                if isinstance(obj[k], str) and obj[k]:
                    obj[k] = _mask_value(obj[k])
                elif isinstance(obj[k], list):
                    obj[k] = [_mask_value(i) if isinstance(i, str) else i for i in obj[k]]
            else:
                _mask_obj(obj[k])
    elif isinstance(obj, list):
        for item in obj:
            _mask_obj(item)


def _mask_json_str(json_str: str) -> str:
    try:
        data = json.loads(json_str)
        _mask_obj(data)
        return json.dumps(data, indent=2, ensure_ascii=False)
    except Exception:
        return json_str


def _normalize_payload(obj):
    """Normaliza recursivamente CPF/CNPJ e RNTRC no payload (remove pontuação)."""
    if isinstance(obj, dict):
        for k, val in obj.items():
            if isinstance(val, str):
                kl = k.lower()
                if "cpf_cnpj" in kl:
                    obj[k] = _strip_doc(val)
                elif "rntrc" in kl:
                    obj[k] = _strip_rntrc(val)
            elif isinstance(val, (dict, list)):
                _normalize_payload(val)
    elif isinstance(obj, list):
        for item in obj:
            _normalize_payload(item)


def _safe_float(s: str, default: float) -> float:
    try:
        return float(s)
    except (ValueError, TypeError):
        return default


def _safe_int(s: str, default: int) -> int:
    try:
        return int(s)
    except (ValueError, TypeError):
        return default


def _build_template_03(saved: dict, cnpj_interessado: str) -> str:
    contratado   = saved.get("cpf_cnpj_transportador", "00000000000")
    rntrc        = saved.get("rntrc_transportador",   "000000000")
    cnpj_int     = _strip_doc(cnpj_interessado) or "00000000000000"
    destinatario = saved.get("cpf_cnpj_destinatario", "33000167000101")  # Petrobras
    g = saved.get  # alias

    veiculos = [{
        "placa":        g("aux_placa_veiculo", "ABC1234"),
        "numero_eixos": g("aux_numero_eixos", "2"),
    }]
    reboque = g("aux_placa_reboque", "")
    if reboque:
        veiculos.append({"placa": reboque, "numero_eixos": "2"})

    body = {
        "tipo_operacao":         _safe_int(g("aux_tipo_operacao", "1"), 1),
        "cpf_cnpj_contratado":   contratado,
        "rntrc_contratado":      rntrc,
        "cpf_cnpj_contratante":  cnpj_int,
        "cpf_cnpj_destinatario": destinatario,
        "valor_frete":           _safe_float(g("aux_valor_frete", "3500.00"), 3500.00),
        "data_inicio_viagem":    g("aux_data_inicio_viagem", "2026-05-24"),
        "data_fim_viagem":       g("aux_data_fim_viagem", "2026-05-25"),
        "veiculos":              veiculos,
        "origem_destino": [{
            "origem": {
                "codigo_municipio": g("aux_codigo_municipio_origem", "3550308"),
                "cep":              g("aux_cep_origem", "01310100"),
            },
            "destino": {
                "codigo_municipio": g("aux_codigo_municipio_destino", "3304557"),
                "cep":              g("aux_cep_destino", "20040020"),
            },
            "distancia_percorrida": _safe_float(g("aux_distancia_percorrida", "430"), 430.0),
        }],
        "dados_carga": {
            "codigo_natureza_carga": g("aux_codigo_natureza_carga", "5706"),
            "peso_carga":            _safe_float(g("aux_peso_carga", "10000"), 10000.0),
            "codigo_tipo_carga":     _safe_int(g("aux_codigo_tipo_carga", "5"), 5),
        },
        "inf_pagamento": [{
            "tipo_pagamento":     6,
            "cpf_cnpj_creditado": contratado,
            "ind_pagamento":      0,
            "chave_pix":          contratado,
        }],
        "indicadores_operacionais": {
            "ind_alto_desempenho": False,
            "ind_retorno_vazio":   False,
            "composicao_veicular": False,
        }
    }
    # ID Operação manual (da DLL ANTT GeradorCIOT.exe) — se preenchido, usa
    id_manual = g("aux_id_operacao_manual", "").strip()
    if id_manual:
        body["id_operacao"] = id_manual
    return json.dumps(body, indent=2, ensure_ascii=False)

# ── Paleta ────────────────────────────────────────────────────────────────────
BG       = "#1e1e2e"
BG2      = "#2a2a3e"
BG3      = "#313145"
FG       = "#cdd6f4"
FG2      = "#a6adc8"
ACCENT   = "#89b4fa"
GREEN    = "#a6e3a1"
RED      = "#f38ba8"
YELLOW   = "#f9e2af"
BORDER   = "#45475a"
FONT_UI  = ("Segoe UI", 9)
FONT_MON = ("Consolas", 9)

# ── Templates JSON por endpoint ───────────────────────────────────────────────
_TEMPLATES = {
    "03": json.dumps({
        "tipo_operacao": 1,
        "cpf_cnpj_contratado": "00000000000",
        "rntrc_contratado": "000000000",
        "cpf_cnpj_contratante": "00000000000000",
        "valor_frete": 3500.00,
        "data_inicio_viagem": "2026-05-24",
        "data_fim_viagem": "2026-05-25",
        "veiculos": [{"placa": "ABC1234", "numero_eixos": "2"}],
        "inf_pagamento": [{
            "tipo_pagamento": 6,
            "cpf_cnpj_creditado": "00000000000",
            "ind_pagamento": 0,
            "chave_pix": "00000000000"
        }],
        "indicadores_operacionais": {
            "ind_alto_desempenho": False,
            "ind_retorno_vazio": False,
            "composicao_veicular": False
        }
    }, indent=2, ensure_ascii=False),
}

# ── Campos simples por endpoint ───────────────────────────────────────────────
# Lista de (label, chave_interna, placeholder)
_FIELDS = {
    "01": [
        ("CPF/CNPJ Transportador", "cpf_cnpj_transportador", "98765432100"),
        ("RNTRC",                  "rntrc_transportador",    "000123456"),
    ],
    "02": [
        ("CPF/CNPJ Transportador", "cpf_cnpj_transportador", "98765432100"),
        ("RNTRC",                  "rntrc_transportador",    "000123456"),
        ("Placas (vírgula)",       "placas",                 "ABC1234,DEF5678"),
    ],
    "04": [
        ("Código CIOT (16 chars)", "codigo_ciot",  "202605241001XXXX"),
        ("Motivo cancelamento",    "motivo",        "Operação não realizada"),
    ],
    "05": [
        ("Código CIOT (16 chars)", "codigo_ciot",   "202605241001XXXX"),
        ("Valor frete (opcional)", "valor_frete",   "3500.00"),
        ("Data fim (opcional)",    "data_fim",      "2026-05-25"),
    ],
    "06": [
        ("Código CIOT (16 chars)", "codigo_ciot",   "202605241001XXXX"),
        ("Peso carga kg (opc.)",   "peso_carga",    ""),
    ],
    "07": [
        ("Id Operação (12 chars)", "id_operacao",   "202605241001"),
    ],
    "08": [
        ("CPF/CNPJ Transportador", "cpf_cnpj_transportador", "98765432100"),
    ],
}

_FIELDS_AUX = [
    ("Pasta DLL GeradorCIOT (auto-gera ID)","aux_dll_geradorciot_dir",   ""),
    ("ID Operação manual (12, da DLL ANTT)","aux_id_operacao_manual",    ""),
    ("Placa reboque (cavalo-trator exige)","aux_placa_reboque",          ""),
    ("Código natureza carga (4 dígitos)","aux_codigo_natureza_carga",    "0101"),
    ("Código tipo carga (1-12)",         "aux_codigo_tipo_carga",        "5"),
    ("Peso carga (kg)",                  "aux_peso_carga",               "10000"),
    ("Cód. município origem (IBGE 7d)",  "aux_codigo_municipio_origem",  "3550308"),
    ("Cód. município destino (IBGE 7d)", "aux_codigo_municipio_destino", "3304557"),
    ("CEP origem",                       "aux_cep_origem",               "01310100"),
    ("CEP destino",                      "aux_cep_destino",              "20040020"),
    ("Distância percorrida (km)",        "aux_distancia_percorrida",     "430"),
    ("Placa veículo",                    "aux_placa_veiculo",            "ABC1234"),
    ("Número eixos",                     "aux_numero_eixos",             "2"),
    ("Valor frete",                      "aux_valor_frete",              "3500.00"),
    ("Tipo operação (1/2/3)",            "aux_tipo_operacao",            "1"),
    ("Data início viagem",               "aux_data_inicio_viagem",       "2026-05-24"),
    ("Data fim viagem",                  "aux_data_fim_viagem",          "2026-05-25"),
]


_ENDPOINT_NAMES = {
    "01": "ConsultarSituacaoTransportador",
    "02": "ConsultarFrotaTransportador",
    "03": "DeclaracaoOperacaoTransporte",
    "04": "CancelamentoOperacaoTransporte",
    "05": "RetificacaoOperacaoTransporte",
    "06": "EncerramentoOperacaoTransporte",
    "07": "ConsultarCIOTGerado",
    "08": "ConsultarExcecao",
}

_ENDPOINT_LIST = [f"{k} — {v}" for k, v in _ENDPOINT_NAMES.items()]


_HELP_ENDPOINTS = {
    "01": """\
═══ 01 — ConsultarSituacaoTransportador (POST) ═══

OBJETIVO
   Valida se o transportador (CPF/CNPJ + RNTRC) está ATIVO no RNTRC e
   retorna o tipo (TAC, ETC, CTC) e nome/razão social.

QUANDO USAR
   • SEMPRE antes de declarar — se RNTRC inativo, declaração rejeita.
   • Cachear resultado: o RNTRC raramente muda.

CAMPOS
   • cpf_cnpj_transportador — CPF (11 dig) ou CNPJ (14 dig). Aceita
     com pontuação, normaliza automaticamente.
   • rntrc_transportador — 9 dígitos. Se vier com 8, completar zero
     à esquerda; com 7, é inválido.

RETORNO RELEVANTE
   • rntrc_ativo: True/False
   • tipo_transportador: TAC | ETC | CTC
   • equiparado_tac: bool — TAC equiparado tem regras diferentes
""",
    "02": """\
═══ 02 — ConsultarFrotaTransportador (POST) ═══

OBJETIVO
   Verifica se as placas informadas pertencem à frota do transportador
   e retorna a situação de cada veículo.

QUANDO USAR
   • Antes de declarar, para garantir que o veículo está vinculado
     ao transportador no RNTRC (evita rejeição "veículo sem vínculo").

CAMPOS
   • placas — separadas por vírgula no tester. Cada placa: 7 chars
     (formato antigo ABC1234 ou Mercosul ABC1D23).

RETORNO RELEVANTE
   • frota: array com placa + situação (1=ativo, etc)
""",
    "03": """\
═══ 03 — DeclaracaoOperacaoTransporte (POST) — GERA O CIOT ═══

OBJETIVO
   Registra a operação de transporte e retorna o CIOT (16 chars =
   12 do ID + 4 do verificador). Esse código vai NO MDF-e.

REGRAS CRÍTICAS
   • Gerar ANTES de iniciar a viagem e ANTES do MDF-e
   • CIOT incorreto ou divergente do MDF-e → multa R$ 10.500
   • TipoOperacao=1 (Lotação): exige InfIndicadoresOperacionais
   • TipoOperacao=2 (Fracionada): exige ContratantesCargFrac
   • TipoOperacao=3 (TAC-Agregado): NÃO informar CpfCnpjDestinatario

CAMPOS SENSÍVEIS (estrutura DCS v1.1 — descobertos batendo no servidor real)
   • Veiculos[*].RNTRC — NÃO "RNTRCVeiculo"!
   • InfPagamento[*].NumeroParcela — flat, NÃO array Parcelas[]
   • DadosCarga.ContratantesCargFrac — sem "a" (typo do DCS)
   • CpfCnpjInteressado NÃO vai no body (só nos outros endpoints)
   • NCMCargaPrincipal não existe no DCS v1.1
   • DistanciaPercorrida deve ser INT (não float!) — float → HTTP 500 NPE
   • DataDeclaracao em BRT com offset "-03:00" — UTC dá rejeição 269

REJEIÇÕES CONHECIDAS (NÃO são bug do código — dados reais)
   • "IdOperacaoTransporte é inválido" (regra B16):
       Formato exige "ID administradora + DV" gerado pela DLL ANTT
       GeradorCIOT.exe. Sem ela, qualquer ID rejeita.
   • "Veículo do tipo automotor não possui vínculo com o transportador":
       A placa precisa estar na frota cadastrada do CNPJ contratado
       no RNTRC. Cadastrar antes via portal ANTT.
   • "CodigoNaturezaCarga é inválido":
       Tabela própria ANTT (4 dígitos). Pedir lista à SUTEC.

PRAZO ENCERRAMENTO (após DataFimViagem)
   • Lotação/Fracionada: 5 dias corridos → senão multa R$ 10.500
   • TAC-Agregado: manual

DADOS AUXILIARES usados para montar o JSON
   • Pegue dados reais cadastrados na ANTT para o CNPJ ativo
   • CodigoNaturezaCarga: tabela própria ANTT (4 dígitos)
   • CodigoTipoCarga: 1=Granel sólido, 5=Carga geral, ...
""",
    "04": """\
═══ 04 — CancelamentoOperacaoTransporte (POST) ═══

OBJETIVO
   Cancela uma operação declarada. Permitido até 24h antes do início
   da viagem (regras B34-B39 do DCS).

CAMPOS
   • codigo_identificacao_operacao — CIOT completo (16 chars):
     codigo (12) + verificador (4)
   • motivo_cancelamento — texto livre até 500 chars, obrigatório

EFEITO
   • Operação fica com status "cancelada" no SQLite local
   • Após cancelar, NÃO pode encerrar nem retificar
""",
    "05": """\
═══ 05 — RetificacaoOperacaoTransporte (POST) ═══

OBJETIVO
   Corrige dados de uma operação já declarada (sem cancelar/redeclarar).

CAMPOS RETIFICÁVEIS
   • ValorFrete (sempre)
   • DataFimViagem (só se TipoOperacao=3 TAC-Agregado)
   • OrigemDestino (só se TipoOperacao=3)
   • DadosCarga (para Fracionada o usuário pode/não retificar)

EFEITO
   • Status passa a "retificada"
   • CIOT permanece o mesmo
""",
    "06": """\
═══ 06 — EncerramentoOperacaoTransporte (POST) ═══

OBJETIVO
   Encerra a operação após a entrega. SEM ISSO MULTA R$ 10.500/CIOT.

PRAZO
   • Lotação/Fracionada: até 5 dias corridos após DataFimViagem
   • TAC-Agregado: manual ao final do contrato

CAMPOS
   • codigo_identificacao_operacao — CIOT completo (16 chars)
   • peso_carga — para Lotação (TipoOperacao=1): peso real entregue
   • origem_destino — obrigatório para TAC-Agregado (TipoOperacao=3)

AUTOMAÇÃO RECOMENDADA
   Job diário lê storage.listar_pendentes_encerramento(dias_aviso=1)
   e encerra automaticamente.

VALIDAÇÃO ANTT
   ANTT cruza ValorFreteEfetivo com pagamento via IPEF.
   Se divergir → autuação automática.
""",
    "07": """\
═══ 07 — ConsultarCIOTGerado (POST) ═══

OBJETIVO
   Consulta um CIOT já gerado a partir do IdOperacaoTransporte (12 chars).
   Útil quando você perdeu o código verificador.

CAMPOS
   • id_operacao — 12 chars, exatamente o IdOperacaoTransporte
     gerado por você na declaração
   • ano_declaracao (opcional, 4 dígitos)

RETORNO
   • codigo_identificacao_operacao + codigo_verificador = CIOT (16)
""",
    "08": """\
═══ 08 — ConsultarExcecao (GET) ═══

OBJETIVO
   Verifica se o transportador está na lista de exceções da Resolução
   ANTT 5.862/2019 (transportadores que não precisam emitir CIOT).

CAMPOS
   • cpf_cnpj_transportador — 11 ou 14 dígitos

RETORNO
   • esta_na_excecao: True = está na lista (DISPENSADO de CIOT)
""",
}


_HELP_AUX = """\
═══ DADOS AUXILIARES — campos persistidos cross-endpoint ═══

ESSES CAMPOS são usados para MONTAR o JSON do endpoint 03 (Declaração).
São salvos em `.tester_config.json` e ficam disponíveis em todas as sessões.

   • Código natureza carga (4 dig) — tabela própria ANTT (NÃO é NCM!)
     Pedir lista à SUTEC/ANTT. Exemplos: 0101, 0202...

   • Código tipo carga (1-12) — fixo no DCS:
       1=Granel sólido        7=Perigosa granel sólido
       2=Granel líquido       8=Perigosa granel líquido
       3=Frigorificada/Aquec  9=Perigosa frigorificada
       4=Conteinerizada      10=Perigosa conteinerizada
       5=Carga geral         11=Perigosa carga geral
       6=Neogranel           12=Granel pressurizada

   • Peso carga (kg) — float, > 0

   • Cód. município (IBGE 7 dig) — busque em
     https://www.ibge.gov.br/explica/codigos-dos-municipios.php
     São Paulo=3550308, Rio de Janeiro=3304557, Brasília=5300108

   • CEP — 8 dígitos, só números

   • Distância percorrida (km) — float, > 0

   • Placa — formato antigo ABC1234 ou Mercosul ABC1D23

   • Número eixos — string 1-4 (implemento) ou 2-4 (automotor)

   • Valor frete — float, >= piso mínimo ANTT (Res. 6.076/2026)

   • Tipo operação — 1=Lotação | 2=Fracionada | 3=TAC-Agregado

   • Data início/fim viagem — formato YYYY-MM-DD


COMO RECARREGAR JSON
   1. Mude os auxiliares
   2. Volte na aba "Parâmetros"
   3. Clique "🔄 Regenerar do Auxiliares"
   4. JSON é reconstruído com os novos valores
"""


def _style_widget(w, **kw):
    try:
        w.configure(**kw)
    except tk.TclError:
        pass


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("CIOT-ANTT Tester")
        self.configure(bg=BG)
        self.resizable(True, True)
        self.minsize(900, 640)

        self._client = None
        self._field_vars: dict[str, tk.StringVar] = {}
        self._field_widgets: list[tk.Widget] = []
        self._aux_vars: dict[str, tk.StringVar] = {}
        self._saved_fields: dict[str, str] = {}  # flat: key → value, persiste cross-endpoint
        self._current_ep_id: str = ""
        self._mask_mode: bool = False
        self._sensitive_entries: list[tk.Entry] = []
        self._last_req_json: str = ""
        self._last_resp_json: str = ""

        # PRECISA carregar _saved_fields ANTES de _build_ui, senão os widgets
        # dos Auxiliares são criados com placeholders e ao salvar regravam
        # os placeholders por cima do config persistido.
        self._preload_saved_fields()

        self._build_ui()
        self._carregar_config()

    # ── Layout principal ──────────────────────────────────────────────────────

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        # ── Notebook principal: API | Operações ──
        self._main_nb = ttk.Notebook(self)
        self._main_nb.pack(fill="both", expand=True)

        self._tab_api = tk.Frame(self._main_nb, bg=BG)
        self._tab_ops = tk.Frame(self._main_nb, bg=BG)
        self._main_nb.add(self._tab_api, text=" 🔌 API ")
        self._main_nb.add(self._tab_ops, text=" 📊 Operações (CIOTs) ")

        # ── Conexão ──
        conn = tk.LabelFrame(self._tab_api, text=" Conexão ", bg=BG, fg=ACCENT,
                             font=FONT_UI, bd=1, relief="flat",
                             highlightbackground=BORDER, highlightthickness=1)
        conn.pack(fill="x", padx=10, pady=(10, 4))

        r0 = tk.Frame(conn, bg=BG)
        r0.pack(fill="x", **pad)
        tk.Label(r0, text="Certificado .pfx:", bg=BG, fg=FG2, font=FONT_UI).pack(side="left")
        self._cert_var = tk.StringVar()
        tk.Entry(r0, textvariable=self._cert_var, width=42, bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_MON).pack(side="left", padx=4)
        self._btn(r0, "Browse", self._browse_cert).pack(side="left")

        r1 = tk.Frame(conn, bg=BG)
        r1.pack(fill="x", **pad)
        tk.Label(r1, text="Senha:", bg=BG, fg=FG2, font=FONT_UI).pack(side="left")
        self._pass_var = tk.StringVar()
        tk.Entry(r1, textvariable=self._pass_var, show="*", width=20, bg=BG3, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_MON).pack(side="left", padx=4)

        tk.Label(r1, text="  Ambiente:", bg=BG, fg=FG2, font=FONT_UI).pack(side="left")
        self._env_var = tk.StringVar(value="homologacao")
        for val, lbl in [("homologacao", "Homologação"), ("producao", "Produção")]:
            tk.Radiobutton(r1, text=lbl, variable=self._env_var, value=val,
                           bg=BG, fg=FG, selectcolor=BG3, activebackground=BG,
                           font=FONT_UI).pack(side="left", padx=4)

        tk.Label(r1, text="  CNPJ Interessado:", bg=BG, fg=FG2, font=FONT_UI).pack(side="left")
        self._cnpj_var = tk.StringVar()
        self._cnpj_entry = tk.Entry(r1, textvariable=self._cnpj_var, width=16, bg=BG3, fg=FG,
                                    insertbackground=FG, relief="flat", font=FONT_MON)
        self._cnpj_entry.pack(side="left", padx=4)
        self._btn_conectar = self._btn(r1, "⚡ Conectar", self._conectar)
        self._btn_conectar.pack(side="left", padx=6)

        # ── Endpoint + campos ──
        ep_frame = tk.LabelFrame(self._tab_api, text=" Endpoint ", bg=BG, fg=ACCENT,
                                 font=FONT_UI, bd=1, relief="flat",
                                 highlightbackground=BORDER, highlightthickness=1)
        ep_frame.pack(fill="x", padx=10, pady=4)

        r2 = tk.Frame(ep_frame, bg=BG)
        r2.pack(fill="x", padx=10, pady=6)
        self._ep_var = tk.StringVar(value=_ENDPOINT_LIST[0])
        self._ep_menu = tk.OptionMenu(r2, self._ep_var, *_ENDPOINT_LIST,
                                      command=lambda _v: self._on_endpoint_change())
        self._ep_menu.configure(bg=BG3, fg=FG, font=FONT_MON, relief="flat",
                                activebackground=BG2, activeforeground=ACCENT,
                                width=50, anchor="w", highlightthickness=0,
                                bd=0, padx=8)
        self._ep_menu["menu"].configure(bg=BG2, fg=FG, font=FONT_MON,
                                        activebackground=BG3, activeforeground=ACCENT,
                                        bd=0)
        self._ep_menu.pack(side="left")

        self._btn_enviar = self._btn(r2, "▶  Enviar", self._enviar, width=12)
        self._btn_enviar.pack(side="left", padx=10)
        self._btn_enviar.configure(state="disabled")

        self._btn(r2, "{ } Ver código", self._ver_codigo).pack(side="left", padx=4)

        self._params_nb = ttk.Notebook(ep_frame)
        self._params_nb.pack(fill="x", padx=10, pady=(0, 6))

        self._params_frame = tk.Frame(self._params_nb, bg=BG)
        self._aux_frame    = tk.Frame(self._params_nb, bg=BG)
        self._help_frame   = tk.Frame(self._params_nb, bg=BG)
        self._params_nb.add(self._params_frame, text=" Parâmetros ")
        self._params_nb.add(self._aux_frame,    text=" Auxiliares ")
        self._params_nb.add(self._help_frame,   text=" ℹ Ajuda ")

        # Style do Notebook
        s_nb = ttk.Style()
        s_nb.configure("TNotebook", background=BG, borderwidth=0)
        s_nb.configure("TNotebook.Tab", background=BG3, foreground=FG2,
                       padding=[12, 4], font=FONT_UI)
        s_nb.map("TNotebook.Tab",
                 background=[("selected", BG2)],
                 foreground=[("selected", ACCENT)])

        self._build_aux_fields()
        self._build_help_pane()

        # ── Request / Response ──
        panes = tk.PanedWindow(self._tab_api, orient="horizontal", bg=BG,
                               sashrelief="flat", sashwidth=4)
        panes.pack(fill="both", expand=True, padx=10, pady=4)

        left = tk.Frame(panes, bg=BG)
        tk.Label(left, text="REQUEST", bg=BG, fg=ACCENT, font=FONT_UI).pack(anchor="w")
        self._txt_req = scrolledtext.ScrolledText(
            left, bg=BG2, fg=YELLOW, font=FONT_MON, relief="flat",
            insertbackground=FG, wrap="none", height=18)
        self._txt_req.pack(fill="both", expand=True)
        panes.add(left, stretch="always")

        right = tk.Frame(panes, bg=BG)
        tk.Label(right, text="RESPONSE", bg=BG, fg=ACCENT, font=FONT_UI).pack(anchor="w")
        self._txt_resp = scrolledtext.ScrolledText(
            right, bg=BG2, fg=GREEN, font=FONT_MON, relief="flat",
            insertbackground=FG, wrap="none", height=18)
        self._txt_resp.pack(fill="both", expand=True)
        panes.add(right, stretch="always")

        # ── Status bar ──
        self._status_var = tk.StringVar(value="Desconectado — carregue um certificado e clique Conectar")
        sb = tk.Label(self, textvariable=self._status_var, bg=BG3, fg=FG2,
                      font=FONT_UI, anchor="w", padx=10, pady=3)
        sb.pack(fill="x", side="bottom")

        # ── Barra inferior ──
        bbar = tk.Frame(self, bg=BG)
        bbar.pack(fill="x", side="bottom", padx=10, pady=4)

        self._btn_pendentes = self._btn(
            bbar, "⚠ Pendentes encerramento", self._ver_pendentes)
        self._btn_pendentes.pack(side="right", padx=4)
        self._btn_pendentes.configure(state="disabled")

        self._btn(bbar, "📄 Ver Log", self._abrir_log).pack(side="right", padx=4)

        self._btn_ops = self._btn(bbar, "📊 Operações (CIOTs)",
                                  lambda: self._main_nb.select(self._tab_ops))
        self._btn_ops.pack(side="right", padx=4)
        self._btn_ops.configure(state="disabled")

        self._eye_btn = self._btn(bbar, "👁 Ocultar dados", self._toggle_mask)
        self._eye_btn.pack(side="left", padx=4)

        # ── TTK style ──
        s = ttk.Style()
        s.theme_use("clam")
        s.configure("TCombobox", fieldbackground=BG3, background=BG3,
                    foreground=FG, arrowcolor=ACCENT, borderwidth=0)

        # ── Aba operações ──
        self._build_ops_tab()

    # ── Painel de Ajuda ───────────────────────────────────────────────────────

    def _build_help_pane(self):
        # Cabeçalho fixo
        hdr = tk.Frame(self._help_frame, bg=BG)
        hdr.pack(fill="x", padx=4, pady=4)
        self._help_title = tk.Label(hdr, text="", bg=BG, fg=ACCENT, font=FONT_UI, anchor="w")
        self._help_title.pack(side="left")

        # Conteúdo scrollable
        self._help_text = scrolledtext.ScrolledText(
            self._help_frame, bg=BG2, fg=FG, font=FONT_MON, relief="flat",
            wrap="word", height=14, padx=8, pady=4
        )
        self._help_text.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self._help_text.configure(state="disabled")

    def _update_help(self, ep_id: str):
        if not hasattr(self, "_help_text"):
            return
        content = (_HELP_ENDPOINTS.get(ep_id, "") + "\n\n" + _HELP_AUX).strip()
        self._help_text.configure(state="normal")
        self._help_text.delete("1.0", "end")
        self._help_text.insert("1.0", content)
        self._help_text.configure(state="disabled")
        ep_name = _ENDPOINT_NAMES.get(ep_id, "?")
        self._help_title.configure(text=f"Endpoint {ep_id} — {ep_name}")

    # ── Campos auxiliares (grade 2 colunas) ───────────────────────────────────

    def _build_aux_fields(self):
        for i, (label, key, placeholder) in enumerate(_FIELDS_AUX):
            col = i % 2
            row_idx = i // 2
            cell = tk.Frame(self._aux_frame, bg=BG)
            cell.grid(row=row_idx, column=col, sticky="w", padx=6, pady=2)

            tk.Label(cell, text=label + ":", bg=BG, fg=FG2,
                     font=FONT_UI, width=28, anchor="w").pack(side="left")

            var = tk.StringVar(value=self._saved_fields.get(key, placeholder))
            tk.Entry(cell, textvariable=var, width=18, bg=BG3, fg=FG,
                     insertbackground=FG, relief="flat", font=FONT_MON).pack(side="left", padx=4)
            self._aux_vars[key] = var

    # ── Botão padrão ──────────────────────────────────────────────────────────

    def _btn(self, parent, text, cmd, width=None):
        kw = dict(text=text, command=cmd, bg=ACCENT, fg=BG,
                  font=(*FONT_UI[:1], FONT_UI[1], "bold"),
                  relief="flat", padx=8, pady=3, cursor="hand2",
                  activebackground=FG, activeforeground=BG)
        if width:
            kw["width"] = width
        return tk.Button(parent, **kw)

    # ── Config persistência ───────────────────────────────────────────────────

    def _preload_saved_fields(self):
        """Carrega só _saved_fields em memória ANTES de construir widgets."""
        cfg = _load_config()
        saved = cfg.get("saved_fields", {})
        # Migra formato antigo (aninhado por ep_id) → flat
        if any(isinstance(v, dict) for v in saved.values()):
            flat: dict[str, str] = {}
            for ep_dict in saved.values():
                if isinstance(ep_dict, dict):
                    flat.update(ep_dict)
            saved = flat
        self._saved_fields = saved

    def _carregar_config(self):
        # _saved_fields já foi populado por _preload_saved_fields antes do _build_ui.
        # Aqui só aplicamos cert/senha/cnpj/env nos widgets já criados e
        # garantimos que os _aux_vars refletem _saved_fields.
        cfg = _load_config()
        if cfg.get("cert_pfx"):
            self._cert_var.set(cfg["cert_pfx"])
        if cfg.get("cert_password"):
            self._pass_var.set(cfg["cert_password"])
        if cfg.get("cnpj_interessado"):
            self._cnpj_var.set(cfg["cnpj_interessado"])
        if cfg.get("env"):
            self._env_var.set(cfg["env"])
        # Sincroniza _aux_vars (já criadas) com valores carregados
        for key, var in self._aux_vars.items():
            if key in self._saved_fields:
                var.set(self._saved_fields[key])
        self._on_endpoint_change()

    def _salvar_config(self):
        if self._field_vars:
            for k, var in self._field_vars.items():
                self._saved_fields[k] = _norm_field(k, var.get())
        if self._aux_vars:
            for k, var in self._aux_vars.items():
                self._saved_fields[k] = var.get()
        _save_config({
            "cert_pfx": self._cert_var.get().strip(),
            "cert_password": self._pass_var.get(),
            "cnpj_interessado": self._cnpj_var.get().strip(),
            "env": self._env_var.get(),
            "saved_fields": self._saved_fields,
        })

    # ── Browse certificado ────────────────────────────────────────────────────

    def _browse_cert(self):
        path = filedialog.askopenfilename(
            title="Selecione o certificado A1",
            filetypes=[("Certificado", "*.pfx *.p12"), ("Todos", "*.*")])
        if path:
            self._cert_var.set(path)

    # ── Conectar ──────────────────────────────────────────────────────────────

    def _conectar(self):
        from ciot_antt import CiotClient
        from ciot_antt.exceptions import CiotAuthError

        self._status("Carregando certificado...", YELLOW)
        self.update()
        try:
            dll_dir = self._saved_fields.get("aux_dll_geradorciot_dir", "").strip() or None
            self._client = CiotClient(
                cert_pfx=self._cert_var.get().strip(),
                cert_password=self._pass_var.get(),
                cnpj_interessado=self._cnpj_var.get().strip(),
                env=self._env_var.get(),
                dll_geradorciot_dir=dll_dir,
            )
            # Hook de log: captura request+response brutos para o arquivo de log
            def _log_hook(resp, *args, **kwargs):
                _log.info(
                    "\n=== %s %s ===\nHTTP %s\n"
                    "--- REQUEST HEADERS ---\n%s\n"
                    "--- REQUEST BODY ---\n%s\n"
                    "--- RESPONSE HEADERS ---\n%s\n"
                    "--- RESPONSE BODY ---\n%s\n",
                    resp.request.method, resp.url,
                    resp.status_code,
                    dict(resp.request.headers),
                    resp.request.body or "(vazio)",
                    dict(resp.headers),
                    resp.text[:4000],
                )
            self._client._session.hooks["response"].append(_log_hook)

            self._salvar_config()
            env_label = "Homologação" if self._env_var.get() == "homologacao" else "Produção"
            self._status(f"✓ Conectado — {env_label} | config salva", GREEN)
            self._btn_enviar.configure(state="normal")
            self._btn_pendentes.configure(state="normal")
            self._btn_ops.configure(state="normal")
            self._atualizar_ops_grid()
        except CiotAuthError as e:
            _log.error("Erro de certificado: %s", e)
            self._status(f"✗ Erro de certificado: {e}", RED)
        except Exception as e:
            _log.error("Erro ao conectar: %s", e, exc_info=True)
            self._status(f"✗ {e}", RED)

    # ── Troca de endpoint ─────────────────────────────────────────────────────

    def _on_endpoint_change(self):
        # Salva valores atuais (flat, cross-endpoint), já normalizando CPF/CNPJ/RNTRC
        if self._field_vars:
            for k, var in self._field_vars.items():
                self._saved_fields[k] = _norm_field(k, var.get())
        if self._aux_vars:
            for k, var in self._aux_vars.items():
                self._saved_fields[k] = var.get()

        selected = self._ep_var.get()
        ep_id = selected[:2] if selected else "01"
        self._current_ep_id = ep_id

        for w in self._field_widgets:
            w.destroy()
        self._field_widgets.clear()
        self._field_vars.clear()
        self._sensitive_entries.clear()

        if ep_id in _TEMPLATES:
            self._build_json_area(ep_id)
        elif ep_id in _FIELDS:
            self._build_simple_fields(ep_id)

        self._update_help(ep_id)

    def _build_simple_fields(self, ep_id: str):
        for label, key, placeholder in _FIELDS[ep_id]:
            row = tk.Frame(self._params_frame, bg=BG)
            row.pack(fill="x", pady=2)
            self._field_widgets.append(row)

            lbl = tk.Label(row, text=label + ":", bg=BG, fg=FG2,
                           font=FONT_UI, width=26, anchor="w")
            lbl.pack(side="left")
            self._field_widgets.append(lbl)

            is_sensitive = "cpf_cnpj" in key or "rntrc" in key
            show_char = "*" if (is_sensitive and self._mask_mode) else ""
            var = tk.StringVar(value=self._saved_fields.get(key, placeholder))
            entry = tk.Entry(row, textvariable=var, width=40, bg=BG3, fg=FG,
                             insertbackground=FG, relief="flat", font=FONT_MON,
                             show=show_char)
            entry.pack(side="left", padx=4)
            self._field_widgets.append(entry)
            self._field_vars[key] = var
            if is_sensitive:
                self._sensitive_entries.append(entry)

    def _build_json_area(self, ep_id: str):
        header = tk.Frame(self._params_frame, bg=BG)
        header.pack(fill="x", pady=(2, 0))
        self._field_widgets.append(header)

        tk.Label(header, text="Payload JSON (editável):",
                 bg=BG, fg=FG2, font=FONT_UI).pack(side="left")

        if ep_id == "03":
            btn = self._btn(header, "🔄 Regenerar do Auxiliares", self._regenerar_json_03)
            btn.pack(side="right")
            self._field_widgets.append(btn)

        self._json_input = scrolledtext.ScrolledText(
            self._params_frame, bg=BG2, fg=YELLOW, font=FONT_MON,
            relief="flat", insertbackground=FG, height=14, wrap="none")
        if ep_id == "03":
            content = _build_template_03(self._saved_fields, self._cnpj_var.get())
        else:
            content = _TEMPLATES[ep_id]
        self._json_input.insert("1.0", content)
        self._json_input.pack(fill="x", pady=2)
        self._field_widgets.append(self._json_input)

    def _regenerar_json_03(self):
        # Salva valores atuais dos aux_vars em _saved_fields
        if self._aux_vars:
            for k, var in self._aux_vars.items():
                self._saved_fields[k] = var.get()
        if self._field_vars:
            for k, var in self._field_vars.items():
                self._saved_fields[k] = _norm_field(k, var.get())
        # Regenera JSON
        content = _build_template_03(self._saved_fields, self._cnpj_var.get())
        self._json_input.delete("1.0", "end")
        self._json_input.insert("1.0", content)
        self._status("✓ JSON regenerado dos auxiliares", GREEN)

    # ── Enviar ────────────────────────────────────────────────────────────────

    def _enviar(self):
        if not self._client:
            self._status("✗ Clique em Conectar primeiro", RED)
            return
        self._btn_enviar.configure(state="disabled", text="⏳ Aguarde...")
        self._txt_req.delete("1.0", "end")
        self._txt_resp.delete("1.0", "end")
        threading.Thread(target=self._enviar_thread, daemon=True).start()

    def _enviar_thread(self):
        ep_id = self._current_ep_id or self._ep_var.get()[:2]
        t0 = time.perf_counter()
        try:
            req_json, resp_obj = self._chamar(ep_id)
            elapsed = int((time.perf_counter() - t0) * 1000)
            self.after(0, self._mostrar_resultado, req_json, resp_obj, elapsed)
        except Exception as e:
            elapsed = int((time.perf_counter() - t0) * 1000)
            self.after(0, self._mostrar_erro, str(e), elapsed)

    def _chamar(self, ep_id: str):
        from ciot_antt import (
            CancelamentoInput, DadosCargaInput, DeclaracaoInput, DestinoInput,
            EncerramentoInput, IndicadoresOperacionaisInput, InfPagamentoInput,
            OrigemDestinoInput, OrigemInput, RetificacaoInput,
            TipoOperacao, TipoPagamento, VeiculoInput,
        )
        c = self._client

        def v(key, default=""):
            raw = self._field_vars.get(key, tk.StringVar(value=default)).get().strip()
            return _norm_field(key, raw)

        def ciot():
            return v("codigo_ciot")

        if ep_id == "01":
            req = {"cpf_cnpj_transportador": v("cpf_cnpj_transportador"),
                   "rntrc_transportador": v("rntrc_transportador")}
            resp = c.consultar_situacao_transportador(**req)

        elif ep_id == "02":
            placas = [p.strip() for p in v("placas").split(",") if p.strip()]
            req = {"cpf_cnpj_transportador": v("cpf_cnpj_transportador"),
                   "rntrc_transportador": v("rntrc_transportador"),
                   "placas": placas}
            resp = c.consultar_frota_transportador(**req)

        elif ep_id == "03":
            raw = json.loads(self._json_input.get("1.0", "end"))
            _normalize_payload(raw)
            req = raw
            veiculos = [VeiculoInput(**vv) for vv in raw.get("veiculos", [])]
            ind_op_raw = raw.get("indicadores_operacionais")
            ind_op = IndicadoresOperacionaisInput(**ind_op_raw) if ind_op_raw else None
            dados_carga_raw = raw.get("dados_carga")
            dados_carga = DadosCargaInput(**dados_carga_raw) if dados_carga_raw else None
            origem_destino = []
            for od in raw.get("origem_destino", []):
                o_raw = od.get("origem") or {}
                d_raw = od.get("destino") or {}
                origem_destino.append(OrigemDestinoInput(
                    origem=OrigemInput(**o_raw),
                    destino=DestinoInput(**d_raw),
                    distancia_percorrida=od.get("distancia_percorrida"),
                    qtd_viagens=od.get("qtd_viagens"),
                ))
            pagamentos = []
            for p in raw.get("inf_pagamento", []):
                pagamentos.append(InfPagamentoInput(
                    tipo_pagamento=TipoPagamento(p["tipo_pagamento"]),
                    cpf_cnpj_creditado=p["cpf_cnpj_creditado"],
                    ind_pagamento=p["ind_pagamento"],
                    chave_pix=p.get("chave_pix"),
                    codigo_instituicao_financeira=p.get("codigo_instituicao_financeira"),
                    numero_agencia=p.get("numero_agencia"),
                    numero_conta=p.get("numero_conta"),
                    codigo_pagamento=p.get("codigo_pagamento"),
                    identificador_pix=p.get("identificador_pix"),
                ))
            dados = DeclaracaoInput(
                tipo_operacao=TipoOperacao(raw["tipo_operacao"]),
                cpf_cnpj_contratado=raw["cpf_cnpj_contratado"],
                rntrc_contratado=raw["rntrc_contratado"],
                cpf_cnpj_contratante=raw["cpf_cnpj_contratante"],
                cpf_cnpj_destinatario=raw.get("cpf_cnpj_destinatario"),
                id_operacao=raw.get("id_operacao") or None,  # se vier da DLL ANTT
                valor_frete=float(raw["valor_frete"]),
                data_inicio_viagem=raw["data_inicio_viagem"],
                data_fim_viagem=raw["data_fim_viagem"],
                veiculos=veiculos,
                inf_pagamento=pagamentos,
                dados_carga=dados_carga,
                origem_destino=origem_destino,
                indicadores_operacionais=ind_op,
            )
            resp = c.declarar_operacao(dados)

        elif ep_id == "04":
            req = {"codigo_identificacao_operacao": ciot(), "motivo_cancelamento": v("motivo")}
            resp = c.cancelar_operacao(CancelamentoInput(**req))

        elif ep_id == "05":
            kwargs: dict = {"codigo_identificacao_operacao": ciot()}
            if v("valor_frete"):
                kwargs["valor_frete"] = float(v("valor_frete"))
            if v("data_fim"):
                kwargs["data_fim_viagem"] = v("data_fim")
            req = kwargs
            resp = c.retificar_operacao(RetificacaoInput(**kwargs))

        elif ep_id == "06":
            kwargs = {"codigo_identificacao_operacao": ciot()}
            if v("peso_carga"):
                kwargs["peso_carga"] = float(v("peso_carga"))
            req = kwargs
            resp = c.encerrar_operacao(EncerramentoInput(**kwargs))

        elif ep_id == "07":
            req = {"id_operacao": v("id_operacao")}
            resp = c.consultar_ciot_gerado(**req)

        elif ep_id == "08":
            req = {"cpf_cnpj_transportador": v("cpf_cnpj_transportador")}
            resp = c.consultar_excecao(**req)

        else:
            raise ValueError(f"Endpoint {ep_id!r} não mapeado")

        return req, resp

    def _mostrar_resultado(self, req, resp_obj, elapsed_ms: int):
        import dataclasses
        self._last_req_json = json.dumps(req, indent=2, ensure_ascii=False, default=str)
        resp_dict = dataclasses.asdict(resp_obj) if dataclasses.is_dataclass(resp_obj) else vars(resp_obj)
        self._last_resp_json = json.dumps(resp_dict, indent=2, ensure_ascii=False, default=str)

        self._txt_req.delete("1.0", "end")
        self._txt_req.insert("1.0", _mask_json_str(self._last_req_json) if self._mask_mode else self._last_req_json)

        self._txt_resp.delete("1.0", "end")
        self._txt_resp.insert("1.0", _mask_json_str(self._last_resp_json) if self._mask_mode else self._last_resp_json)

        codigo = getattr(resp_obj, "codigo", "")
        if isinstance(codigo, list):
            codigo = codigo[0] if codigo else ""
        cor = GREEN if codigo in ("000000", "110", "111") else RED
        self._status(f"⏱ {elapsed_ms}ms  |  Código: {codigo}", cor)
        self._btn_enviar.configure(state="normal", text="▶  Enviar")
        # Atualiza grid de operações após cada chamada (declaração/cancel/retif/encerra mexem no storage)
        self._atualizar_ops_grid()

    def _mostrar_erro(self, msg: str, elapsed_ms: int):
        self._txt_resp.delete("1.0", "end")
        self._txt_resp.insert("1.0", msg)
        self._txt_resp.configure(fg=RED)
        self._status(f"✗ Erro ({elapsed_ms}ms): {msg[:120]}", RED)
        self._btn_enviar.configure(state="normal", text="▶  Enviar")
        self.after(100, lambda: self._txt_resp.configure(fg=GREEN))

    # ── Ver log ───────────────────────────────────────────────────────────────

    def _abrir_log(self):
        if not _LOG_FILE.exists():
            self._status("Nenhum log gerado ainda.", YELLOW)
            return
        win = tk.Toplevel(self)
        win.title(f"Log — {_LOG_FILE}")
        win.configure(bg=BG)
        win.geometry("900x500")

        bar = tk.Frame(win, bg=BG)
        bar.pack(fill="x", padx=8, pady=4)
        self._btn(bar, "Atualizar", lambda: _refresh()).pack(side="left")
        self._btn(bar, "Abrir no editor", lambda: _open_editor()).pack(side="left", padx=6)
        self._btn(bar, "Limpar log", lambda: _clear()).pack(side="left")

        txt = scrolledtext.ScrolledText(win, bg=BG2, fg=FG2, font=FONT_MON,
                                        relief="flat", wrap="none")
        txt.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        def _refresh():
            content = _LOG_FILE.read_text(encoding="utf-8", errors="replace")
            txt.delete("1.0", "end")
            txt.insert("1.0", content)
            txt.see("end")

        def _open_editor():
            if sys.platform == "win32":
                os.startfile(str(_LOG_FILE))
            else:
                subprocess.Popen(["xdg-open", str(_LOG_FILE)])

        def _clear():
            _LOG_FILE.write_text("", encoding="utf-8")
            txt.delete("1.0", "end")

        _refresh()

    # ── Aba Operações (browser de CIOTs embedded) ────────────────────────────

    _OPS_COLS = (
        "id_operacao", "ciot_codigo", "ciot_verificador", "status",
        "tipo_operacao", "data_declaracao", "data_inicio_viagem", "data_fim_viagem",
        "data_limite_encerramento", "data_encerramento",
        "cpf_cnpj_contratado", "valor_frete", "protocolo", "created_at", "updated_at",
    )
    _OPS_COL_WIDTHS = {
        "id_operacao": 110, "ciot_codigo": 110, "ciot_verificador": 80,
        "status": 80, "tipo_operacao": 60, "data_declaracao": 140,
        "data_inicio_viagem": 100, "data_fim_viagem": 100,
        "data_limite_encerramento": 130, "data_encerramento": 130,
        "cpf_cnpj_contratado": 120, "valor_frete": 80, "protocolo": 130,
        "created_at": 140, "updated_at": 140,
    }

    def _build_ops_tab(self):
        # Toolbar
        topo = tk.Frame(self._tab_ops, bg=BG)
        topo.pack(fill="x", padx=8, pady=6)
        tk.Label(topo, text="Filtrar status:", bg=BG, fg=FG2, font=FONT_UI).pack(side="left")
        self._ops_filtro = tk.StringVar(value="todas")
        for val, lbl in [("todas", "Todas"), ("declarada", "Declaradas"),
                          ("retificada", "Retificadas"), ("cancelada", "Canceladas"),
                          ("encerrada", "Encerradas")]:
            tk.Radiobutton(topo, text=lbl, variable=self._ops_filtro, value=val,
                           bg=BG, fg=FG, selectcolor=BG3, activebackground=BG,
                           font=FONT_UI, command=self._atualizar_ops_grid).pack(side="left", padx=4)

        self._ops_count_lbl = tk.Label(topo, text="", bg=BG, fg=FG2, font=FONT_UI)
        self._ops_count_lbl.pack(side="right", padx=8)
        self._btn(topo, "🔄 Atualizar", self._atualizar_ops_grid).pack(side="right", padx=4)

        # Grid
        grid_frame = tk.Frame(self._tab_ops, bg=BG)
        grid_frame.pack(fill="both", expand=True, padx=8, pady=4)

        self._ops_tree = ttk.Treeview(grid_frame, columns=self._OPS_COLS,
                                      show="headings", height=18,
                                      selectmode="browse")
        for c in self._OPS_COLS:
            self._ops_tree.heading(c, text=c.replace("_", " ").title())
            self._ops_tree.column(c, width=self._OPS_COL_WIDTHS.get(c, 100), anchor="w")

        # Scrollbar
        sb_v = ttk.Scrollbar(grid_frame, orient="vertical", command=self._ops_tree.yview)
        sb_h = ttk.Scrollbar(grid_frame, orient="horizontal", command=self._ops_tree.xview)
        self._ops_tree.configure(yscrollcommand=sb_v.set, xscrollcommand=sb_h.set)

        sb_v.pack(side="right", fill="y")
        sb_h.pack(side="bottom", fill="x")
        self._ops_tree.pack(fill="both", expand=True)

        style = ttk.Style()
        style.configure("Treeview", background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=24, font=FONT_MON)
        style.configure("Treeview.Heading", background=BG3, foreground=ACCENT, font=FONT_UI)
        style.map("Treeview", background=[("selected", BG3)], foreground=[("selected", ACCENT)])

        # Tags de cor por status
        self._ops_tree.tag_configure("declarada", foreground=YELLOW)
        self._ops_tree.tag_configure("cancelada", foreground=RED)
        self._ops_tree.tag_configure("retificada", foreground=ACCENT)
        self._ops_tree.tag_configure("encerrada", foreground=GREEN)

        # Double-click = abrir menu de ações
        self._ops_tree.bind("<Double-Button-1>", lambda _e: self._abrir_menu_acoes())
        self._ops_tree.bind("<Button-3>",        lambda e: self._abrir_menu_acoes(e))

        # Barra de ações
        bar = tk.Frame(self._tab_ops, bg=BG)
        bar.pack(fill="x", padx=8, pady=4)

        self._btn(bar, "⚙ Ações ▾", self._abrir_menu_acoes).pack(side="left", padx=4)
        self._btn(bar, "📋 Copiar CIOT",  self._copiar_ciot_linha).pack(side="left", padx=4)
        self._btn(bar, "📄 Ver Req/Resp", self._ver_json_linha).pack(side="left", padx=4)

        # Legenda
        leg = tk.Frame(self._tab_ops, bg=BG)
        leg.pack(fill="x", padx=8, pady=(0, 6))
        tk.Label(leg, text="Status: ", bg=BG, fg=FG2, font=FONT_UI).pack(side="left")
        for lbl, cor in [("declarada", YELLOW), ("retificada", ACCENT),
                         ("encerrada", GREEN), ("cancelada", RED)]:
            tk.Label(leg, text=f"● {lbl}", bg=BG, fg=cor, font=FONT_UI).pack(side="left", padx=6)
        tk.Label(leg, text="  •  Duplo clique ou clique direito numa linha = ações disponíveis",
                 bg=BG, fg=FG2, font=FONT_UI).pack(side="right")

    def _op_selecionada(self) -> Optional[dict]:
        sel = self._ops_tree.selection() if hasattr(self, "_ops_tree") else None
        if not sel:
            return None
        vals = self._ops_tree.item(sel[0], "values")
        return {c: v for c, v in zip(self._OPS_COLS, vals)}

    def _atualizar_ops_grid(self):
        if not hasattr(self, "_ops_tree"):
            return
        if not self._client:
            self._ops_count_lbl.configure(text="(desconectado — nada para exibir)")
            for r in self._ops_tree.get_children():
                self._ops_tree.delete(r)
            return
        for r in self._ops_tree.get_children():
            self._ops_tree.delete(r)
        status = None if self._ops_filtro.get() == "todas" else self._ops_filtro.get()
        ops = self._client.storage.listar_todas(status=status)
        for op in ops:
            vals = [op.get(c, "") for c in self._OPS_COLS]
            self._ops_tree.insert("", "end", values=vals, tags=(op.get("status", ""),))
        self._ops_count_lbl.configure(text=f"{len(ops)} operações")

    def _abrir_menu_acoes(self, event=None):
        # Garante seleção quando vier de click direito
        if event is not None:
            row_id = self._ops_tree.identify_row(event.y)
            if row_id:
                self._ops_tree.selection_set(row_id)

        op = self._op_selecionada()
        if not op:
            self._status("Selecione uma operação no grid primeiro", YELLOW)
            return

        m = tk.Menu(self, tearoff=0, bg=BG2, fg=FG, font=FONT_UI,
                   activebackground=BG3, activeforeground=ACCENT, bd=0)
        status = (op.get("status") or "").lower()

        # Sempre permitido
        m.add_command(label="📋 Copiar CIOT", command=self._copiar_ciot_linha)
        m.add_command(label="🔍 Consultar CIOT (07)",
                      command=lambda: self._ir_endpoint_com_op("07", op))
        m.add_command(label="📄 Ver Request/Response", command=self._ver_json_linha)
        m.add_separator()

        # Conforme status
        if status in ("declarada", "retificada"):
            m.add_command(label="✏ Retificar (05)",
                          command=lambda: self._ir_endpoint_com_op("05", op))
            m.add_command(label="✓ Encerrar (06)",
                          command=lambda: self._ir_endpoint_com_op("06", op))
            m.add_command(label="🛑 Cancelar (04)",
                          command=lambda: self._ir_endpoint_com_op("04", op))
        else:
            m.add_command(label=f"(operação {status} — só consulta)", state="disabled")

        # Posicionar
        if event is not None:
            m.tk_popup(event.x_root, event.y_root)
        else:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            m.tk_popup(x, y)

    def _ir_endpoint_com_op(self, ep_id: str, op: dict):
        """Troca o endpoint atual e preenche o CIOT/IdOperacao com os dados da operação."""
        ep_label = f"{ep_id} — {_ENDPOINT_NAMES.get(ep_id, '')}"
        self._ep_var.set(ep_label)
        self._on_endpoint_change()

        ciot_full = (op.get("ciot_codigo") or "") + (op.get("ciot_verificador") or "")

        if "codigo_ciot" in self._field_vars and ciot_full:
            self._field_vars["codigo_ciot"].set(ciot_full)
            preview = ciot_full
        elif "id_operacao" in self._field_vars:
            self._field_vars["id_operacao"].set(op.get("id_operacao", ""))
            preview = op.get("id_operacao", "")
        else:
            preview = "?"

        # Volta para aba API
        self._main_nb.select(self._tab_api)
        self._status(f"→ Endpoint {ep_id} preenchido com {preview}", ACCENT)

    def _copiar_ciot_linha(self):
        op = self._op_selecionada()
        if not op:
            self._status("Selecione uma operação no grid primeiro", YELLOW)
            return
        ciot_full = (op.get("ciot_codigo") or "") + (op.get("ciot_verificador") or "")
        if not ciot_full:
            self._status("Operação sem CIOT gerado", YELLOW)
            return
        self.clipboard_clear()
        self.clipboard_append(ciot_full)
        self._status(f"CIOT {ciot_full} copiado para a área de transferência", GREEN)

    def _ver_json_linha(self):
        op = self._op_selecionada()
        if not op:
            self._status("Selecione uma operação no grid primeiro", YELLOW)
            return
        full = self._client.storage.buscar_por_id_operacao(op.get("id_operacao", ""))
        if not full:
            self._status("Operação não encontrada no banco", RED)
            return

        win = tk.Toplevel(self)
        win.title(f"Operação {op.get('id_operacao', '')} — JSON")
        win.configure(bg=BG)
        win.geometry("920x540")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        for lang, key in [("REQUEST", "request_json"), ("RESPONSE", "response_json")]:
            f = tk.Frame(nb, bg=BG2)
            nb.add(f, text=f" {lang} ")
            txt = scrolledtext.ScrolledText(f, bg=BG2, fg=FG, font=FONT_MON,
                                            relief="flat", wrap="none")
            txt.pack(fill="both", expand=True, padx=6, pady=6)
            raw = full.get(key, "") or ""
            try:
                pretty = json.dumps(json.loads(raw), indent=2, ensure_ascii=False, default=str)
            except Exception:
                pretty = raw
            display = _mask_json_str(pretty) if self._mask_mode else pretty
            txt.insert("1.0", display)
            txt.configure(state="disabled")

    # ── Ver pendentes ─────────────────────────────────────────────────────────

    def _ver_pendentes(self):
        if not self._client:
            return
        pendentes = self._client.storage.listar_pendentes_encerramento(dias_aviso=1)
        win = tk.Toplevel(self)
        win.title(f"CIOTs pendentes de encerramento ({len(pendentes)})")
        win.configure(bg=BG)
        win.geometry("760x320")

        if not pendentes:
            tk.Label(win, text="Nenhum CIOT pendente de encerramento.",
                     bg=BG, fg=GREEN, font=FONT_UI).pack(pady=20)
            return

        cols = ("id_operacao", "ciot_codigo", "tipo_operacao", "status",
                "data_limite_encerramento", "valor_frete")
        tree = ttk.Treeview(win, columns=cols, show="headings", height=10)
        for c in cols:
            tree.heading(c, text=c.replace("_", " ").title())
            tree.column(c, width=120, anchor="w")

        style = ttk.Style()
        style.configure("Treeview", background=BG2, foreground=FG,
                        fieldbackground=BG2, rowheight=22, font=FONT_MON)
        style.configure("Treeview.Heading", background=BG3, foreground=ACCENT,
                        font=FONT_UI)

        for row in pendentes:
            tree.insert("", "end", values=[row.get(c, "") for c in cols],
                        tags=("vencido",))
        tree.tag_configure("vencido", foreground=RED)
        tree.pack(fill="both", expand=True, padx=8, pady=8)

    # ── Máscara de dados sensíveis ────────────────────────────────────────────

    def _toggle_mask(self):
        self._mask_mode = not self._mask_mode
        show = "*" if self._mask_mode else ""
        label = "🙈 Mascarado" if self._mask_mode else "👁 Ocultar dados"
        color = YELLOW if self._mask_mode else ACCENT
        self._eye_btn.configure(text=label, bg=color)

        # Entry CNPJ Interessado
        self._cnpj_entry.configure(show=show)

        # Entries sensíveis dos campos de endpoint
        for e in self._sensitive_entries:
            e.configure(show=show)

        # Re-exibir JSONs com/sem máscara
        if self._last_req_json:
            display = _mask_json_str(self._last_req_json) if self._mask_mode else self._last_req_json
            self._txt_req.delete("1.0", "end")
            self._txt_req.insert("1.0", display)
        if self._last_resp_json:
            display = _mask_json_str(self._last_resp_json) if self._mask_mode else self._last_resp_json
            self._txt_resp.delete("1.0", "end")
            self._txt_resp.insert("1.0", display)

    # ── Status bar ────────────────────────────────────────────────────────────

    def _status(self, msg: str, cor: str = FG2):
        self._status_var.set(msg)
        for w in self.winfo_children():
            if isinstance(w, tk.Label) and w.cget("textvariable") == str(self._status_var):
                w.configure(fg=cor)
                break
        # Busca direta pelo label de status
        self._update_status_color(cor)

    def _update_status_color(self, cor: str):
        for w in self.winfo_children():
            if isinstance(w, tk.Label):
                try:
                    if str(w.cget("textvariable")) == str(self._status_var):
                        w.configure(fg=cor)
                except Exception:
                    pass

    # ── Ver código de exemplo ─────────────────────────────────────────────────

    def _ep_payload(self, ep_id: str) -> dict:
        """Monta o payload para o endpoint atual com os valores dos campos."""
        def v(key, default=""):
            if key in self._field_vars:
                raw = self._field_vars[key].get().strip()
                return _norm_field(key, raw)
            return default

        base = self._base_url() if self._client else "https://appservices-hml.antt.gov.br/pefServices/api"
        cnpj = self._cnpj_var.get().strip()

        if ep_id == "01":
            return {"CPFCNPJInteressado": cnpj, "CPFCNPJTransportador": v("cpf_cnpj_transportador"),
                    "RNTRCTransportador": v("rntrc_transportador")}
        if ep_id == "02":
            placas = [p.strip() for p in v("placas", "ABC1234").split(",") if p.strip()]
            return {"CPFCNPJInteressado": cnpj, "CPFCNPJTransportador": v("cpf_cnpj_transportador"),
                    "RNTRCTransportador": v("rntrc_transportador"), "Placas": placas}
        if ep_id == "03":
            try:
                return json.loads(self._json_input.get("1.0", "end"))
            except Exception:
                return {"tipo_operacao": 1, "cpf_cnpj_contratado": "00000000000"}
        if ep_id == "04":
            return {"CodigoIdentificacaoOperacao": v("codigo_ciot"), "MotivoCancelamento": v("motivo")}
        if ep_id == "05":
            return {"CodigoIdentificacaoOperacao": v("codigo_ciot"), "ValorFrete": v("valor_frete"),
                    "DataFimViagem": v("data_fim")}
        if ep_id == "06":
            return {"CodigoIdentificacaoOperacao": v("codigo_ciot"), "PesoCarga": v("peso_carga")}
        if ep_id == "07":
            return {"CPFCNPJInteressado": cnpj, "IdOperacaoTransporte": v("id_operacao")}
        if ep_id == "08":
            return {"CPFCNPJTransportador": v("cpf_cnpj_transportador")}
        return {}

    def _base_url(self) -> str:
        env = self._env_var.get()
        return ("https://appservices.antt.gov.br/pefServices/api"
                if env == "producao"
                else "https://appservices-hml.antt.gov.br/pefServices/api")

    def _ver_codigo(self):
        ep_id = self._current_ep_id or (self._ep_var.get()[:2] if self._ep_var.get() else "01")
        ep_name = _ENDPOINT_NAMES.get(ep_id, ep_id)
        base = self._base_url()
        url = f"{base}/{ep_name}"
        method = "GET" if ep_id == "08" else "POST"
        payload = self._ep_payload(ep_id)
        payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
        cnpj = _strip_doc(self._cnpj_var.get())
        cert_pfx = self._cert_var.get().strip() or "caminho/certificado.pfx"

        codes = {
            "Python (SDK)": _code_python_sdk(ep_id, ep_name, cnpj, cert_pfx, payload),
            "Python (requests)": _code_python_raw(url, method, payload_json, cert_pfx),
            "C#": _code_csharp(url, method, ep_name, payload_json, cert_pfx),
            "WLanguage": _code_wlanguage(url, method, payload_json, cert_pfx),
            "Harbour": _code_harbour(url, method, payload_json, cert_pfx),
            "Pascal": _code_pascal(url, method, payload_json, cert_pfx),
            "COBOL": _code_cobol(url, method, payload_json),
        }

        win = tk.Toplevel(self)
        win.title(f"Código — {ep_id} {ep_name}")
        win.configure(bg=BG)
        win.geometry("920x640")

        nb = ttk.Notebook(win)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        style = ttk.Style()
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=BG3, foreground=FG2,
                        padding=[10, 4], font=FONT_UI)
        style.map("TNotebook.Tab", background=[("selected", BG2)],
                  foreground=[("selected", ACCENT)])

        for lang, code in codes.items():
            frame = tk.Frame(nb, bg=BG2)
            nb.add(frame, text=lang)

            bar = tk.Frame(frame, bg=BG2)
            bar.pack(fill="x", padx=6, pady=4)

            def _copiar(c=code):
                win.clipboard_clear()
                win.clipboard_append(c)
                self._status(f"Código {lang} copiado!", ACCENT)

            self._btn(bar, "Copiar", _copiar).pack(side="right")

            txt = scrolledtext.ScrolledText(frame, bg=BG2, fg=FG, font=FONT_MON,
                                            relief="flat", wrap="none")
            txt.pack(fill="both", expand=True, padx=6, pady=(0, 6))
            txt.insert("1.0", code)
            txt.configure(state="disabled")


# ── Geradores de código por linguagem ────────────────────────────────────────

_EP_METHOD_MAP = {
    "01": "consultar_situacao_transportador",
    "02": "consultar_frota_transportador",
    "03": "declarar_operacao",
    "04": "cancelar_operacao",
    "05": "retificar_operacao",
    "06": "encerrar_operacao",
    "07": "consultar_ciot_gerado",
    "08": "consultar_excecao",
}


def _code_python_sdk(ep_id: str, ep_name: str, cnpj: str, cert_pfx: str, payload: dict) -> str:
    method = _EP_METHOD_MAP.get(ep_id, "???")
    args_lines = "\n".join(f"    {k}={repr(v)}," for k, v in payload.items())
    return f"""\
from ciot_antt import CiotClient

client = CiotClient(
    cert_pfx="{cert_pfx}",
    cert_password="SUA_SENHA",
    cnpj_interessado="{cnpj}",
    env="homologacao",  # ou "producao"
)

resultado = client.{method}(
{args_lines}
)

print(resultado.codigo, resultado.mensagem)
"""


def _code_python_raw(url: str, method: str, payload_json: str, cert_pfx: str) -> str:
    if method == "GET":
        req_block = f"""\
resp = session.get(
    "{url}",
    params=payload,
)"""
    else:
        req_block = f"""\
resp = session.post(
    "{url}",
    json=payload,
)"""
    return f"""\
import ssl, tempfile, requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates

with open("{cert_pfx}", "rb") as f:
    pk, cert, chain = load_key_and_certificates(f.read(), b"SUA_SENHA")

with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as tc:
    tc.write(cert.public_bytes(Encoding.PEM))
    for c in (chain or []):
        tc.write(c.public_bytes(Encoding.PEM))
    cert_file = tc.name

with tempfile.NamedTemporaryFile(suffix=".pem", delete=False) as tk_:
    tk_.write(pk.private_bytes(Encoding.PEM, PrivateFormat.TraditionalOpenSSL, NoEncryption()))
    key_file = tk_.name

ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
ctx.minimum_version = ssl.TLSVersion.TLSv1_2
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
ctx.load_cert_chain(cert_file, key_file)

class MtlsAdapter(HTTPAdapter):
    def init_poolmanager(self, *a, **kw):
        kw["ssl_context"] = ctx
        super().init_poolmanager(*a, **kw)

session = requests.Session()
session.mount("https://", MtlsAdapter())
session.headers["Content-Type"] = "application/json"

payload = {payload_json}

{req_block}

print(resp.status_code, resp.json())
"""


def _code_csharp(url: str, method: str, ep_name: str, payload_json: str, cert_pfx: str) -> str:
    if method == "GET":
        req_block = f"""\
        var qs = string.Join("&", payload.Select(kv => $"{{kv.Key}}={{Uri.EscapeDataString(kv.Value.ToString())}}"));
        var resp = await http.GetAsync($"{url}?{{qs}}");"""
    else:
        req_block = f"""\
        var body = new StringContent(JsonSerializer.Serialize(payload), Encoding.UTF8, "application/json");
        var resp = await http.PostAsync("{url}", body);"""
    payload_cs = payload_json.replace('"', '\\"')
    return f"""\
using System;
using System.Net.Http;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

var cert = new X509Certificate2("{cert_pfx}", "SUA_SENHA");
var handler = new HttpClientHandler();
handler.ClientCertificates.Add(cert);
handler.ServerCertificateCustomValidationCallback = (_, _, _, _) => true; // homologação

using var http = new HttpClient(handler);
http.DefaultRequestHeaders.Add("Accept", "application/json");

var payloadJson = @"
{payload_json}
";

{req_block}

var json = await resp.Content.ReadAsStringAsync();
Console.WriteLine(resp.StatusCode);
Console.WriteLine(json);
"""


def _code_wlanguage(url: str, method: str, payload_json: str, cert_pfx: str) -> str:
    method_call = "HTTPGet" if method == "GET" else "HTTPPost"
    return f"""\
// WLanguage — Windev/Webdev/Windev Mobile
oRequest is httpRequest
oReq is string
oResp is httpResponse

// Carregar certificado mTLS
oRequest..Certificado = CertificadoCarrega("{cert_pfx}", "SUA_SENHA")
oRequest..URL = "{url}"
oRequest..Método = HTTP{"Get" if method == "GET" else "Post"}
oRequest..ContentType = "application/json"

// Payload
oReq = [
{payload_json}
]
oRequest..Conteúdo = oReq

// Executar
oResp = HTTPEnvia(oRequest)

IF oResp..StatusHTTP = 200 THEN
    Info(oResp..Conteúdo)
ELSE
    Erro("HTTP " + oResp..StatusHTTP + ": " + oResp..MensagemErro)
FIN
"""


def _code_harbour(url: str, method: str, payload_json: str, cert_pfx: str) -> str:
    payload_oneline = payload_json.replace("\n", " ").replace("'", '"')
    return f"""\
// Harbour — usando hbcurl (libcurl binding)
#include "hbcurl.ch"

LOCAL hCurl
LOCAL cPayload
LOCAL cResponse := ""

cPayload := '{payload_oneline}'

hCurl := curl_easy_init()

IF ! Empty( hCurl )
    curl_easy_setopt( hCurl, HB_CURLOPT_URL, "{url}" )
    curl_easy_setopt( hCurl, HB_CURLOPT_SSL_VERIFYPEER, 0 )
    curl_easy_setopt( hCurl, HB_CURLOPT_SSL_VERIFYHOST, 0 )
    curl_easy_setopt( hCurl, HB_CURLOPT_SSLCERT, "{cert_pfx}" )
    curl_easy_setopt( hCurl, HB_CURLOPT_SSLCERTPASSWD, "SUA_SENHA" )
    curl_easy_setopt( hCurl, HB_CURLOPT_SSLCERTTYPE, "P12" )
    curl_easy_setopt( hCurl, HB_CURLOPT_HTTPHEADER, {{ "Content-Type: application/json" }} )
    {("curl_easy_setopt( hCurl, HB_CURLOPT_POST, .T. )" if method == "POST" else "// GET — sem body")}
    {("curl_easy_setopt( hCurl, HB_CURLOPT_POSTFIELDS, cPayload )" if method == "POST" else "// --")}
    curl_easy_setopt( hCurl, HB_CURLOPT_DL_BUFF_SETUP, @cResponse )
    curl_easy_perform( hCurl )
    curl_easy_cleanup( hCurl )
ENDIF

? cResponse
"""


def _code_pascal(url: str, method: str, payload_json: str, cert_pfx: str) -> str:
    payload_pas = payload_json.replace("'", "''").replace("\n", " ")
    write_line = ("Http.Document.WriteBuffer(Pointer(Payload)^, Length(Payload));"
                  if method == "POST" else "// GET — sem body")
    http_call = (f"Http.HTTPMethod('POST', '{url}');"
                 if method == "POST" else f"Http.HTTPMethod('GET', '{url}');")
    return f"""\
// Free Pascal — usando Synapse (ssl_openssl) + fpjson
program CiotAntt;

{{$mode objfpc}}{{$H+}}

uses
  SysUtils, Classes, httpsend, ssl_openssl, fpjson, jsonparser;

var
  Http: THTTPSend;
  Payload, Response: string;
begin
  Payload := '{payload_pas}';

  Http := THTTPSend.Create;
  try
    Http.Sock.SSL.CertificateFile := '{cert_pfx}';
    Http.Sock.SSL.PrivateKeyFile  := '{cert_pfx}';
    Http.Sock.SSL.KeyPassword     := 'SUA_SENHA';
    Http.Headers.Add('Content-Type: application/json');
    Http.MimeType := 'application/json';

    {write_line}
    {http_call}

    SetLength(Response, Http.Document.Size);
    Http.Document.Read(Pointer(Response)^, Http.Document.Size);

    WriteLn('Status: ', Http.ResultCode);
    WriteLn(Response);
  finally
    Http.Free;
  end;
end.
"""


def _code_cobol(url: str, method: str, payload_json: str) -> str:
    safe_url = url[:60]
    safe_payload = payload_json[:200].replace('"', "'")
    return f"""\
      *> COBOL — GnuCOBOL + libcurl via C interop (conceitual)
       IDENTIFICATION DIVISION.
       PROGRAM-ID. CIOT-ANTT.

       ENVIRONMENT DIVISION.

       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-URL          PIC X(120) VALUE
           "{safe_url}".
       01  WS-PAYLOAD      PIC X(500) VALUE
           "{safe_payload}".
       01  WS-RESPONSE     PIC X(4096).
       01  WS-STATUS       PIC 9(3).

      *> Requer módulo de chamada C/libcurl ou COBOL HTTP library
      *> Exemplo conceitual com CALL para módulo externo:
       PROCEDURE DIVISION.
       MAIN-PARA.
           CALL "HTTP-POST-MTLS" USING
               WS-URL
               WS-PAYLOAD
               "SUA_SENHA_CERT"
               WS-RESPONSE
               WS-STATUS
           END-CALL

           DISPLAY "Status: " WS-STATUS
           DISPLAY WS-RESPONSE
           STOP RUN.
"""


if __name__ == "__main__":
    app = App()
    app.mainloop()
