"""
Cascading wavefront isochrone computation.

For large travel times, direct ORS is slow (complexity grows quadratically
with the radius — ORS must visit every reachable road node).

Algorithm
─────────
Each "layer" advances the frontier by hop_minutes of travel time.
After k layers the accumulated union approximates the k×hop_minutes
isochrone from the origin.

  Layer 0  — compute hop_minutes isochrone from the origin (1 isochrone).

  Layer k  — for EACH isochrone in layer k-1, extract its N/S/E/W extreme
              points.  Deduplicate across all frontier isochrones.  Drop any
              candidate that falls inside the current accumulated union (it
              is already covered).  Compute hop_minutes isochrones from all
              remaining candidates in parallel.  Union the new isochrones
              into the accumulated result.  The new isochrones become the
              frontier for layer k+1.

Why per-isochrone extremes instead of union-boundary extremes?
──────────────────────────────────────────────────────────────
Taking extremes from the union boundary conflates road corridors running in
different directions into a single shape.  The southernmost point of a union
that covers both the coast road AND the inland highway is some average — it
may not sit on either corridor.

By contrast, taking the S extreme of each individual frontier isochrone
gives one point that faithfully sits at the end of whatever south-running
road led to that seed.  The cascade then extends that specific corridor
another hop_minutes further south.

Diagonal coverage emerges naturally: if the N seed's isochrone extends NE,
its E extreme chases the NE corridor; if the E seed's isochrone extends SE,
its S extreme chases the SE corridor.  No diagonal compass points are needed
because the tree branches cover them organically.

Pruning
───────
A seed that falls inside the accumulated union cannot generate new area
(any road reachable from it is already covered), so it is dropped.
This keeps the active frontier small even for very long travel times.

Wall-time comparison for a 480-min driving isochrone:
  Direct ORS:   times out
  Cascading:    ~30–60 s  (4 layers × up to ~16 parallel ORS calls/layer,
                            but pruning keeps most layers to 4–8 active seeds)
"""

import math
from concurrent.futures import ThreadPoolExecutor, as_completed

from shapely.geometry import Point as ShapelyPoint
from shapely.ops import unary_union

from .isochrone import fetch_isochrones, IsochroneError
from .geometry import union_polygons

# Below this threshold, direct ORS is fast enough — skip cascading overhead.
DIRECT_THRESHOLD_MINUTES = 240

# Size of each cascade hop.
# 120 min is the default: long enough for motorways to clearly outpace local
# roads (so cardinal extremes reliably land on fast corridors), yet short
# enough that each individual ORS call completes in a few seconds.
HOP_MINUTES = 120

# Maximum parallel ORS requests per layer.  ORS handles concurrent requests
# well, but cap this to avoid overwhelming the server.
MAX_WORKERS = 16


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cardinal_points(geom) -> list:
    """
    Return (lon, lat) tuples for the 4 cardinal extreme points (N, S, E, W)
    of a Shapely Polygon or MultiPolygon.

    For MultiPolygon (e.g. coastal results with island fragments) all
    component polygons are searched so a disconnected far-flung piece is
    not missed.

    Duplicate coordinates (possible in simple geometries) are removed so
    we don't waste ORS calls on the same point twice.
    """
    if geom.geom_type == "Polygon":
        coords = list(geom.exterior.coords)
    elif geom.geom_type == "MultiPolygon":
        coords = [c for poly in geom.geoms for c in poly.exterior.coords]
    else:
        # Fallback for exotic geometry types: use bounding-box mid-edges.
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        return [(cx, maxy), (cx, miny), (maxx, cy), (minx, cy)]

    raw = [
        max(coords, key=lambda c: c[1]),   # N — max lat
        min(coords, key=lambda c: c[1]),   # S — min lat
        max(coords, key=lambda c: c[0]),   # E — max lon
        min(coords, key=lambda c: c[0]),   # W — min lon
    ]

    # Deduplicate while preserving N/S/E/W order.
    seen   = set()
    unique = []
    for pt in raw:
        key = (round(pt[0], 6), round(pt[1], 6))
        if key not in seen:
            seen.add(key)
            unique.append(pt)
    return unique


def _fetch_one(lonlat: tuple, mode: str, minutes: int):
    """
    Compute a single isochrone and return a Shapely geometry (or None).
    Runs safely inside a worker thread.  Silently returns None on any ORS
    failure so one bad seed does not abort the entire layer.
    """
    try:
        polys = fetch_isochrones([lonlat], mode, minutes, strict=True)
        return union_polygons(polys)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_isochrone(
    origin_lonlat: tuple,
    mode: str,
    total_minutes: int,
    hop_minutes: int = HOP_MINUTES,
    progress_callback=None,
):
    """
    Compute an isochrone for ANY travel time using cascading wavefront expansion.

    Args:
        origin_lonlat:     (lon, lat) of the starting point.
        mode:              Travel mode key matching ORS_PROFILES
                           ("Drive", "Walk", "Cycle").
        total_minutes:     Total travel budget in minutes.
        hop_minutes:       Size of each cascade hop (default 120 min).
        progress_callback: Optional callable(hop: int, total_hops: int, msg: str)
                           called at the start of each layer.

    Returns:
        Shapely Polygon / MultiPolygon, or None if nothing was reachable.

    Raises:
        IsochroneError if the first hop from the origin fails entirely.
    """
    # ── Fast path ────────────────────────────────────────────────────────────
    if total_minutes <= DIRECT_THRESHOLD_MINUTES:
        polys = fetch_isochrones([origin_lonlat], mode, total_minutes, strict=True)
        return union_polygons(polys)

    # ── Build hop schedule ───────────────────────────────────────────────────
    # Full hops of hop_minutes, plus a remainder if total is not divisible.
    # e.g. 300 min @ 120 min/hop → [120, 120, 60]
    hops = []
    remaining = total_minutes
    while remaining > 0:
        hops.append(min(hop_minutes, remaining))
        remaining -= hop_minutes
    total_hops = len(hops)

    # ── Layer 0: seed from origin ────────────────────────────────────────────
    if progress_callback:
        progress_callback(1, total_hops,
                          f"layer 1/{total_hops} — {hops[0]} min from origin")

    polys = fetch_isochrones([origin_lonlat], mode, hops[0], strict=True)
    origin_geom = union_polygons(polys)
    if origin_geom is None or origin_geom.is_empty:
        raise IsochroneError(
            "Initial isochrone from origin returned empty geometry. "
            "Check that ORS has graphs built for this region."
        )

    accumulated    = origin_geom
    frontier_geoms = [origin_geom]   # isochrones computed in the previous layer

    # ── Layers 1‥N ──────────────────────────────────────────────────────────
    for layer_num, hop_size in enumerate(hops[1:], start=2):

        # Collect cardinal extremes from every frontier isochrone.
        candidate_set: set = set()
        for geom in frontier_geoms:
            for pt in _cardinal_points(geom):
                candidate_set.add((round(pt[0], 6), round(pt[1], 6)))

        # Prune seeds already inside the accumulated union — they add no new area.
        seeds = [
            pt for pt in candidate_set
            if not accumulated.contains(ShapelyPoint(pt[0], pt[1]))
        ]

        if progress_callback:
            progress_callback(
                layer_num, total_hops,
                f"layer {layer_num}/{total_hops} — {hop_size} min "
                f"from {len(seeds)} frontier seeds "
                f"(pruned {len(candidate_set) - len(seeds)} inside union)",
            )

        if not seeds:
            # All frontier points already covered — isochrone has converged.
            break

        # Compute isochrones for all seeds in parallel.
        new_layer_geoms: list = []
        workers = min(len(seeds), MAX_WORKERS)
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [
                executor.submit(_fetch_one, pt, mode, hop_size)
                for pt in seeds
            ]
            for future in as_completed(futures):
                geom = future.result()
                if geom is not None:
                    new_layer_geoms.append(geom)

        if not new_layer_geoms:
            break

        accumulated    = unary_union([accumulated] + new_layer_geoms)
        frontier_geoms = new_layer_geoms   # only this layer's isochrones feed the next

    return accumulated
