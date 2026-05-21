# 🚛 API ANTT CIOT — Guia para Desenvolvedores

> **Vigência:** Portaria SUROC nº 06/2026 · Resolução ANTT nº 6.078/2026 · MP 1.343/2026  
> **Autuação automática:** R$ 10.500 por ocorrência sem intervenção humana

---

## 📋 Índice

- [🚛 API ANTT CIOT — Guia para Desenvolvedores](#-api-antt-ciot--guia-para-desenvolvedores)
  - [📋 Índice](#-índice)
  - [1. O que é o CIOT](#1-o-que-é-o-ciot)
    - [Base legal](#base-legal)
  - [2. Quem precisa emitir](#2-quem-precisa-emitir)
    - [✅ CIOT obrigatório quando contratar:](#-ciot-obrigatório-quando-contratar)
    - [❌ Exceções (sem CIOT):](#-exceções-sem-ciot)
  - [3. CT-e + MDF-e + CIOT — o triângulo obrigatório](#3-ct-e--mdf-e--ciot--o-triângulo-obrigatório)
    - [Como a ANTT cruza os três em tempo real:](#como-a-antt-cruza-os-três-em-tempo-real)
  - [4. Fluxo completo de uma operação](#4-fluxo-completo-de-uma-operação)
    - [Cenário prático: João Silva (TAC), SP → Curitiba, R$ 3.500](#cenário-prático-joão-silva-tac-sp--curitiba-r-3500)
      - [Passo 1 — Validar o transportador](#passo-1--validar-o-transportador)
      - [Passo 2 — Declarar a operação e receber o CIOT](#passo-2--declarar-a-operação-e-receber-o-ciot)
      - [Passo 3 — Encerrar o CIOT após a entrega](#passo-3--encerrar-o-ciot-após-a-entrega)
  - [5. Autenticação mTLS — o pré-requisito que trava todo mundo](#5-autenticação-mtls--o-pré-requisito-que-trava-todo-mundo)
    - [Passos para configurar](#passos-para-configurar)
  - [6. Os 8 endpoints da API](#6-os-8-endpoints-da-api)
    - [Tipos de operação (campo `TipoOperacao`)](#tipos-de-operação-campo-tipooperacao)
    - [Códigos de retorno](#códigos-de-retorno)
  - [7. Encerramento — o passo que mais gera multa](#7-encerramento--o-passo-que-mais-gera-multa)
    - [Prazos](#prazos)
    - [Como implementar o encerramento automático](#como-implementar-o-encerramento-automático)
  - [8. Multas e fiscalização eletrônica](#8-multas-e-fiscalização-eletrônica)
  - [9. Checklist do desenvolvedor](#9-checklist-do-desenvolvedor)
  - [10. Referências oficiais](#10-referências-oficiais)

---

## 1. O que é o CIOT

O **CIOT (Código Identificador da Operação de Transporte)** é o "RG digital" de cada viagem de carga. É um código numérico único gerado pela ANTT que registra:

- Quem **contratou** o serviço
- Quem vai **rodar** (transportador)
- Qual **veículo**
- Qual **carga** (NCM)
- **Origem e destino**
- **Valor do frete**

### Base legal

| Norma | O que regula |
|-------|-------------|
| Lei nº 11.442/2007 | Regula o transporte rodoviário de cargas |
| Resolução ANTT nº 5.862/2019 | Criou o "CIOT para todos" |
| MP nº 1.343/2026 | Ampliou penalidades e rastreabilidade |
| Resolução ANTT nº 6.078/2026 | Regras operacionais atuais |
| Portaria SUROC nº 06/2026 | Operacionaliza a API — **vigência 24/05/2026** |

---

## 2. Quem precisa emitir

### ✅ CIOT obrigatório quando contratar:

| Tipo | Descrição |
|------|-----------|
| **TAC** | Transportador Autônomo de Cargas — CPF ativo no RNTRC |
| **TAC Equiparado** | ETC com até 3 veículos ativos no RNTRC |
| **CTC** | Cooperativa de Transportadores de Carga |
| **ETC frota própria** | Novidade 2026 — ETC que opera com seus próprios veículos |

### ❌ Exceções (sem CIOT):

- Transporte de veículos novos não emplacados
- Cargas especiais com composição não homologada pela SENATRAN
- Transporte rodoviário internacional de cargas
- ETC com mais de 3 veículos que contrata outra ETC

> 💡 **Novidade 2026:** A Resolução 6.078/2026 passou a exigir CIOT também quando a ETC realiza o transporte com sua própria frota, sem subcontratar TAC.

---

## 3. CT-e + MDF-e + CIOT — o triângulo obrigatório

Se você já tem CT-e e MDF-e implementados, está **90% do caminho**. O CIOT é o terceiro vértice que a ANTT cruza em tempo real.

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│    CT-e     │    │    MDF-e    │    │    CIOT     │
│             │    │             │    │             │
│ Documenta   │    │ Manifesto   │    │ Código da   │
│ o serviço,  │    │ da viagem:  │    │ operação.   │
│ valor,      │    │ veículo,    │    │ Gerado na   │
│ remetente,  │    │ motorista,  │◄───│ API ANTT.   │
│ destinatário│    │ NCM, CIOT   │    │ Base da     │
└─────────────┘    └─────────────┘    │ fiscalização│
                                      └─────────────┘
```

### Como a ANTT cruza os três em tempo real:

```
CIOT declarado → MDF-e emitido (com nº do CIOT) → viagem → 
pagamento via IPEF → CIOT encerrado

A ANTT verifica:
  ✓ Valor do frete no CIOT == valor no MDF-e?
  ✓ Valor pago pela IPEF == valor no CIOT?
  ✓ NCM da carga justifica o piso mínimo cobrado?
  
Se qualquer coisa não bater → autuação automática
```

> ⚠️ **NT 2025.001 — mudança no schema do MDF-e:** O NCM da mercadoria principal agora é obrigatório no MDF-e. Verifique se o seu schema está atualizado antes de implementar o CIOT.

---

## 4. Fluxo completo de uma operação

```
[1] Validar       [2] Validar    [3] Declarar    [4] Buscar
    transportador     veículo        operação        CIOT
    (RNTRC)          (frota)        ← GERA O CIOT   gerado
         │                │               │              │
         ▼                ▼               ▼              ▼
[5] Emitir MDF-e  [6] Viagem      [7] Encerrar CIOT
    com nº CIOT       realizada       ≤ 5 dias ⚠️
```

### Cenário prático: João Silva (TAC), SP → Curitiba, R$ 3.500

#### Passo 1 — Validar o transportador

```json
// POST /ConsultarSituacaoTransportador
// Request
{
  "CpfCnpjInteressado": "12345678000190",  // seu CNPJ (contratante)
  "CpfCnpjTransportador": "98765432100",   // CPF do João
  "RNTRCTransportador": "000123456"        // sempre 9 dígitos
}

// Response esperado
{
  "RNTRCAtivo": true,
  "TipoTransportador": "TAC",
  "EquiparadoTAC": false,
  "Codigo": "000000"  // 000000 = sucesso
}
```

#### Passo 2 — Declarar a operação e receber o CIOT

> 🛑 **Erro comum:** emitir o MDF-e primeiro e tentar gerar o CIOT depois. O CIOT precisa existir **antes** da viagem e **antes** do MDF-e.

```json
// POST /DeclaracaoOperacaoTransporte
{
  "IdOperacaoTransporte": "202605241001",  // ID único (12 chars) gerado por você
  "TipoOperacao": 1,                       // 1=Lotação | 2=Fracionada | 3=TAC-Agregado
  "CpfCnpjContratado": "98765432100",
  "RNTRCContratado": "000123456",
  "CpfCnpjContratante": "12345678000190",
  "PlacaVeiculo": "ABC1234",
  "DataInicioViagem": "2026-05-24",
  "CidadeOrigem": "São Paulo",
  "UFOrigem": "SP",
  "CidadeDestino": "Curitiba",
  "UFDestino": "PR",
  "ValorFrete": 3500.00,                   // deve ser >= piso mínimo ANTT
  "NCMCargaPrincipal": "1001.10.10"        // obrigatório desde NT 2025.001
}

// Response — guarde o CodigoCIOT!
{
  "CodigoCIOT": "20260524100112",    // ← esse código vai no MDF-e
  "Protocolo": "2026052400000001",
  "Codigo": "000000"
}
```

#### Passo 3 — Encerrar o CIOT após a entrega

```json
// POST /EncerramentoOperacaoTransporte
{
  "IdOperacaoTransporte": "202605241001",
  "CpfCnpjInteressado": "12345678000190",
  "DataEncerramentoViagem": "2026-05-25",
  "ValorFreteEfetivo": 3500.00  // valor real pago — cruzado com pagamento IPEF
}

// ⚠️ Se ValorFreteEfetivo divergir do valor pago via IPEF → autuação automática
```

---

## 5. Autenticação mTLS — o pré-requisito que trava todo mundo

> 🔐 **Por que o endpoint retorna 404 mesmo com a URL certa?**  
> O servidor da ANTT valida o certificado do cliente **antes** de processar qualquer requisição. Sem o certificado ICP-Brasil na chamada HTTP, o servidor descarta a conexão. O 404 não é sobre a URL — é sobre o handshake de autenticação.

### Passos para configurar

**Passo 1 — Obter o certificado ICP-Brasil**

- Tipo A1 (arquivo `.pfx`/`.p12`) ou A3 (token/smartcard)
- Emitido por AC credenciada: Serpro, Certisign, Soluti, Valid etc.
- CNPJ da empresa no OID `2.16.76.1.3.3`
- Extended Key Usage: `Client Authentication`

**Passo 2 — Cadastrar o certificado na ANTT**

A ANTT registra o par CNPJ + CN (Common Name) do certificado. Sem esse cadastro, 100% das chamadas são rejeitadas.

📧 **Contato:** jose-aa.filho@antt.gov.br · ☎️ (61) 3410-1561

**Passo 3 — Solicitar o host e contexto dos endpoints**

O host exato é fornecido pela ANTT no credenciamento. O domínio de homologação é `appservices-hml.antt.gov.br`, mas o path precisa ser confirmado.

**Passo 4 — Configurar mTLS no cliente HTTP**

```python
# Python — pip install requests
import requests

# Converter .pfx para .pem:
# openssl pkcs12 -in cert.pfx -out cert.pem -nokeys -clcerts
# openssl pkcs12 -in cert.pfx -out key.pem -nocerts -nodes

CERT     = ("cert.pem", "key.pem")
CA_CHAIN = "cadeia-icp-brasil.pem"  # disponível no site ICP-Brasil
BASE_URL = "https://<HOST-ANTT>/pefServices"

def antt_post(endpoint, payload):
    resp = requests.post(
        f"{BASE_URL}/{endpoint}",
        json=payload,
        cert=CERT,       # ← autenticação mútua (mTLS)
        verify=CA_CHAIN  # ← valida certificado do servidor
    )
    resp.raise_for_status()
    return resp.json()
```

```javascript
// Node.js — npm install axios
const https = require('https');
const fs    = require('fs');
const axios = require('axios');

const agent = new https.Agent({
  cert: fs.readFileSync('cert.pem'),
  key:  fs.readFileSync('key.pem'),
  ca:   fs.readFileSync('cadeia-icp.pem')
});

const antt = axios.create({
  baseURL: 'https://<HOST-ANTT>/pefServices',
  httpsAgent: agent
});

const { data } = await antt.post('DeclaracaoOperacaoTransporte', {
  IdOperacaoTransporte: '202605241001',
  TipoOperacao: 1,
  // ... demais campos
});

console.log('CIOT gerado:', data.CodigoCIOT);
```

---

## 6. Os 8 endpoints da API

Todos sob `https://<HOST-ANTT>/pefServices/`

| # | Método | Endpoint | O que faz |
|---|--------|----------|-----------|
| 1 | POST | `ConsultarSituacaoTransportador` | Valida transportador no RNTRC |
| 2 | POST | `ConsultarFrotaTransportador` | Verifica se placas pertencem ao transportador |
| 3 | POST | `DeclaracaoOperacaoTransporte` | **Gera o CIOT** |
| 4 | POST | `CancelamentoOperacaoTransporte` | Cancela operação (até 24h antes) |
| 5 | POST | `RetificacaoOperacaoTransporte` | Corrige dados após declaração |
| 6 | POST | `EncerramentoOperacaoTransporte` | Encerra a operação (obrigatório) |
| 7 | GET  | `ConsultarCIOTGerado` | Retorna código CIOT com dígito verificador |
| 8 | GET  | `ConsultarExcecao` | Verifica exceções à Resolução 5.862 |

### Tipos de operação (campo `TipoOperacao`)

| Código | Tipo | Quando usar | Prazo encerramento |
|--------|------|-------------|-------------------|
| `1` | Carga Lotação | Um único contratante, caminhão dedicado | 5 dias corridos |
| `2` | Carga Fracionada | Múltiplos contratantes / vários pontos | 5 dias corridos |
| `3` | TAC-Agregado | TAC em exclusividade (10 a 30 dias) | Manual |

### Códigos de retorno

| Código | Significado | Ação |
|--------|-------------|------|
| `000000` | ✅ Sucesso | Processar normalmente |
| `B1` | Campo obrigatório não informado | Verificar payload |
| `B3` | RNTRC inválido | RNTRC deve ter 8 ou 9 dígitos |
| `B14` | Transportador sem RNTRC ativo | Consultar situação no portal ANTT |
| `B17` | IdOperacao já existente | Gerar novo ID único de 12 chars |
| `B112` | CPF/CNPJ inválido | Validar dígitos verificadores |
| `HTTP 404` | ❌ Endpoint não encontrado | Verificar URL + certificado cadastrado |
| `TLS Error` | ❌ Handshake falhou | Certificado não cadastrado ou tipo incorreto |

> ⚠️ **Regra RNTRC:** sempre 9 dígitos. Se o número tiver 8, preencher com zero à esquerda. Com 7 dígitos é inválido.

---

## 7. Encerramento — o passo que mais gera multa

**R$ 10.500** por CIOT não encerrado, por ocorrência, por viagem.

### Prazos

- **Lotação / Fracionada:** até **5 dias corridos** após o término da viagem
- **TAC-Agregado:** encerramento manual ao final do período contratado

### Como implementar o encerramento automático

```
Evento: confirmação de entrega no sistema (TMS, app do motorista, CT-e de retorno)
    │
    ▼
Job chama EncerramentoOperacaoTransporte
    │
    ▼
Guarda o Protocolo de retorno (para auditoria)
    │
    ▼
ANTT cruza ValorFreteEfetivo com pagamento IPEF
    │
    ├─ Valores batem → operação encerrada ✅
    └─ Valores divergem → autuação automática ❌
```

> 🔁 **Implemente também um job de varredura diária** que verifica CIOTs em aberto há mais de 4 dias e dispara o encerramento automaticamente. Não dependa de ação manual.

---

## 8. Multas e fiscalização eletrônica

Em 2026 a ANTT não precisa mais parar o caminhão na estrada. Tudo é cruzado automaticamente.

| Infração | Multa | Responsável |
|----------|-------|-------------|
| Não registrar a operação / não gerar o CIOT | **R$ 10.500** | Contratante / ETC |
| Gerar CIOT com dados diferentes da contratação real | **R$ 10.500** | Contratante / ETC |
| Emitir MDF-e sem o número correto do CIOT | **R$ 10.500** | Transportadora |
| Não encerrar o CIOT no prazo | **R$ 10.500** | Quem gerou o CIOT |
| Frete efetivo abaixo do piso mínimo (Res. 6.076/2026) | **R$ 10.500** | Contratante / ETC |

---

## 9. Checklist do desenvolvedor

- [ ] Certificado ICP-Brasil A1/A3 com CNPJ obtido de AC credenciada
- [ ] OID `2.16.76.1.3.3` + Extended Key Usage "Client Authentication"
- [ ] Certificado cadastrado na ANTT — contato: jose-aa.filho@antt.gov.br
- [ ] URL de homologação confirmada com a ANTT (fornecida no credenciamento)
- [ ] TLS 1.2 + mTLS configurado: `cert=(client.pem, key.pem)` + `verify=cadeia-icp.pem`
- [ ] Fluxo correto: validar RNTRC → validar placa → declarar → MDF-e → encerrar
- [ ] CIOT gerado **antes** do início da viagem e **antes** de emitir o MDF-e
- [ ] RNTRC sempre com 9 dígitos (preencher zero à esquerda quando necessário)
- [ ] NCM da carga principal incluído no payload e no MDF-e (NT 2025.001)
- [ ] Valor do frete ≥ piso mínimo (Resolução ANTT 6.076/2026)
- [ ] Número do CIOT sendo incluído no MDF-e antes da emissão
- [ ] Encerramento automático implementado (≤ 5 dias após entrega)
- [ ] Job de varredura de CIOTs em aberto (alerta antes de 4 dias)
- [ ] Log e armazenamento do protocolo de retorno de cada operação

---

## 10. Referências oficiais

| Recurso | Link |
|---------|------|
| Portal ANTT — CIOT para Todos | https://www.gov.br/antt/pt-br/assuntos/cargas/codigo-identificador-da-operacao-de-transporte-ciot |
| DCS Técnico (PDF oficial, 66 páginas) | https://www.gov.br/antt/pt-br/assuntos/cargas/pagamento-eletronico-de-fretes-pef-ciot/documento-de-contrato-de-servico.pdf |
| Piso mínimo de frete | https://www.gov.br/antt/pt-br/assuntos/cargas/ciot-para-todos-1/piso-minimo-ciot |
| Contato técnico ANTT | jose-aa.filho@antt.gov.br · (61) 3410-1561 · SUTEC/ANTT |

---

*Material compilado a partir do DCS oficial da SUTEC/ANTT (v1.0 · 2026), Portaria SUROC nº 06/2026 e Resolução ANTT nº 6.078/2026.*  
*Este documento tem fins educativos. Sempre valide com a documentação oficial antes de ir para produção.*

---

💬 **Grupo Wts Programação com IA by Cleiton nosso Amigo!**

Feito com 🤝 pela galera: **Amarildo ShowMan** · **EasyCodar** · **Cleiton** · **Claude (Anthropic)**