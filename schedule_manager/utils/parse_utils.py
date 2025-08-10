# utils/parse_utils.py
def parse_id_list(text: str) -> list[int]:
    """
    '1, 2,3' -> [1,2,3]
    빈문자열 -> []
    숫자 이외 토큰은 무시
    """
    if not text.strip():
        return []
    seen = set()
    out = []
    for tok in text.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if not tok.isdigit():
            continue
        n = int(tok)
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out
