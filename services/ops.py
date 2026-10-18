"""
OpenPOIService (OPS) client.

Queries the local OPS instance at OPS_BASE_URL (port 5000) for POI locations
within a geometry, filtered by OPS category IDs.

Preferred query mode — GeoJSON polygon:
    Pass a Shapely geometry as `geom`.  It is simplified before sending
    (tolerance 0.01°, ~1 km) to reduce coordinate count, then serialised as
    a GeoJSON Polygon / MultiPolygon.  This is always smaller in area than
    the bounding-box rectangle and avoids OPS size-limit rejections.

Fallback — bounding-box:
    If no Shapely geometry is available (geocoded search-area path), pass
    `bbox` in Nominatim format [south, north, west, east].
"""

import requests
from config import OPS_BASE_URL, MAX_POIS_PER_CRITERION


class OpsError(Exception):
    pass


def _nominatim_to_ops_bbox(bbox: list) -> list:
    south, north, west, east = bbox
    return [[west, south], [east, north]]


def _geom_to_geojson(geom) -> dict:
    """Simplify a Shapely geometry and return a GeoJSON-compatible dict."""
    simplified = geom.simplify(0.01, preserve_topology=True)

    def _ring(coords):
        ring = [[round(x, 6), round(y, 6)] for x, y in coords]
        if ring[0] != ring[-1]:
            ring.append(ring[0])
        return ring

    if simplified.geom_type == "Polygon":
        coords = [_ring(simplified.exterior.coords)]
        for interior in simplified.interiors:
            coords.append(_ring(interior.coords))
        return {"type": "Polygon", "coordinates": coords}

    if simplified.geom_type == "MultiPolygon":
        polys = []
        for poly in simplified.geoms:
            rings = [_ring(poly.exterior.coords)]
            for interior in poly.interiors:
                rings.append(_ring(interior.coords))
            polys.append(rings)
        return {"type": "MultiPolygon", "coordinates": polys}

    # Fallback: bounding box polygon
    minx, miny, maxx, maxy = simplified.bounds
    return {
        "type": "Polygon",
        "coordinates": [[[minx, miny], [maxx, miny], [maxx, maxy], [minx, maxy], [minx, miny]]],
    }


def fetch_pois(filters: dict, bbox: list = None, geom=None) -> list:
    """
    Query OPS for POIs matching the given category filters.

    Args:
        filters: dict with 'category_ids' and/or 'category_group_ids' keys.
        geom:    Shapely Polygon/MultiPolygon — preferred over bbox.
        bbox:    Nominatim-style [south, north, west, east] — fallback.

    Returns:
        List of (lon, lat) tuples, at most MAX_POIS_PER_CRITERION items.

    Raises:
        OpsError on HTTP failure or unexpected response.
        ValueError if neither geom nor bbox is supplied.
    """
    if geom is not None:
        geometry_payload = {"geojson": _geom_to_geojson(geom)}
    elif bbox is not None:
        geometry_payload = {"bbox": _nominatim_to_ops_bbox(bbox)}
    else:
        raise ValueError("fetch_pois requires either geom or bbox")

    body = {
        "request":  "pois",
        "geometry": geometry_payload,
        "filters":  filters,
        "limit":    MAX_POIS_PER_CRITERION,
        "sortby":   "category",
    }

    try:
        resp = requests.post(f"{OPS_BASE_URL}/pois", json=body, timeout=30)
    except requests.ConnectionError:
        raise OpsError(
            f"Cannot connect to OPS at {OPS_BASE_URL}. "
            "Is the ops-api container running on port 5000?"
        )
    except requests.RequestException as exc:
        raise OpsError(f"OPS request failed: {exc}") from exc

    if not resp.ok:
        try:
            detail = resp.json()
            msg = f"code {detail.get('code', '?')}: {detail.get('message', resp.text)}"
        except Exception:
            msg = resp.text
        raise OpsError(f"OPS returned HTTP {resp.status_code} — {msg}")

    features = resp.json().get("features", [])
    coords = []
    for feat in features:
        try:
            lon, lat = feat["geometry"]["coordinates"]
            coords.append((lon, lat))
        except (KeyError, ValueError, TypeError):
            continue

    return coords[:MAX_POIS_PER_CRITERION]
