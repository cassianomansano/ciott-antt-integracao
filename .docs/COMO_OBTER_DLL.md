# DLL `GeradorCIOTShared.dll` — uso e referência técnica

A DLL e o executável **já estão incluídos neste repositório** em `.docs/geradorciotdll/` e `.docs/geradorciotexe/`. São distribuídos publicamente pela ANTT.

> Em caso de versão atualizada, baixe a versão mais recente direto da ANTT (e-mail `pef@antt.gov.br`).

---

## 📁 Estrutura

```
.docs/geradorciotdll/
├── GeradorCIOTShared.dll          ← biblioteca .NET Standard 2.0 (~10 KB)
├── GeradorCIOTShared.deps.json    ← dependências
└── GeradorCIOTShared.pdb          ← debug symbols (opcional)

.docs/geradorciotexe/
├── GeradorCIOT.exe                ← app GUI Avalonia v3.1 (~90 MB self-contained)
├── GeradorCIOT.pdb
├── GeradorCIOTShared.pdb
├── libHarfBuzzSharp.pdb
└── libSkiaSharp.pdb
```

---

## ⚙️ Como usar no SDK Python

```python
from ciot_antt import CiotClient

client = CiotClient(
    cert_pfx="caminho/cert.pfx",
    cert_password="senha",
    cnpj_interessado="12345678000190",
    env="homologacao",
    dll_geradorciot_dir=".docs/geradorciotdll",  # ← caminho da pasta
)

# Ao declarar sem id_operacao, SDK chama a DLL automaticamente
resp = client.declarar_operacao(dados_sem_id_operacao)
```

Requisitos:
- Windows + .NET Runtime **6.0, 8.0 ou 9.0** instalado
- `pip install -e ".[dll]"` (instala `pythonnet`)

---

## 🔧 Como funciona por baixo

A DLL chama a API interna da ANTT em duas etapas:

```
POST {base}/token   body: {"chave": "<segredo embutido>"}    → {"token": "<JWT>"}
POST {base}/gerar   header Authorization: Bearer <JWT>       → dados.ciot.Dados.CIOT
                    body: {"cnpj": "<CNPJ-CONTRATANTE>"}
```

A "chave" fica embutida na DLL. Por isso a DLL é distribuída pronta — você não precisa configurar nada.

CIOTs gerados seguem padrão `[ID-administradora-7-chars][sequencial-5-chars]`:
- Exemplo: `5600000XXXXX`
- Validados pela regra B16 do DCS — formato "ID administradora + DV"

---

## 🖥 Usar o executável GUI (alternativa)

Se preferir gerar CIOTs manualmente:

```
.docs/geradorciotexe/GeradorCIOT.exe
```

- Digite o CNPJ contratante
- Clique GERAR CIOT
- Copie o código de 12 chars
- Cole no campo `aux_id_operacao_manual` da aba Auxiliares do `tester.py`

---

## ⚠️ Observações

- Em produção, os CIOTs gerados são **reais** — sujeitos a multa de R$ 10.500
  se não encerrados em até 5 dias após `DataFimViagem`.
- Em homologação, CIOTs gerados não têm validade legal.
- Versão atual: **v3.1** (compilada por `izaias.costa` em `C:\Users\izaias.costa\source\repos\GeradorCIOTShared`).

---

## 📧 Contato técnico ANTT

- **`pef@antt.gov.br`** (canal oficial)
- `jose-aa.filho@antt.gov.br` · (61) 3410-1561
