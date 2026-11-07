import re

_NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}"
_PLAIN = re.compile(rf"^(?P<sign>-)?(?P<dollar>\$)?(?P<number>{_NUMBER})$")
_PAREN = re.compile(rf"^\((?P<dollar>\$)?(?P<number>{_NUMBER})\)$")


def _cents(number: str) -> int:
    whole, frac = number.replace(",", "").split(".")
    return int(whole) * 100 + int(frac)


def parse_amount(token: str) -> int:
    if not isinstance(token, str):
        raise ValueError(str(token))
    text = token.strip()
    paren = _PAREN.fullmatch(text)
    if paren:
        return -_cents(paren.group("number"))
    plain = _PLAIN.fullmatch(text)
    if not plain:
        raise ValueError(token)
    cents = _cents(plain.group("number"))
    return -cents if plain.group("sign") else cents
