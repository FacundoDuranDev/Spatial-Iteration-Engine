ASCII_SETS = {
    "suave": " .:-=+*#%@",
    "denso": " .'`^\",:;Il!i~+_-?][}{1)(|\\/tfjrxnuvczXYUJCLQ0OZmwqpdbkhao*#MW&8%B@$",
}


def resolve_charset(name_or_charset: str) -> str:
    return ASCII_SETS.get(name_or_charset, name_or_charset)
