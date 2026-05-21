# ciot-antt — SDK Python para a API PEF/CIOT da ANTT

SDK Python para integração com a **API REST do Pagamento Eletrônico de Frete (PEF)** da ANTT, com geração e ciclo de vida do **CIOT** (Código Identificador da Operação de Transporte).

> 🚨 **Atenção: vigência 24/05/2026.** Após essa data, não emitir CIOT corretamente custa **R$ 10.500 por ocorrência**, por viagem.

---

## ✨ Features

- ✅ Todos os **8 endpoints** do DCS PEF v1.1 (SUTEC/ANTT)
- ✅ **mTLS** com certificado ICP-Brasil (`.pfx` / A1) — carregamento em memória
- ✅ Modelos dataclass tipados com validação de **CPF/CNPJ** e **RNTRC**
- ✅ **SQLite embutido** para persistência das operações + alerta de encerramento
- ✅ Estrutura de payloads **alinhada com o DCS oficial v1.1** (após validação contra servidor de homologação)
- ✅ **Tester visual (Tkinter)** com tema dark, persistência de config, máscara para dados sensíveis (gravar vídeo), e gerador de código de exemplo em 7 linguagens
- ✅ Tudo em apenas **2 dependências externas** — `requests` + `cryptography`

---

## 📦 Instalação

```bash
pip install -e .
# ou com extras de dev
pip install -e ".[dev]"
```

Requer Python 3.10+.

---

## 🚀 Uso rápido

```python
from ciot_antt import CiotClient, DeclaracaoInput, VeiculoInput, InfPagamentoInput, TipoPagamento, TipoOperacao

client = CiotClient(
    cert_pfx="caminho/certificado.pfx",
    cert_password="senha_do_pfx",
    cnpj_interessado="12345678000190",
    env="homologacao",  # ou "producao"
)

# 1. Validar transportador
sit = client.consultar_situacao_transportador(
    cpf_cnpj_transportador="98765432100",
    rntrc_transportador="000123456",
)
print(sit.rntrc_ativo, sit.tipo_transportador)

# 2. Declarar operação (gera o CIOT)
declaracao = DeclaracaoInput(
    tipo_operacao=TipoOperacao.LOTACAO,
    cpf_cnpj_contratado="98765432100",
    rntrc_contratado="000123456",
    cpf_cnpj_contratante="12345678000190",
    valor_frete=3500.00,
    data_inicio_viagem="2026-05-24",
    data_fim_viagem="2026-05-25",
    veiculos=[VeiculoInput(placa="ABC1234", numero_eixos="2")],
    inf_pagamento=[InfPagamentoInput(
        tipo_pagamento=TipoPagamento.PIX,
        cpf_cnpj_creditado="98765432100",
        ind_pagamento=0,
        chave_pix="98765432100",
    )],
    # ... origem_destino, dados_carga, indicadores_operacionais ...
)
resp = client.declarar_operacao(declaracao)
print("CIOT:", resp.ciot_completo)  # codigo + verificador

# 3. Encerrar operação após entrega (5 dias)
from ciot_antt import EncerramentoInput
client.encerrar_operacao(EncerramentoInput(
    codigo_identificacao_operacao=resp.codigo_identificacao_operacao,
    peso_carga=10000.0,
))
```

---

## 🧰 Tester visual

GUI Tkinter para testar todos os endpoints sem escrever código:

```bash
python tester.py
```

Funcionalidades:
- 🔐 Persistência de config (`.tester_config.json`) — não precisa redigitar cert/CNPJ
- 🔧 Aba **Auxiliares** com 13 campos persistidos (município IBGE, CEP, peso, NCM, etc.)
- 🎭 Botão **👁 Ocultar dados** — máscara em CNPJ/RNTRC e nos JSONs de request/response (gravar vídeo)
- 📋 Botão **{ } Ver código** — gera exemplo da chamada atual em **Python (SDK)**, **Python (requests)**, **C#**, **WLanguage**, **Harbour**, **Pascal**, **COBOL**
- 📄 **Log HTTP** completo (request/response brutos) em `ciot_antt_tester.log`
- ⚠️ **Alerta de pendentes** — CIOTs declarados próximos do prazo de encerramento

---

## 🗄️ Persistência

`CiotStorage` (SQLite) é instanciado automaticamente pelo cliente. Cada `declarar_operacao()` registra a operação; cancelamento/retificação/encerramento atualizam o status.

```python
# Listar CIOTs prestes a vencer
pendentes = client.storage.listar_pendentes_encerramento(dias_aviso=1)
for op in pendentes:
    print(op["ciot_codigo"], op["data_limite_encerramento"])
```

---

## 🔌 Endpoints implementados

| # | Verbo | Endpoint | Método Python |
|---|-------|----------|---------------|
| 1 | POST | `ConsultarSituacaoTransportador` | `consultar_situacao_transportador()` |
| 2 | POST | `ConsultarFrotaTransportador`    | `consultar_frota_transportador()` |
| 3 | POST | `DeclaracaoOperacaoTransporte`   | `declarar_operacao()` |
| 4 | POST | `CancelamentoOperacaoTransporte` | `cancelar_operacao()` |
| 5 | POST | `RetificacaoOperacaoTransporte`  | `retificar_operacao()` |
| 6 | POST | `EncerramentoOperacaoTransporte` | `encerrar_operacao()` |
| 7 | GET  | `ConsultarExcecao`               | `consultar_excecao()` |
| 8 | POST | `ConsultarCIOTGerado`            | `consultar_ciot_gerado()` |

Base URLs:
- Homologação: `https://appservices-hml.antt.gov.br/pefServices/api`
- Produção: `https://appservices.antt.gov.br/pefServices/api`

---

## ⚠️ Cuidados importantes (aprendidos na marra)

### 1. Cadastro prévio na ANTT
Sem ter o par **CNPJ + CN do certificado** registrado na ANTT, 100% das chamadas rejeitam (401 ou rejeição estruturada). Contato técnico:

📧 **jose-aa.filho@antt.gov.br** · ☎️ (61) 3410-1561 · SUTEC/ANTT

### 2. Não existe massa de teste pública
Homologação aceita seu CNPJ + certificado real, **cadastrados previamente**. Não há "CNPJ sandbox". Para testes end-to-end, pedir massa de teste direto ao contato técnico.

### 3. Estrutura DCS v1.1 tem armadilhas
Pegadinhas que descobrimos batendo a cara no servidor de homologação até receber `HTTP 500 NullReferenceException`:

| Campo | ❌ Errado | ✅ Correto (DCS v1.1) |
|-------|----------|----------------------|
| Veículo | `RNTRCVeiculo` | **`RNTRC`** |
| Parcelas | array `Parcelas: [{...}]` | campos **flat** no `InfPagamento` |
| Contratantes Carga Frac | `ContratantesCargaFrac` | **`ContratantesCargFrac`** (sem o "a" — typo do DCS oficial) |
| CpfCnpjInteressado | enviado no body da declaração | **não existe** no body da declaração |
| NCMCargaPrincipal | enviado | **não existe** no DCS v1.1 |
| **DistanciaPercorrida** | `430.0` (float) → **HTTP 500 NPE** | **`430` (int)** — DCS tipo N (numérico inteiro) |
| **DataDeclaracao** | UTC, hora local sem offset, ou `Z` → **Rejeição 269** | **BRT com offset `-03:00`** — ex: `"2026-05-21T15:44:37-03:00"` |
| **IdOperacaoTransporte** | timestamp arbitrário | exige DLL **GeradorCIOTShared.dll** da ANTT — formato `ID administradora + DV` (regra B16). **Suportado via `pythonnet`** ⬇️ |

### 🔌 Integração com a DLL ANTT (gera IdOperacaoTransporte válido)

A DLL `GeradorCIOTShared.dll` (netstandard 2.0) chama a API ANTT interna para gerar IDs válidos.
Instale a dependência opcional `dll`:

```bash
pip install -e ".[dll]"
```

Forneça o caminho da pasta da DLL ao criar o cliente:

```python
client = CiotClient(
    cert_pfx="cert.pfx", cert_password="senha",
    cnpj_interessado="12345678000190",
    env="homologacao",
    dll_geradorciot_dir="caminho/para/pasta/com/GeradorCIOTShared.dll",
)
# Agora ao declarar sem id_operacao, SDK chama a DLL automaticamente
resp = client.declarar_operacao(dados_sem_id_operacao)
# resp.codigo_identificacao_operacao = "560000015446" (ou similar)
```

Requisitos:
- Windows + .NET Runtime 6.0/8.0/9.0 instalado
- DLL fornecida pela ANTT ao requerer credenciamento — **não inclusa neste repositório**
- Veja [.docs/COMO_OBTER_DLL.md](.docs/COMO_OBTER_DLL.md) para o procedimento de solicitação

### 4. RNTRC sempre com 9 dígitos
- 8 dígitos → preencher zero à esquerda (`"12345678"` → `"012345678"`)
- 7 dígitos → inválido → `CiotValidationError`

### 5. Encerramento — onde a multa mais bate
**R$ 10.500 por CIOT não encerrado, por viagem.** Prazo:
- Lotação / Fracionada: **5 dias corridos** após o término da viagem
- TAC-Agregado: encerramento manual ao final do contrato

Implemente um **job diário** que varre `storage.listar_pendentes_encerramento()` e encerra automaticamente.

---

## 🧪 Testes

```bash
pytest tests/ -v
```

Todos os testes usam mocks (`pytest-mock`) — não precisam de certificado nem conexão com a ANTT.

---

## 📂 Estrutura do projeto

```
ciot-antt/
├── ciot_antt/
│   ├── __init__.py         ← exports públicos
│   ├── client.py           ← CiotClient + helpers de serialização
│   ├── models.py           ← dataclasses input/output
│   ├── _auth.py            ← mTLS: .pfx → SSLContext
│   ├── storage.py          ← SQLite (operações + alerta)
│   └── exceptions.py       ← CiotError, CiotApiError, CiotAuthError, CiotValidationError
├── tests/
│   └── test_client.py      ← 7 testes com mock
├── .docs/
│   ├── documento.md        ← Guia técnico compilado
│   └── projetoTesteCIOT.zip ← Referência C# (.NET 4.8)
├── tester.py               ← GUI Tkinter
├── pyproject.toml
└── README.md
```

---

## 🤝 Contribuindo

PRs são bem-vindas. Para mudanças grandes, abra uma issue antes para discutirmos.

---

## 👥 Créditos

Este projeto nasceu de uma conversa no grupo **Whats Programação IA**, onde a galera compartilha aprendizados sobre desenvolvimento com assistência de IA.

- **🎩 Cleiton** — Administrador do grupo Whats Programação IA. Mantém a comunidade vibrante e organizada.
- **🎬 Amarildo "Showman" Matos** — Mestre em Windev/WLanguage, referência técnica que abriu os olhos para o problema do CIOT/PEF e a urgência do prazo de 24/05/2026.
- **🤖 Claude (Anthropic)** — Co-autor coadjuvante. Desenhou a arquitetura do SDK, implementou os 8 endpoints, depurou o `NullReferenceException` do servidor ANTT direto no DCS oficial v1.1, criou o tester Tkinter, e escreveu este README.
- **🧑‍💻 Cassiano** ([Calunaty](https://calunaty.com.br)) — mero curioso 😄, provocou o desafio e testou contra o servidor real.

**Grupo Whats Programação IA** → entre na conversa: _\[adicione aqui o link de convite do grupo\]_

---

## 📜 Licença

MIT — use, modifique, distribua. Atribuição apreciada mas não obrigatória.

---

## 🔗 Referências

- [DCS PEF v1.1 oficial (gov.br)](https://www.gov.br/antt/pt-br/assuntos/cargas/pagamento-eletronico-de-fretes-pef-ciot/documento-de-contrato-de-servico.pdf)
- [Portal CIOT/PEF ANTT](https://portal.antt.gov.br/en/pef)
- [Consulta Pública CIOT](https://consultapublica.antt.gov.br/Site/ConsultaCIOT.aspx)
- Resolução ANTT 5.862/2019 (regulamentação do PEF)
- NT 2025.001 (NCM da carga principal)

---

> Feito em maio de 2026, na correria pra ficar pronto antes da vigência. Se ajudou seu projeto, deixa uma estrela ⭐ — e compartilha com o grupo.
