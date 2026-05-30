# Regras de validação do DCS PEF v1.1 (referência rápida)

> Resumo curado das regras de negócio (`B*`), domínios de campo e mensagens de
> rejeição do **DCS PEF v1.1** oficial da ANTT. Objetivo: entender **por que** o
> servidor rejeita um payload sem precisar abrir/parsear o PDF de 66 páginas.
>
> **Fonte:** [DCS PEF v1.1 (PDF oficial)](https://www.gov.br/antt/pt-br/assuntos/cargas/ciot-para-todos-1/dcs_pef_v1-1.pdf).
> As regras marcadas ✅ foram conferidas diretamente no texto do DCS.

---

## 🚦 Quem emite e por qual canal (regra B115)

A regra que mais confunde. A ANTT separa o acesso por **tipo de certificado**:

- **Certificado de IP** (Instituição de Pagamento = IPEF) → emite CIOT **por terceiros**.
- **Certificado que NÃO é de IP** (empresa comum) → emite **"em nome próprio"**.

**Regra B115 (rejeição 314)** ✅ — texto do DCS:
> "quando a empresa estiver emitindo em nome próprio, o `CpfCnpjContratado` é
> igual ao CNPJ da empresa emissora identificado no acesso à API, rejeitando a
> requisição caso sejam diferentes."

**Regra de ouro:** Webservice direto ⇔ **titular do certificado == `CpfCnpjContratado`** (quem assina é quem executa o frete).

| Situação | Quem emite | Canal |
|---|---|---|
| ETC com frota própria (sem TAC) | a própria ETC | **Webservice direto** ✅ |
| ETC subcontratada por outra ETC | a ETC que **executa** | **Webservice direto** ✅ |
| Qualquer um contratando TAC | quem contratou | **Somente via IPEF** ⚠️ |
| Indústria/comércio contratando TAC | a indústria/comércio | **Somente via IPEF** ⚠️ |
| ETC contratando TAC | a ETC contratante | **Somente via IPEF** ⚠️ |

→ **Contratou TAC = só via IPEF** (eFrete, Roadcard, Target Bank). O SDK (Webservice
direto) barra esse caso com `CiotValidationError` antes de chamar o servidor;
para certificado de IPEF use `CiotClient(..., emissor_e_ipef=True)`.

Regras relacionadas ao certificado:
- **B112 (rej. 311)** ✅ — cert não-IP → `CpfCnpjTransportador` deve ser igual ao CNPJ do certificado.
- **B113 (rej. 312)** ✅ — cert não-IP → o `IdOperacaoTransporte` deve pertencer ao CNPJ do certificado.

---

## 📋 Domínios de campo

### `CodigoNaturezaCarga` — regra B9 ✅
**= os 4 primeiros dígitos do NCM** do produto principal (maior valor/quantidade)
da NF-e. Numérico, máx. 4 dígitos. **Não** é uma tabela própria da ANTT — é o
próprio NCM/SH; a ANTT valida contra a base interna ("existe na base de dados").

- Ex.: soja `1201.90.00` → `1201` · combustível `2710.19.21` → `2710` · embutidos `1601` → `1601`
- `5705` e `1001` foram testados como válidos (são headings NCM válidos).
- Enviar como **int**. Valor como `4` (1 dígito) → rejeição "não existe".

### `CodigoTipoCarga` — domínio fixo 1-12 ✅ (DCS seção 15.3)
```
1  Granel sólido            7  Perigosa (granel sólido)
2  Granel líquido           8  Perigosa (granel líquido)
3  Frigorificada/Aquecida   9  Perigosa frigorificada
4  Conteinerizada          10  Perigosa conteinerizada
5  Carga Geral             11  Perigosa carga geral
6  Neogranel               12  Granel pressurizada
```
> ⚠️ Não confundir com `CodigoNaturezaCarga`. São campos diferentes: Tipo = enum 1-12; Natureza = NCM 4 díg.

### `TipoOperacao`
`1` = Lotação · `2` = Fracionada · `3` = TAC-Agregado

### `TipoPagamento`
`1` IP · `2` Conta corrente · `3` Conta poupança · `4` Conta pagamento · `5` Outros · `6` PIX

### `RNTRC` — 9 dígitos
8 díg → completar com zero à esquerda · 7 díg → inválido.

---

## 🔑 Regras de validação verificadas (`B*`)

| Regra | Rej. | O que verifica | Mensagem |
|-------|------|----------------|----------|
| **B4** ✅ | — | transportador contratado existe (CPF/CNPJ + RNTRC) | "Não foi encontrado transportador contratado com CPF/CNPJ {0} e RNTRC {1}" |
| **B9** ✅ | 211 | `CodigoNaturezaCarga` existe na base (NCM) | "O código da natureza da carga informado não existe" |
| **B15** ✅ | 205 | `IdOperacaoTransporte` no formato válido (**ID da administradora + DV**) | "O campo IdOperacaoTransporte é inválido" |
| **B16** ✅ | 219 | ID não duplicado no mesmo ano | "Código de identificação da operação já cadastrado" |
| **B112** ✅ | 311 | cert não-IP → transportador == cert | "O CPF/CNPJ do certificado digital não corresponde ao transportador..." |
| **B113** ✅ | 312 | cert não-IP → ID pertence ao cert | "...não corresponde ao transportador responsável pelo CIOT..." |
| **B115** ✅ | 314 | em nome próprio → contratado == emissor | "A empresa transportadora só pode emitir CIOT diretamente em nome próprio quando for o transportador contratado" |

> O `IdOperacaoTransporte` **tem que vir do endpoint `/gerar`** (ou da DLL) — ele
> calcula o DV. Não dá para montar/incrementar à mão (vira rejeição 205).

---

## ⚠️ Pegadinhas de payload (DCS v1.1)

| Campo | ❌ Errado | ✅ Correto |
|-------|----------|-----------|
| Veículo | `RNTRC` | **`RNTRCVeiculo`** (com sufixo) |
| Contratantes carga frac | `ContratantesCargaFrac` | **`ContratantesCargFrac`** (typo do DCS) |
| `DistanciaPercorrida` | float (`430.0`) → HTTP 500 | **int** (`430`) |
| `DataDeclaracao` | UTC / `Z` / sem offset → rej. 269 | **BRT `-03:00`** |
| `NumeroEixos` | string | **int** |
| `CodigoNaturezaCarga` | string / `4` | **int de 4 díg (NCM)** |
| `JustificativaContingencia` | `""` | **`null`** |
| `IdentificadorPix` | omitido (com ChavePix) | **auto-gerado** (YYYYMMDDHHMMSS) |
| `CpfCnpjInteressado` / `NCMCargaPrincipal` | enviados | **não existem** no body |

---

## 📑 Catálogo de mensagens de rejeição

Lista das rejeições do DCS (textos podem aparecer truncados por quebra de linha no PDF):

- O campo &lt;nome do campo&gt; é obrigatório / é inválido
- Não foi encontrado transportador contratado com CPF/CNPJ {0} e RNTRC {1}
- CPF/CNPJ e RNTRC informados não correspondem a um transportador [ativo]
- O RNTRC informado não pertence ao CPF/CNPJ do [transportador]
- Existe duplicidade de placa na lista informada
- A placa {0} não pertence ao transportador de RNTRC {1}, ou o mesmo não está ativo
- O veículo do tipo automotor informado não possui vínculo com o transportador contratado
- O(s) veículo(s) de placas {0} está(ão) contratado(s) para [outra operação]
- É necessário informar ao menos um veículo do tipo automotor
- Somente um veículo deve ser do tipo automotor
- É obrigatório informar ao menos um implemento quando o [veículo for cavalo-trator]
- Somente é permitido informar até 5 veículos para uma [operação]
- Quantidade de eixos inválida para o tipo de veículo informado
- O código da natureza da carga informado não existe
- Natureza da carga obrigatória para o tipo de operação informado
- Peso da carga deve ser maior que 0 e menor 9999999.99
- A data de início da viagem não pode ser inferior à data atual / à data de declaração
- A data prevista para término da viagem deve ser maior ou [igual ao início]
- A data e hora da declaração está fora do intervalo de tolerância
- A data da declaração deve ser menor ou igual à data atual e não [anterior a 30 dias]
- A data da declaração não pode ser anterior a 168 horas em [relação à atual]
- A data de início da viagem excede o limite máximo de 30 dias
- O intervalo entre a data de início e a data de fim da viagem [excede limite]
- O campo IdOperacaoTransporte é inválido
- Código de identificação da operação já cadastrado
- O contratado informado deve ser do tipo TAC para operações [TAC-Agregado]
- A operação de transporte do tipo TAC-Agregado não pode ser [retificada/...]
- CPF/CNPJ do destinatário obrigatório para o tipo de operação [informado]
- Já existem 2 CIOTs abertos/vigentes entre o contratante e o contratado
- Existem CIOTs pendentes de encerramento pelo contratante há [tempo]
- O valor do frete informado é menor do que o valor mínimo de frete
- O valor do frete deve ser informado
- Distância não compatível com a Origem/Destino informados
- Deve ser informada ao menos uma forma válida de localização (município, CEP ou coordenadas)
- Latitude e longitude devem ser informadas em conjunto
- O tipo de localização informado para origem deve ser o mesmo do destino
- Os campos obrigatórios para o tipo de pagamento informado [faltam]
- Não é permitido o tipo de pagamento informado para [TAC/equiparado]
- Não é permitido informar o tipo de pagamento por cartão pré-pago quando o cert não é de IP
- Os campos de parcelamento devem/não devem ser informados quando [...]
- O(s) contratante(s) da carga fracionada não pode(m) ser [iguais]
- O CPF/CNPJ do certificado digital não corresponde ao transportador / responsável pelo CIOT
- O contratante informado encontra-se bloqueado em função de penalidade vigente
- Esta administradora não tem permissão para declarar operações para o contratante de CNPJ {0}
- Não foi encontrada nenhuma Operação de Transporte com os [dados informados]
- O prazo para cancelamento / retificação da operação foi [excedido]
- Não é possível cancelar/retificar uma operação já [cancelada/encerrada]
- Operação de Transporte já está cancelada / encerrada
- Os dados da viagem são obrigatórios / não devem ser informados no encerramento
- Não é possível encerrar uma operação de transporte antes da [data de início]
