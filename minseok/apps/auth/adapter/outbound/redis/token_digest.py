import hashlib


def digest(token: str) -> str:
    """세션 토큰의 저장용 키 — SHA-256 hex. 토큰은 48바이트 난수라 솔트 없이도 역산할 수 없다."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
