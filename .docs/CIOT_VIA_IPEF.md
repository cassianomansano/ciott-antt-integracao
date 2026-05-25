# CIOT gratuito via IPEF — quando esse SDK NÃO é pra você

> Este projeto (`ciot-antt`) é um SDK técnico que fala direto com a API da ANTT.
> Se você não é desenvolvedor e só precisa emitir CIOT esporadicamente, o caminho
> mais simples é usar o **canal gratuito de uma IPEF habilitada**.

---

## 1. Vou conseguir mesmo de graça?

**Sim, com fricção.** A Resolução ANTT 5.862/2019 obriga toda IPEF (Instituição
de Pagamento Eletrônico de Frete) a oferecer canal gratuito de geração de CIOT
pela internet. Na prática:

- O gratuito existe, mas fica escondido atrás de cadastro burocrático
- Vendedor da IPEF empurra produto pago (cartão frete, TAG pedágio, integração)
- Cadastro leva **3 a 15 dias úteis** — não serve pra frete que sai hoje
- Encerramento é manual (viagem por viagem) no portal — sem API

Se você aceita essas condições, dá pra emitir 100% sem custo.

---

## 2. Qual IPEF escolher

Lista oficial: [portal ANTT — instituições habilitadas](https://www.gov.br/antt/pt-br/assuntos/cargas/pagamento-eletronico-de-fretes-pef-ciot/instituicoes-de-pagamento-eletronico-de-frete).

> 📣 **Aviso da comunidade (atualizado 2026-05-25):** relatos preliminares
> de usuários indicam que, na prática, **algumas IPEFs criam fricção pesada**
> no canal gratuito — cadastros que não saem, suporte que não responde,
> redirecionamento insistente para plano pago. A **eFrete** tem sido citada
> como uma das poucas com fluxo gratuito realmente operacional para usuário
> esporádico.
>
> Este documento **não afirma conduta deliberada** de nenhuma instituição.
> Resolução ANTT 5.862/2019 garante gratuidade; se você enfrentar dificuldade,
> use os canais oficiais da §10.
>
> Sua experiência foi diferente do esperado? **Abra uma issue no repositório**
> relatando IPEF, prazo de cadastro e se conseguiu emitir. Vamos manter este
> guia vivo com dados reais da comunidade.

Ranking por facilidade real do plano gratuito (não pela ordem da ANTT):

| IPEF | Cadastro | Pressão pra plano pago | Relato comunidade 2026-05 | Recomendação |
|---|---|---|---|---|
| **eFrete** | Simples | Baixa | ✅ Gratuito operacional | ⭐ Comece por aqui |
| **Target Bank** | Simples, online | Baixa | ⚠️ Relatos mistos | Alternativa |
| **Roadcard "CIOT gratuito"** | Contrato adesão + documentos | Média | ⚠️ Relatos mistos | Alternativa |
| **Repom** | Burocrático | Alta | ❌ Relatos de fricção | Evitar p/ uso esporádico |
| Sem Parar / NDD / Bradesco | Foco em cartão frete | Alta | ❌ Relatos de fricção | Pular |
| Fitbank / PagBem | Voltado B2B | Alta | — sem relatos | Só se tiver volume |

> Coluna "Relato comunidade" reflete depoimentos informais de usuários, não
> teste sistemático. Atualizada conforme issues abertas. Discordância? Reporte.

---

## 3. Como evitar cair no upsell

Quando o vendedor ligar/responder, **escreva esse pedido por e-mail** (deixa
prova documental):

> "Quero utilizar apenas o canal gratuito de geração de CIOT previsto na
> Resolução ANTT nº 5.862/2019. Confirme por e-mail que não há cobrança
> obrigatória para essa emissão básica, nem produtos vinculados que precise
> contratar."

Argumentos comuns do vendedor e o que responder:

| Vendedor diz | Verdade | Resposta |
|---|---|---|
| "Pra agilizar use nosso cartão frete" | CIOT independe de cartão | "Não, vou usar canal gratuito" |
| "Integração com seu sistema custa R$X/mês" | API é só do pago | "Não preciso, vou usar pelo portal web" |
| "Sem nossa TAG pedágio você não emite" | Mentira, TAG é outro produto | "TAG não é requisito de CIOT" |
| "Plano gratuito não tem suporte" | Verdade parcial — tem e-mail | "Aceito suporte só por e-mail" |

---

## 4. Dados a separar antes

Tenha em mãos:

- **Transportador:** RNTRC (9 dígitos com zero à esquerda se necessário), CPF/CNPJ, dados bancários ou chave Pix
- **Contratante:** CPF/CNPJ, razão social
- **Veículo:** placa(s) — formato `AAA9999` ou `AAA9A99`, sem traço
- **Rota:** origem, destino, distância aproximada
- **Carga:** tipo de mercadoria, peso, NCM principal
- **Frete:** valor (respeitando piso mínimo ANTT), forma de pagamento
- **Datas:** início e fim previsto da viagem
- **Vale-pedágio:** valor quando aplicável

⚠️ **Armadilhas comuns:**
- RNTRC com 8 dígitos → preencher zero à esquerda → 9 dígitos
- Valor de frete abaixo do piso ANTT → rejeição
- Placa com traço/espaço → rejeição
- CPF/CNPJ com dígito verificador errado → rejeição

---

## 5. Passo-a-passo realista

| Passo | O que fazer | Tempo |
|---|---|---|
| 1 | Cadastrar na IPEF escolhida (site dela) | 3 a 15 dias úteis |
| 2 | Aguardar liberação de usuário/senha | dias |
| 3 | Acessar portal, preencher dados da operação | 10-30 min (primeira) |
| 4 | Confirmar e gerar CIOT | imediato |
| 5 | Salvar comprovante + registrar no CT-e | 2 min |
| 6 | **Encerrar dentro do prazo** (ver §6) | manual, por viagem |

Primeira emissão = sempre lenta. Da segunda em diante: 5-10 min.

---

## 6. Encerramento — onde a multa mais bate

**R$ 10.500 por CIOT não encerrado**, por viagem. Mais comum que erro de emissão.

Prazos legais:

| Tipo de operação | Prazo de encerramento |
|---|---|
| Lotação | 5 dias corridos após término da viagem |
| Fracionada | 5 dias corridos após término da viagem |
| TAC-Agregado | manual ao final do contrato |

No plano gratuito, encerramento é manual: portal → buscar CIOT → "encerrar" →
informar peso real → confirmar. **Crie alerta no celular** pra cada CIOT
emitido.

---

## 7. Quando o gratuito vira gargalo

| Perfil | Gratuito serve? |
|---|---|
| 1 a 5 CIOTs/mês, sem ERP | ✅ Sim, vale a chatice |
| 5 a 30 CIOTs/mês | ⚠️ Marginal — encerramento manual vira gargalo |
| 30+ CIOTs/mês | ❌ Não — partir pra plano pago ou SDK |
| Integração com ERP/CT-e | ❌ Não — só plano pago tem API |

---

## 8. Quando partir pro SDK (esse projeto)

Considere a integração direta DCS PEF v1.1 (esse repositório) se:

- Volume > 30 CIOTs/mês
- ERP próprio precisa emitir/encerrar automaticamente
- Encerramento manual no portal IPEF vira risco operacional
- Quer evitar mensalidade/lock-in de IPEF paga

Requisitos:
- Certificado ICP-Brasil A1 (`.pfx`)
- Cadastro técnico junto à SUTEC/ANTT: `pef@antt.gov.br` · (61) 3410-1561
- Desenvolvedor pra integrar o SDK no fluxo

Veja o [README principal](../README.md) pros detalhes técnicos.

---

## 9. Onde reclamar quando o gratuito não sai

Resolução ANTT 5.862/2019 obriga IPEF habilitada a oferecer canal gratuito.
Se o cadastro emperra, suporte some ou querem te empurrar plano pago como
condição, **registre por escrito e use os canais oficiais**:

| Canal | Para quê | Como |
|---|---|---|
| **Ouvidoria ANTT** | Descumprimento de norma por IPEF | https://ouvidoria.antt.gov.br |
| **SUTEC/ANTT** | Questão técnica/regulatória do PEF | pef@antt.gov.br · (61) 3410-1561 |
| **Procon estadual** | Cobrança indevida ou prática abusiva | site Procon do seu estado |
| **Consumidor.gov.br** | Mediação direta com a IPEF | https://www.consumidor.gov.br |

**Antes de reclamar:** tenha em mãos prints da tela, e-mails trocados e
o pedido escrito de canal gratuito (texto da §3). Sem prova documental,
reclamação não anda.

**Contribua com o guia:** abra uma [issue no repositório](https://github.com/cassianomansano/ciott-antt-integracao/issues/new)
com a tag `ipef-status` relatando sua experiência. Quanto mais relatos,
mais útil o ranking da §2 fica pros próximos.

---

## 10. Links úteis

| Recurso | Link |
|---|---|
| FAQ ANTT — PEF/CIOT | https://portal.antt.gov.br/perguntas-frequentes/-/categories/362297 |
| Lista oficial IPEFs | https://www.gov.br/antt/pt-br/assuntos/cargas/pagamento-eletronico-de-fretes-pef-ciot/instituicoes-de-pagamento-eletronico-de-frete |
| Consulta pública CIOT | https://consultapublica.antt.gov.br/Site/ConsultaCIOT.aspx |
| Resolução 5.862/2019 | https://www.gov.br/antt/pt-br/assuntos/cargas/pagamento-eletronico-de-fretes-pef-ciot |
| eFrete — busque pelo portal oficial via Google | (não linkado para evitar URL errada — confirme na lista oficial ANTT acima) |
| Target Bank — CIOT gratuito | https://www.transportesbra.com.br/vectiofretepublico/Default.aspx |
| Roadcard — CIOT gratuito | https://roadcard.com.br/geracao-de-ciot-gratuito/ |

---

> Este documento tem finalidade orientativa. Regras e plataformas podem mudar —
> confirme no portal ANTT e no canal oficial da IPEF antes de implantar.
