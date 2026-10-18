import requests
from config import NOMINATIM_URL


class GeocodingError(Exception):
    pass


def geocode_city(city_name: str) -> dict:
    """
    Geocode a city/area name via Nominatim.

    Returns:
        {
            "bbox":         [south, north, west, east],   # floats, WGS-84
            "center":       [lat, lon],
            "display_name": str,
        }

    Raises:
        GeocodingError on no result or HTTP failure.
    """
    params = {
        "q":             city_name,
        "format":        "json",
        "limit":         1,
        "addressdetails": 0,
    }
    headers = {"User-Agent": "ClaudeMapOrsOps/1.0"}

    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise GeocodingError(f"Nominatim request failed: {exc}") from exc

    results = resp.json()
    if not results:
        raise GeocodingError(f"No results found for '{city_name}'")

    r = results[0]
    # Nominatim boundingbox order: [south, north, west, east]
    south, north, west, east = (float(x) for x in r["boundingbox"])

    return {
        "bbox":         [south, north, west, east],
        "center":       [float(r["lat"]), float(r["lon"])],
        "display_name": r.get("display_name", city_name),
    }
