"""Split a PostgreSQL script into statements without cutting dollar-quoted blocks."""


def split_sql(script: str) -> list[str]:
    statements: list[str] = []
    current: list[str] = []
    index = 0
    in_dollar = False
    length = len(script)
    while index < length:
        if not in_dollar and script.startswith("--", index):
            newline = script.find("\n", index)
            if newline == -1:
                break
            index = newline + 1
            continue
        if script.startswith("$$", index):
            in_dollar = not in_dollar
            current.append("$$")
            index += 2
            continue
        character = script[index]
        if character == ";" and not in_dollar:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            index += 1
            continue
        current.append(character)
        index += 1
    if in_dollar:
        raise ValueError("SQL script has an unclosed dollar quote.")
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements
