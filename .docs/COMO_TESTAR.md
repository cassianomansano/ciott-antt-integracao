# Como testar o SDK ciot-antt — guia prático

Passo a passo do que funciona, o que não funciona, e como debugar contra o ambiente de homologação da ANTT.

---

## 1. Pré-requisitos

- **Python 3.10+** instalado
- **.NET Runtime 6.0, 8.0 ou 9.0** (Windows) — necessário para a DLL `GeradorCIOTShared.dll`
- **Certificado ICP-Brasil A1** (`.pfx`/`.p12`) emitido para um CNPJ **previamente cadastrado** na ANTT
- **Conexão com a internet**
- **DLL `GeradorCIOTShared.dll`** + `.pdb` na pasta `.docs/geradorciotdll/`

```bash
pip install -e ".[dev,dll]"
```

`dev` traz pytest. `dll` traz `pythonnet` (chamada à DLL .NET).

---

## 2. Configurar o tester visual

```bash
python tester.py
```

### Aba 🔌 API → seção Conexão

| Campo               | O que preencher |
|---------------------|-----------------|
| Certificado .pfx    | Caminho do seu `.pfx` |
| Senha               | Senha do `.pfx` |
| Ambiente            | `Homologação` (escolha sempre primeiro pra testar) |
| CNPJ Interessado    | CNPJ do certificado (com ou sem pontuação) |

Clica **⚡ Conectar**. Status fica verde "Conectado".

### Aba 📊 Operações (CIOTs)

Grid das declarações já feitas (banco SQLite local `ciot_operacoes.db`). Mostra status, CIOT, data, protocolo etc. Duplo clique numa linha → menu de ações (cancelar, encerrar, retificar).

### Aba 🔌 API → Auxiliares

13+ campos persistidos em `.tester_config.json`. Os mais importantes:

| Campo                              | Valor que funciona em homolog |
|------------------------------------|-------------------------------|
| **Pasta DLL GeradorCIOT**          | `d:/projetos/GitHub/ciot-antt/.docs/geradorciotdll` |
| Placa veículo (cavalo)             | Placa REAL do seu CNPJ — tipo automotor |
| Placa reboque (implemento)         | Placa REAL do seu CNPJ — tipo implemento |
| **Código natureza carga**          | 4 primeiros díg do NCM (ex: `1201`). `5705`/`1001` ✅ testados |
| Código tipo carga (1-12)           | `5` (Carga Geral) |
| Peso carga (kg)                    | `10000` |
| Cód. município origem IBGE 7d      | `3550308` (São Paulo) |
| Cód. município destino IBGE 7d     | `3304557` (Rio de Janeiro) |
| CEP origem / destino               | `01310100` / `20040020` |
| Distância percorrida (km)          | `430` (vai como INT, NUNCA float — quebra o servidor) |
| Número eixos do cavalo             | `3` |
| Valor frete                        | `3500.00` |
| Tipo operação (1/2/3)              | `1` (Lotação) |
| Data início / fim viagem           | datas dentro de 30 dias |

⚠️ **`aux_id_operacao_manual`** — deixa **VAZIO**. SDK chama a DLL automaticamente.

---

## 3. Fluxo de teste por endpoint

### 01 — ConsultarSituacaoTransportador
- Combo: escolhe `01 — ConsultarSituacaoTransportador`
- Preenche `CPF/CNPJ Transportador` + `RNTRC`
- **▶ Enviar** → response com `RNTRCAtivo`, `TipoTransportador` (TAC/ETC/CTC)

### 02 — ConsultarFrotaTransportador
- Preenche placas separadas por vírgula: `ABC1D23,ABC4567`
- Response lista cada placa com situação

### 03 — DeclaracaoOperacaoTransporte (gera CIOT)
- Vai pra aba **Auxiliares**, confere os valores
- Volta pra aba **Parâmetros**
- Clica **🔄 Regenerar do Auxiliares** (monta JSON com base nos campos)
- **▶ Enviar**
- **SDK chama a DLL automaticamente** pra gerar o `IdOperacaoTransporte` válido
- Se passar: CIOT completo retornado (12+4 chars). Aba **📊 Operações** mostra a linha amarela "declarada"

### 04 — CancelamentoOperacaoTransporte
- Na aba 📊 Operações, **duplo clique** numa linha "declarada"
- Menu → **🛑 Cancelar (04)**
- Volta pra aba API com CIOT já preenchido
- Edita motivo → **▶ Enviar**

### 05 / 06 — Retificar / Encerrar
- Mesmo padrão do cancelamento (menu na linha)

### 07 / 08 — Consultar CIOT / Exceção
- 07 precisa do `IdOperacaoTransporte` (12 chars)
- 08 precisa só do CPF/CNPJ do transportador

---

## 4. Mapa de erros conhecidos e soluções

### Erros estruturais (já resolvidos no SDK)

| Mensagem servidor                            | Causa                                        | Resolução |
|----------------------------------------------|----------------------------------------------|-----------|
| `HTTP 500 NullReferenceException line 23`    | `DistanciaPercorrida` enviado como float     | ✅ SDK força int |
| `Rejeição: A data e hora da declaração está fora do intervalo de tolerância` | `DataDeclaracao` em UTC, sem offset, ou com `Z` | ✅ SDK usa BRT `-03:00` |
| `Rejeição: O campo IdOperacaoTransporte é inválido` | ID arbitrário (regra B16: ID administradora + DV) | ✅ SDK chama a DLL ANTT |

### Erros de dados (você precisa ajustar)

| Mensagem                                     | O que fazer |
|----------------------------------------------|-------------|
| `Não foi encontrado transportador contratado com CPF/CNPJ X e RNTRC Y` | CNPJ/RNTRC não cadastrado nesse ambiente. Pedir massa de teste ou trocar ambiente |
| `O veículo do tipo automotor informado não possui vínculo com o transportador contratado` | Placa não está na frota do CNPJ no RNTRC. Cadastrar via portal ANTT |
| `É obrigatório informar ao menos um implemento quando o veículo automotor for do tipo cavalo-trator` | Adicionar placa de reboque na aba Auxiliares |
| `Somente um veículo deve ser do tipo automotor` | Você passou 2 cavalos. Apenas 1 cavalo + 1+ implementos |
| `É necessário informar ao menos um veículo do tipo automotor` | Só passou implemento. Precisa de pelo menos 1 cavalo |
| `O código da natureza da carga informado não existe` | É o **NCM**: use os **4 primeiros dígitos do NCM** do produto principal da NF-e (ex: `1201` soja, `2710` combustível). Regra B9 do DCS. `5705`/`1001` funcionam por serem headings NCM válidos |
| `A empresa transportadora só pode emitir CIOT diretamente em nome próprio quando for o transportador contratado` (rej. 314) | Webservice direto = emissão **em nome próprio** (regra B115). Titular do certificado TEM que ser o `CpfCnpjContratado`. **Contratou TAC → só via IPEF**, esse webservice não resolve. Veja tabela "QUEM EMITE e COMO" no README |
| `Acesso Negado` (401) em `/token` | Endpoint interno da DLL — chave embutida pode estar rotacionada |

---

## 5. Identificando tipo de placa (cavalo vs implemento)

Não há API pública pra consultar o tipo de uma placa. Descobrimos testando:

- Se rejeição = `"O veículo do tipo automotor informado não possui vínculo com o transportador contratado"` → a placa é **automotor (cavalo)** e o tipo passou na validação
- Se rejeição = `"É necessário informar ao menos um veículo do tipo automotor"` → a placa é **implemento (reboque)**
- Se rejeição = `"Somente um veículo deve ser do tipo automotor"` → você passou 2 cavalos

Lembrando: o array `Veiculos` exige sempre **1 cavalo + 1+ implementos**.

⚠️ **Em homologação as placas reais (de produção) NÃO ESTÃO vinculadas** ao CNPJ no RNTRC. A vinculação existe só em produção. Para testar declaração end-to-end:

1. Solicitar ao contato ANTT (`pef@antt.gov.br` ou `jose-aa.filho@antt.gov.br`) o cadastro de placas no ambiente de homologação para o seu CNPJ
2. **OU** rodar em produção com cuidado (gera CIOT real, sujeito a multas se incorreto)

---

## 6. Análise da DLL (referência técnica)

A DLL `GeradorCIOTShared.dll` (netstandard 2.0, ~10KB) faz:

```
POST https://appservices-hml.antt.gov.br/pefServices/token
Body: {"chave": "<CHAVE-DA-ADMINISTRADORA>"}
→ Response: {"token": "<JWT>"}

POST https://appservices-hml.antt.gov.br/pefServices/gerar
Header: Authorization: Bearer <JWT>
Body: {"cnpj": "<CNPJ-CONTRATANTE>"}
→ Response (caminho aninhado): dados.ciot.Dados.CIOT = "<12 chars>"
```

A chave é embutida na DLL — não precisamos extrair manualmente (pythonnet chama o método `GerarCIOT(cpfCnpj)` direto).

CIOTs gerados em sequência:
```
560000015404, 560000015405, 560000015406, ...
```

Padrão `56 00000 XXXXX` = `5600000` (administradora) + 5 dígitos sequenciais (DV é calculado por trás).

---

## 7. Rodando os testes mock (sem chamada real)

```bash
pytest tests/ -v
```

7 testes usam `pytest-mock` — não precisam de certificado nem conexão. Cobrem:

- Endpoint 01 (situação)
- Endpoint 03 (declaração sucesso + rejeição)
- Normalização de RNTRC (8 dígitos → 9; 7 → erro)
- Endpoint 04 (cancelamento atualizando SQLite)
- Listagem de pendentes de encerramento

---

## 8. Debug

### Habilitar log HTTP completo
- Botão **📄 Ver Log** no tester abre `ciot_antt_tester.log` com:
  - Request method, URL, headers, body (UTF-8)
  - Response status, headers, body

### Banco SQLite
```bash
sqlite3 ciot_operacoes.db "SELECT id_operacao, status, ciot_codigo, mensagem FROM operacoes ORDER BY created_at DESC LIMIT 10"
```

### Visualizar JSON de uma operação
- Aba 📊 Operações → seleciona linha → botão **📄 Ver Req/Resp** mostra request e response originais (do storage)

### Modo privacidade (gravar vídeo)
- Botão **👁 Ocultar dados** mascara CNPJs, RNTRCs, chaves PIX e demais sensíveis no UI e nos JSONs

---

## 9. Cheat sheet de contatos

| Necessidade                                | Para quem mandar email |
|--------------------------------------------|------------------------|
| Cadastrar certificado/CNPJ na ANTT         | `pef@antt.gov.br` ou `jose-aa.filho@antt.gov.br` |
| Pedir DLL `GeradorCIOTShared.dll`          | Idem |
| Pedir massa de teste em homologação        | Idem |
| Dúvidas técnicas                           | (61) 3410-1561 (SUTEC/ANTT) |

---

## 10. Quick test (1 comando)

```bash
python tester.py
# 1. Conectar
# 2. Vai pro endpoint 03 (Declaração)
# 3. Clica "🔄 Regenerar do Auxiliares"
# 4. Clica "▶ Enviar"
# 5. Se der "veículo sem vínculo" → tudo OK no SDK, falta cadastrar placa na ANTT
# 6. Se der "código natureza carga inválido" → muda pra 5705 ou 1001
# 7. Se der HTTP 500 NPE → bug no payload (abre issue)
```
