import math


def delta_e_cie76(L1, a1, b1, L2, a2, b2):
    """CIE76 Delta E — Euclidean distance in Lab colour space."""
    return math.sqrt(
        (float(L1) - float(L2)) ** 2 +
        (float(a1) - float(a2)) ** 2 +
        (float(b1) - float(b2)) ** 2
    )