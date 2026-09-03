import math


def haversine_km(lat1, lng1, lat2, lng2):
    """Great-circle distance in km between two lat/lng points. Good enough
    for a ballpark 'nearby customer' reference -- not road distance."""
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))
