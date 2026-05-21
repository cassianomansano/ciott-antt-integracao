import ssl
import tempfile
import os

import requests
from requests.adapters import HTTPAdapter
from cryptography.hazmat.primitives.serialization import pkcs12, Encoding, PrivateFormat, NoEncryption
from cryptography.hazmat.primitives.serialization.pkcs12 import load_key_and_certificates

from .exceptions import CiotAuthError


class _MtlsAdapter(HTTPAdapter):
    def __init__(self, ssl_context: ssl.SSLContext, **kwargs):
        self._ssl_context = ssl_context
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def build_mtls_session(cert_pfx: str, password: str) -> requests.Session:
    try:
        with open(cert_pfx, "rb") as f:
            pfx_data = f.read()
    except OSError as e:
        raise CiotAuthError(f"Não foi possível ler o certificado: {e}") from e

    try:
        pwd_bytes = password.encode() if isinstance(password, str) else password
        private_key, certificate, additional_certs = load_key_and_certificates(
            pfx_data, pwd_bytes
        )
    except Exception as e:
        raise CiotAuthError(f"Falha ao carregar certificado .pfx: {e}") from e

    cert_pem = certificate.public_bytes(Encoding.PEM)
    key_pem = private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())

    # Escreve em arquivos temporários — ssl.SSLContext.load_cert_chain exige caminhos
    cert_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    key_file = tempfile.NamedTemporaryFile(delete=False, suffix=".pem")
    try:
        cert_file.write(cert_pem)
        cert_file.flush()
        key_file.write(key_pem)
        key_file.flush()
        cert_file.close()
        key_file.close()

        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile=cert_file.name, keyfile=key_file.name)
        # Não verifica cadeia da ANTT em homologação (cert auto-assinado)
        # Em produção, configurar: ctx.load_verify_locations(cafile="cadeia-icp-brasil.pem")
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    finally:
        os.unlink(cert_file.name)
        os.unlink(key_file.name)

    session = requests.Session()
    adapter = _MtlsAdapter(ctx)
    session.mount("https://", adapter)
    session.headers.update({"Content-Type": "application/json"})
    return session
