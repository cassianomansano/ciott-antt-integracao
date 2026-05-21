class CiotError(Exception):
    pass


class CiotApiError(CiotError):
    def __init__(self, codigo: str, mensagem: str, protocolo: str = ""):
        self.codigo = codigo
        self.mensagem = mensagem
        self.protocolo = protocolo
        super().__init__(f"[{codigo}] {mensagem}")


class CiotAuthError(CiotError):
    pass


class CiotValidationError(CiotError):
    pass
