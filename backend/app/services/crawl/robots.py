"""A small robots.txt reader for User-agent: *."""


def disallowed_prefixes(robots_text: str) -> list[str]:
    prefixes: list[str] = []
    applies = False
    saw_agent = False
    for raw in (robots_text or "").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key == "user-agent":
            applies = value == "*"
            saw_agent = True
        elif key == "disallow" and (applies or not saw_agent) and value:
            prefixes.append(value)
    return prefixes


def path_allowed(path: str, prefixes: list[str]) -> bool:
    target = path or "/"
    return not any(target.startswith(prefix) for prefix in prefixes)
