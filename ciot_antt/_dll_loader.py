"""Wrapper opcional para a DLL GeradorCIOTShared.dll da ANTT.

A DLL gera IdOperacaoTransporte válidos chamando a API interna da ANTT
(/token + /gerar). Requer pythonnet instalado e Windows + .NET runtime.

Uso:
    from ciot_antt._dll_loader import gerar_id_via_dll
    id_op = gerar_id_via_dll("12345678000190", dll_dir="caminho/para/geradorciotdll")
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional

_svc = None  # singleton da instância .NET


def _init_dll(dll_dir: str) -> None:
    """Inicializa runtime .NET + carrega DLL. Idempotente."""
    global _svc
    if _svc is not None:
        return

    from clr_loader import get_coreclr
    from pythonnet import set_runtime

    dll_path = Path(dll_dir).resolve()
    if not (dll_path / "GeradorCIOTShared.dll").exists():
        raise FileNotFoundError(f"GeradorCIOTShared.dll não encontrada em {dll_path}")

    # Cria runtimeconfig minimal se não existir (DLL é netstandard2.0)
    cfg = dll_path / "GeradorCIOTShared.runtimeconfig.json"
    if not cfg.exists():
        # Tenta net6 → net9 → net8 (na ordem dos mais comuns instalados)
        for tfm, ver in [("net6.0", "6.0.0"), ("net9.0", "9.0.0"), ("net8.0", "8.0.0")]:
            try:
                cfg.write_text(json.dumps({
                    "runtimeOptions": {
                        "tfm": tfm,
                        "framework": {"name": "Microsoft.NETCore.App", "version": ver},
                    }
                }, indent=2), encoding="utf-8")
                break
            except Exception:
                continue

    try:
        set_runtime(get_coreclr(runtime_config=str(cfg)))
    except Exception:
        # Runtime já pode ter sido setado pelo processo
        pass

    import sys, clr
    if str(dll_path) not in sys.path:
        sys.path.insert(0, str(dll_path))
    clr.AddReference("GeradorCIOTShared")

    from GeradorCIOTShared import GeradorCIOTService_v3  # type: ignore
    _svc = GeradorCIOTService_v3()


def gerar_id_via_dll(cnpj: str, dll_dir: str) -> str:
    """Gera um IdOperacaoTransporte válido (12 chars) via DLL ANTT.

    Args:
        cnpj: CNPJ do contratante (14 dígitos, sem pontuação).
        dll_dir: Caminho do diretório contendo GeradorCIOTShared.dll.

    Returns:
        Código de 12 chars (ex: '560000015411') aceito pela regra B16 da ANTT.

    Raises:
        FileNotFoundError: se DLL não estiver no dll_dir.
        Exception: se chamada à DLL falhar (sem rede, .NET ausente, etc).
    """
    _init_dll(dll_dir)
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    return str(_svc.GerarCIOT(cnpj_limpo))


def validar_ciot_via_dll(cnpj: str, dll_dir: str) -> str:
    """Valida um CIOT existente via DLL."""
    _init_dll(dll_dir)
    return str(_svc.ValidarCIOT(cnpj))
