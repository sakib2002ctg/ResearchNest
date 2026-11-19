from fastapi import Request


def client_ip(request: Request) -> str | None:
    # Proxy headers are not trusted here; trusted proxy handling belongs at ingress.
    return request.client.host[:45] if request.client else None
