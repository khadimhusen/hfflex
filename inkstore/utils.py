import math


def delta_e_cie76(L1, a1, b1, L2, a2, b2):
    """CIE76 Delta E — Euclidean distance in Lab colour space."""
    return math.sqrt(
        (float(L1) - float(L2)) ** 2 +
        (float(a1) - float(a2)) ** 2 +
        (float(b1) - float(b2)) ** 2
    )

def sort_by_nearest_neighbour_grouped(inks, mode='nw'):
    if not inks:
        return []

    def get_lab(ink):
        if mode == 'nw':
            return ink.l_nw, ink.a_nw, ink.b_nw
        return ink.l_ww, ink.a_ww, ink.b_ww

    def get_hue_group(ink):
        L, a, b = get_lab(ink)
        if L is None or a is None or b is None:
            return None
        if float(L) == 0 and float(a) == 0 and float(b) == 0:
            return None
        h = math.degrees(math.atan2(float(b), float(a)))
        if h < 0:
            h += 360
        return int(h // 30)  # 0–11 (12 groups of 30°)

    def greedy_chain(group_inks):
        """Nearest-neighbour chain within one hue group."""
        if not group_inks:
            return []
        unvisited = list(group_inks)
        chain = [unvisited.pop(0)]
        while unvisited:
            current = chain[-1]
            cL, cA, cB = get_lab(current)
            nearest, nearest_de = None, float('inf')
            for ink in unvisited:
                iL, iA, iB = get_lab(ink)
                de = delta_e_cie76(
                    float(cL), float(cA), float(cB),
                    float(iL), float(iA), float(iB)
                )
                if de < nearest_de:
                    nearest_de, nearest = de, ink
            unvisited.remove(nearest)
            chain.append(nearest)
        return chain

    # Split into 12 hue groups + no-data bucket
    groups     = {i: [] for i in range(12)}
    no_data    = []

    for ink in inks:
        g = get_hue_group(ink)
        if g is None:
            no_data.append(ink)
        else:
            groups[g].append(ink)

    # Run greedy chain on each group, concat in hue order
    result = []
    for i in range(12):
        result.extend(greedy_chain(groups[i]))

    result.extend(no_data)
    return result

def get_hue(L, a, b):
    if a is None or b is None:
        return 999
    # treat 0,0,0 (unmeasured dummy rows) as no data
    if float(L) == 0 and float(a) == 0 and float(b) == 0:
        return 999
    h = math.degrees(math.atan2(float(b), float(a)))
    return h + 360 if h < 0 else h