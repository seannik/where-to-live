import requests
from shapely.geometry import shape
from config import ORS_BASE_URL, ORS_PROFILES, ORS_BATCH_SIZE


class IsochroneError(Exception):
    pass


def _post_batch(profile: str, locations: list, range_seconds: int) -> list:
    """
    Single ORS isochrones call for up to ORS_BATCH_SIZE locations.

    Returns list of GeoJSON Feature dicts (one polygon per location).
    Raises IsochroneError on HTTP failure.
    """
    url  = f"{ORS_BASE_URL}/isochrones/{profile}"
    body = {
        "locations":  locations,      # [[lon, lat], ...]
        "range":      [range_seconds],
        "range_type": "time",
    }

    try:
        resp = requests.post(url, json=body, timeout=300)   # 5 min — large isochrones are slow
    except requests.RequestException as exc:
        raise IsochroneError(f"ORS request failed: {exc}") from exc

    if resp.status_code != 200:
        try:
            detail = resp.json()
        except Exception:
            detail = resp.text
        raise IsochroneError(f"ORS returned {resp.status_code}: {detail}")

    return resp.json().get("features", [])


def fetch_isochrones(
    locations: list,
    travel_mode: str,
    max_minutes: int,
    progress_callback=None,
    strict: bool = False,
) -> list:
    """
    Generate isochrone polygons for every location in batches.

    Args:
        locations:         List of (lon, lat) tuples.
        travel_mode:       Key from ORS_PROFILES ("Walk", "Cycle", "Drive").
        max_minutes:       Travel time limit in minutes.
        progress_callback: Optional callable(current: int, total: int).
        strict:            If True, re-raise ORS errors instead of silently
                           skipping the failed batch.  Use for single-point
                           calls (locations) where any failure is fatal.

    Returns:
        List of valid Shapely Polygon / MultiPolygon objects.
        In non-strict mode, locations in failed batches are silently skipped.

    Raises:
        IsochroneError if travel_mode is not recognised, or (in strict mode)
        if any ORS batch request fails.
    """
    profile = ORS_PROFILES.get(travel_mode)
    if profile is None:
        raise IsochroneError(f"Unknown travel mode: {travel_mode!r}. "
                             f"Valid modes: {list(ORS_PROFILES.keys())}")

    range_seconds = max_minutes * 60
    polygons      = []
    total         = len(locations)

    for start in range(0, total, ORS_BATCH_SIZE):
        batch    = locations[start: start + ORS_BATCH_SIZE]
        loc_list = [list(loc) for loc in batch]   # (lon, lat) tuples -> lists

        try:
            features = _post_batch(profile, loc_list, range_seconds)
        except IsochroneError:
            if strict:
                raise   # surface the real ORS error to the caller
            # Non-strict: skip the failed batch; don't abort the whole criterion
            if progress_callback:
                progress_callback(min(start + ORS_BATCH_SIZE, total), total)
            continue

        for feat in features:
            try:
                geom = shape(feat["geometry"])
                if not geom.is_valid:
                    geom = geom.buffer(0)   # repair self-intersecting rings
                if not geom.is_empty:
                    polygons.append(geom)
            except Exception:
                continue

        if progress_callback:
            progress_callback(min(start + ORS_BATCH_SIZE, total), total)

    return polygons
