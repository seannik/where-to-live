import requests
from config import OVERPASS_URL, MAX_POIS_PER_CRITERION


class OverpassError(Exception):
    pass


def _build_query(filter_expr: str, bbox: list) -> str:
    """
    Build an Overpass QL query.

    bbox = [south, north, west, east]   (Nominatim order)
    Overpass bbox format = (south, west, north, east)
    """
    s, n, w, e = bbox[0], bbox[1], bbox[2], bbox[3]
    overpass_bbox = f"({s},{w},{n},{e})"

    return (
        f"[out:json][timeout:60];\n"
        f"(\n"
        f"  node[{filter_expr}]{overpass_bbox};\n"
        f"  way[{filter_expr}]{overpass_bbox};\n"
        f"  relation[{filter_expr}]{overpass_bbox};\n"
        f");\n"
        f"out center {MAX_POIS_PER_CRITERION};\n"
    )


def fetch_pois(filter_expr: str, bbox: list) -> list:
    """
    Query Overpass for POIs matching filter_expr within bbox.

    Returns:
        List of (lon, lat) tuples — ORS expects longitude first.
        At most MAX_POIS_PER_CRITERION items.

    Raises:
        OverpassError on HTTP failure.
    """
    query = _build_query(filter_expr, bbox)

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=60,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise OverpassError(f"Overpass request failed: {exc}") from exc

    data = resp.json()
    coords = []

    for el in data.get("elements", []):
        if el["type"] == "node":
            lat, lon = el["lat"], el["lon"]
        elif "center" in el:
            # ways and relations return a centroid under "center"
            lat, lon = el["center"]["lat"], el["center"]["lon"]
        else:
            continue
        coords.append((lon, lat))   # ORS convention: [longitude, latitude]

    return coords[:MAX_POIS_PER_CRITERION]
