import streamlit as st
import folium
from streamlit_folium import st_folium
from shapely.ops import unary_union
from concurrent.futures import ThreadPoolExecutor, as_completed

from config import (
    POI_TYPES,
    ORS_PROFILES,
    CRITERION_COLORS,
    INTERSECTION_COLOR,
    INTERSECTION_FILL_OPACITY,
)
from services.geocoding import geocode_city, GeocodingError
from services.ops import fetch_pois, OpsError
from services.isochrone import fetch_isochrones, IsochroneError
from services.cascading_isochrone import compute_isochrone
from services.geometry import union_polygons, intersect_all, shapely_to_geojson

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Where Can I Live?",
    page_icon="🗺️",
    layout="wide",
)

st.markdown("""
<style>
  .block-container {
      padding-top:    0.5rem !important;
      padding-bottom: 0      !important;
  }
  section[data-testid="stSidebar"] { overflow-y: auto; }

  /*
   * Make the folium iframe fill the remaining window height.
   * 'stFullScreenFrame' is the actual class Streamlit 1.3x applies to the
   * custom-component wrapper; the iframe inside it gets our vh-based height.
   * If this selector misses on a future Streamlit version, the Python
   * MAP_HEIGHT constant below is the safe fallback.
   */
  .stCustomComponentV1 iframe,
  [class*="stCustomComponent"] iframe,
  .stFullScreenFrame iframe {
      height: calc(100vh - 90px) !important;
      min-height: 400px;
  }
</style>
""", unsafe_allow_html=True)

# Pixel height passed to st_folium as a fallback if the CSS above doesn't
# land on the correct selector.  On a 1080 p monitor the usable area below
# the Streamlit header is roughly 90 px less than the viewport, so 900 px
# is a safe approximation.  Adjust this single constant if your screen
# shows the map cut off or with a large gap beneath it.
MAP_HEIGHT = 980

st.title("🗺️ Where Can I Live?")
st.caption("Add locations and POI criteria — the map shows every area satisfying them all at once.")

# ---------------------------------------------------------------------------
# Session-state initialisation
# ---------------------------------------------------------------------------
def _init():
    defaults = {
        "locations":    [],
        "search_area":  "Australia",
        "criteria": [
            {"poi_type": "Beach",    "mode": "Walk",  "minutes": 30,  "group": "A"},
            {"poi_type": "Hospital", "mode": "Drive", "minutes": 120, "group": "B"},
        ],
        "loc_results":  [],
        "results":      [],
        "intersection": None,
        "map_center":   [-25.2744, 133.7751],
        "map_zoom":     4,
        # Result caches — keyed by fingerprint strings
        "_loc_cache":   {},   # fp → {union, point, display}
        "_poi_cache":   {},   # fp → {union, poi_count}
        # Map-pin picking state
        "pin_pick_idx":         None,   # location index awaiting a map click
        "last_consumed_click":  None,   # (lat, lng) we already used
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


_init()


# ---------------------------------------------------------------------------
# Cache fingerprinting helpers
# ---------------------------------------------------------------------------
def _loc_fingerprint(loc: dict) -> str:
    """Stable string key for a location entry."""
    if loc.get("input_type") == "Name / address":
        return f"addr|{loc.get('city', '').strip().lower()}|{loc['mode']}|{loc['minutes']}"
    return (f"coords|{float(loc.get('lat', 0)):.5f}"
            f"|{float(loc.get('lon', 0)):.5f}|{loc['mode']}|{loc['minutes']}")


def _poi_fingerprint(crit: dict, bbox_fp: str) -> str:
    """Stable string key for a POI criterion + the bbox it was searched in."""
    return f"poi|{crit['poi_type']}|{crit['mode']}|{crit['minutes']}|{bbox_fp}"


def _bbox_fingerprint(locations: list) -> str:
    """Fingerprint for the set of locations that determine the POI search area."""
    return "|".join(_loc_fingerprint(l) for l in locations) or "no_locations"


# ---------------------------------------------------------------------------
# ORS per-mode limits — config cap and slow-warning threshold
# ---------------------------------------------------------------------------
ORS_MAX_SECONDS = {
    "Drive": 28800,   # 480 min — set in ors-config.yml
    "Walk":  14400,   # 240 min
    "Cycle": 14400,   # 240 min
}
# Beyond these values computation takes several minutes; warn the user.
ORS_SLOW_MINUTES = {
    "Drive": 150,
    "Walk":  60,
    "Cycle": 60,
}


def _check_ors_limit(mode: str, minutes: int):
    """Raise ValueError if minutes exceeds the ORS server cap;
    show an info notice if it is likely to be slow."""
    limit_s = ORS_MAX_SECONDS.get(mode, 7200)
    limit_m = limit_s // 60
    if minutes * 60 > limit_s:
        raise ValueError(
            f"{mode} isochrones are capped at **{limit_m} minutes** in ORS. "
            f"You requested {minutes} min. "
            f"To increase the limit edit `maximum_range_time` in "
            f"`ors-config.yml` and run `docker restart ors-app`."
        )
    slow = ORS_SLOW_MINUTES.get(mode, 60)
    if minutes > slow:
        st.info(
            f"⏳ {minutes} min {mode} isochrone may take **1–4 minutes** to compute "
            f"— ORS explores a large area of the road network."
        )


# ---------------------------------------------------------------------------
# Resolve a single location dict → (lon, lat), display_name
# ---------------------------------------------------------------------------
def _resolve_one(loc):
    if loc["input_type"] == "Name / address":
        geo = geocode_city(loc["city"])
        return (geo["center"][1], geo["center"][0]), geo["display_name"]
    lon, lat = float(loc["lon"]), float(loc["lat"])
    return (lon, lat), f"{lat:.5f}, {lon:.5f}"


# ---------------------------------------------------------------------------
# Location worker  (runs in a ThreadPoolExecutor — NO Streamlit calls here)
# ---------------------------------------------------------------------------
def _run_location(idx: int, loc: dict):
    """
    Resolve + compute a single location isochrone.

    Returns:
        (idx, geom, lonlat, display, messages, error_str)
        geom is None and error_str is set on failure.
        messages is a list of (kind, text) pairs accumulated during computation
        and replayed in the main thread afterwards.
    """
    messages = []
    try:
        lonlat, display = _resolve_one(loc)
        messages.append(("write", f"📌 Resolved: **{display}**"))

        def _progress(hop, total_hops, msg):
            messages.append(("write", f"↳ {msg}"))

        geom = compute_isochrone(
            lonlat,
            loc["mode"],
            loc["minutes"],
            progress_callback=_progress,
        )

        if geom is None or geom.is_empty:
            return idx, None, lonlat, display, messages, (
                "ORS returned no polygon. Check travel time is within ORS limits "
                "and graphs are built for this region."
            )

        return idx, geom, lonlat, display, messages, None

    except Exception as exc:                          # GeocodingError, IsochroneError, …
        return idx, None, None, None, messages, str(exc)


# ---------------------------------------------------------------------------
# Search  (with incremental caching)
# ---------------------------------------------------------------------------
def run_search():
    st.session_state.loc_results  = []
    st.session_state.results      = []
    st.session_state.intersection = None

    all_iso_geoms       = []   # locations + per-group POI unions (fed to intersect_all)
    loc_iso_geoms       = []
    crit_geoms_by_group = {}   # group_letter → [criterion_union, ...]
    map_center          = None

    loc_cache = st.session_state._loc_cache
    poi_cache = st.session_state._poi_cache

    # ── 1. Location isochrones ────────────────────────────────────────────
    # Pass 1 — split into cache hits and misses, collect hits immediately.
    loc_assembled = {}    # idx → entry dict (filled from cache OR parallel compute)
    locs_to_compute = []  # [(idx, loc, fp, color, label), ...]

    for idx, loc in enumerate(st.session_state.locations):
        fp       = _loc_fingerprint(loc)
        color    = CRITERION_COLORS[idx % len(CRITERION_COLORS)]
        loc_name = loc.get("city") or f"{loc.get('lat', 0):.3f}, {loc.get('lon', 0):.3f}"
        label    = f"Within {loc['minutes']} min {loc['mode']} of {loc_name}"

        if fp in loc_cache:
            cached = loc_cache[fp]
            loc_assembled[idx] = {
                "union":       cached["union"],
                "color":       color,
                "label":       label,
                "point":       cached["point"],
                "display":     cached["display"],
                "is_location": True,
            }
            st.success(f"⚡ **Location {idx + 1}** — {label} *(cached)*")
        else:
            locs_to_compute.append((idx, loc, fp, color, label))

    # Pass 2 — parallel cascading compute for cache misses.
    if locs_to_compute:
        n = len(locs_to_compute)
        plural = "isochrone" if n == 1 else "isochrones"
        using_cascade = any(loc["minutes"] > 90 for _, loc, _, _, _ in locs_to_compute)
        method_note   = " via cascading wavefront" if using_cascade else ""

        with st.status(
            f"📍 Computing {n} location {plural} in parallel{method_note}…",
            expanded=True,
        ) as loc_status:

            with ThreadPoolExecutor(max_workers=n) as executor:
                future_map = {
                    executor.submit(_run_location, idx, loc): (idx, fp, color, label)
                    for idx, loc, fp, color, label in locs_to_compute
                }

                for future in as_completed(future_map):
                    idx, fp, color, label = future_map[future]
                    r_idx, geom, lonlat, display, messages, error = future.result()

                    # Replay progress messages (thread-safe now we're in main thread)
                    for kind, msg in messages:
                        st.write(msg)

                    if error:
                        st.error(f"❌ **Location {idx + 1}** — {error}")
                    elif geom is not None:
                        loc_cache[fp] = {
                            "union":   geom,
                            "point":   {"lat": lonlat[1], "lon": lonlat[0]},
                            "display": display,
                        }
                        loc_assembled[idx] = {
                            "union":       geom,
                            "color":       color,
                            "label":       label,
                            "point":       {"lat": lonlat[1], "lon": lonlat[0]},
                            "display":     display,
                            "is_location": True,
                        }
                        st.write(f"✅ **Location {idx + 1}** complete")
                    else:
                        st.warning(f"⚠️ **Location {idx + 1}** — no polygon returned.")

            done_count = sum(
                1 for idx, _, _, _, _ in locs_to_compute if idx in loc_assembled
            )
            loc_status.update(
                label=f"✅ {done_count}/{n} location {plural} computed",
                state="complete",
                expanded=False,
            )

    # Pass 3 — assemble loc_results in index order so layer colours stay consistent.
    for idx in sorted(loc_assembled.keys()):
        entry = loc_assembled[idx]
        st.session_state.loc_results.append(entry)
        loc_iso_geoms.append(entry["union"])
        all_iso_geoms.append(entry["union"])
        if map_center is None:
            map_center = [entry["point"]["lat"], entry["point"]["lon"]]

    # ── 2. POI search geometry & its cache fingerprint ───────────────────
    poi_geom = None   # Shapely geometry — preferred for OPS queries
    poi_bbox = None   # Nominatim bbox — fallback for geocoded search area
    bbox_fp  = _bbox_fingerprint(st.session_state.locations)

    if loc_iso_geoms:
        if len(loc_iso_geoms) > 1:
            candidate = intersect_all(loc_iso_geoms)
            if candidate is None or candidate.is_empty:
                candidate = unary_union(loc_iso_geoms)
        else:
            candidate = loc_iso_geoms[0]

        if candidate and not candidate.is_empty:
            poi_geom = candidate   # send the actual polygon to OPS, not its bbox

    if poi_geom is None and poi_bbox is None:
        sa = st.session_state.search_area.strip()
        if not sa:
            st.error("Please add at least one location or enter a search area.")
            return

        with st.status("📍 Resolving search area…", expanded=True) as sa_st:
            try:
                geo        = geocode_city(sa)
                poi_bbox   = geo["bbox"]
                map_center = geo["center"]
                bbox_fp    = f"geocoded:{sa.lower()}"
                st.write(f"✅ {geo['display_name']}")
                sa_st.update(
                    label=f"📍 {geo['display_name']}", state="complete", expanded=False
                )
            except GeocodingError as exc:
                st.error(str(exc))
                sa_st.update(label="Search area failed", state="error")
                return

    if map_center is None:
        if poi_geom is not None:
            minx, miny, maxx, maxy = poi_geom.bounds
            map_center = [(miny + maxy) / 2, (minx + maxx) / 2]
        else:
            south, north, west, east = poi_bbox
            map_center = [(south + north) / 2, (west + east) / 2]

    st.session_state.map_center = map_center
    st.session_state.map_zoom   = 9

    # ── 3. POI criteria ───────────────────────────────────────────────────
    colour_offset = len(st.session_state.locations)

    for idx, crit in enumerate(st.session_state.criteria):
        fp    = _poi_fingerprint(crit, bbox_fp)
        color = CRITERION_COLORS[(idx + colour_offset) % len(CRITERION_COLORS)]
        label = f"{crit['poi_type']} — {crit['minutes']} min {crit['mode']}"

        if fp in poi_cache:
            # ── Cache hit ──────────────────────────────────────────────────
            cached = poi_cache[fp]
            entry  = {
                "union":        cached["union"],
                "color":        color,
                "label":        label,
                "poi_count":    cached["poi_count"],
                "poi_locations": cached["poi_locations"],
            }
            st.session_state.results.append(entry)
            crit_geoms_by_group.setdefault(crit.get("group", "A"), []).append(cached["union"])
            st.success(f"⚡ **Criterion {idx + 1}** — {label} *(cached)*")

        else:
            # ── Cache miss: compute ────────────────────────────────────────
            with st.status(f"Criterion {idx + 1}: {label}", expanded=True) as c_status:
                st.write(f"🔎 Querying OPS for **{crit['poi_type']}**…")
                try:
                    locations = fetch_pois(
                        POI_TYPES[crit["poi_type"]],
                        geom=poi_geom,
                        bbox=poi_bbox,
                    )
                except OpsError as exc:
                    st.warning(f"OPS error: {exc}")
                    c_status.update(
                        label=f"Criterion {idx + 1} — OPS failed", state="error"
                    )
                    continue

                if not locations:
                    st.warning(f"No **{crit['poi_type']}** found in this area.")
                    c_status.update(
                        label=f"Criterion {idx + 1} — no POIs", state="complete"
                    )
                    continue

                st.write(f"Found **{len(locations)}** location(s). Generating isochrones…")
                progress_bar = st.progress(0)

                def _cb(pbar, total):
                    def cb(current, _total):
                        pbar.progress(min(current / max(total, 1), 1.0))
                    return cb

                try:
                    _check_ors_limit(crit["mode"], crit["minutes"])
                    polys = fetch_isochrones(
                        locations, crit["mode"], crit["minutes"],
                        progress_callback=_cb(progress_bar, len(locations)),
                    )
                except (IsochroneError, ValueError) as exc:
                    st.warning(str(exc))
                    c_status.update(
                        label=f"Criterion {idx + 1} — ORS failed", state="error"
                    )
                    continue

                progress_bar.progress(1.0)
                union_geom = union_polygons(polys)

                if union_geom is None:
                    st.warning("All isochrones empty — try a longer travel time.")
                    c_status.update(
                        label=f"Criterion {idx + 1} — empty", state="complete"
                    )
                    continue

                poi_cache[fp] = {
                    "union":         union_geom,
                    "poi_count":     len(locations),
                    "poi_locations": locations,
                }
                entry = {
                    "union":         union_geom,
                    "color":         color,
                    "label":         label,
                    "poi_count":     len(locations),
                    "poi_locations": locations,
                }
                st.session_state.results.append(entry)
                crit_geoms_by_group.setdefault(crit.get("group", "A"), []).append(union_geom)
                c_status.update(
                    label=f"✅ Criterion {idx + 1} done ({len(polys)} isochrones)",
                    state="complete", expanded=False,
                )

    # ── 4. Combine criteria by group: OR within group, AND across groups ──
    for grp, geoms in crit_geoms_by_group.items():
        if not geoms:
            continue
        merged = union_polygons(geoms) if len(geoms) > 1 else geoms[0]
        if merged is not None and not merged.is_empty:
            all_iso_geoms.append(merged)

    # ── 5. Intersection ───────────────────────────────────────────────────
    if len(all_iso_geoms) >= 2:
        with st.status("⚙️ Computing intersection…", expanded=False) as int_status:
            intersection = intersect_all(all_iso_geoms)
            st.session_state.intersection = intersection
            int_status.update(
                label="✅ Intersection computed" if intersection else "⚠️ No overlapping area",
                state="complete",
            )


# ---------------------------------------------------------------------------
# Map builder
# ---------------------------------------------------------------------------
def build_map() -> folium.Map:
    m = folium.Map(
        location=st.session_state.map_center,
        zoom_start=st.session_state.map_zoom,
        # CARTO basemaps now require an API key, so use the keyless
        # OpenStreetMap tiles instead (no signup / no external key needed).
        tiles="OpenStreetMap",
    )

    # Pre-search pin markers — show placed pins before search runs.
    # Suppressed once loc_results is populated to avoid duplicating the resolved markers.
    if not st.session_state.loc_results:
        for i, loc in enumerate(st.session_state.locations):
            if loc.get("input_type") not in ("Map pin", "Coordinates"):
                continue
            lat_v = float(loc.get("lat") or 0)
            lon_v = float(loc.get("lon") or 0)
            if lat_v == 0 and lon_v == 0:
                continue
            folium.Marker(
                location=[lat_v, lon_v],
                tooltip=f"Location {i + 1} (pending)",
                icon=folium.Icon(color="blue", icon="map-pin", prefix="fa"),
            ).add_to(m)

    # Location markers + isochrone layers
    # Heavier border (weight 3) visually separates them from POI layers (weight 2)
    # without needing dashes that become invisible at typical zoom levels.
    for res in st.session_state.loc_results:
        pt = res["point"]
        folium.Marker(
            location=[pt["lat"], pt["lon"]],
            tooltip=res["display"],
            icon=folium.Icon(color="red", icon="home", prefix="fa"),
        ).add_to(m)

        folium.GeoJson(
            shapely_to_geojson(res["union"]),
            name=res["label"],
            style_function=lambda _f, c=res["color"]: {
                "fillColor":   c,
                "color":       c,
                "fillOpacity": 0.35,
                "weight":      3,
                "opacity":     1.0,
            },
            tooltip=res["label"],
        ).add_to(m)

    # POI criterion layers — isochrone polygon + individual POI markers
    for res in st.session_state.results:
        folium.GeoJson(
            shapely_to_geojson(res["union"]),
            name=res["label"],
            style_function=lambda _f, c=res["color"]: {
                "fillColor":   c,
                "color":       c,
                "fillOpacity": 0.30,
                "weight":      2,
                "opacity":     0.9,
            },
            tooltip=res["label"],
        ).add_to(m)

        poi_group = folium.FeatureGroup(name=f"{res['label']} — POIs", show=True)
        for lon, lat in res.get("poi_locations", []):
            folium.CircleMarker(
                location=[lat, lon],
                radius=4,
                color=res["color"],
                fill=True,
                fill_color=res["color"],
                fill_opacity=0.85,
                weight=1,
                tooltip=res["label"],
            ).add_to(poi_group)
        poi_group.add_to(m)

    # Intersection layer
    intersection = st.session_state.intersection
    if intersection is not None and not intersection.is_empty:
        folium.GeoJson(
            shapely_to_geojson(intersection),
            name="✅ Matching area (all criteria)",
            style_function=lambda _f: {
                "fillColor":   INTERSECTION_COLOR,
                "color":       INTERSECTION_COLOR,
                "fillOpacity": INTERSECTION_FILL_OPACITY,
                "weight":      2.5,
                "opacity":     0.95,
            },
            tooltip="This area satisfies ALL your criteria",
        ).add_to(m)

    # Auto-fit bounds — encompass results, intersection, and pre-search pins
    bounds_box = None  # [[lat_min, lon_min], [lat_max, lon_max]]

    all_geoms = [r["union"] for r in st.session_state.loc_results + st.session_state.results]
    if intersection is not None and not intersection.is_empty:
        all_geoms.append(intersection)

    if all_geoms:
        bounds_geom = unary_union(all_geoms)
        minx, miny, maxx, maxy = bounds_geom.bounds
        bounds_box = [[miny, minx], [maxy, maxx]]
    else:
        # Pre-search: include any placed Map pin / Coordinates locations
        pts = []
        for loc in st.session_state.locations:
            if loc.get("input_type") not in ("Map pin", "Coordinates"):
                continue
            lat_v = float(loc.get("lat") or 0)
            lon_v = float(loc.get("lon") or 0)
            if lat_v == 0 and lon_v == 0:
                continue
            pts.append((lat_v, lon_v))
        if pts:
            lats = [p[0] for p in pts]
            lons = [p[1] for p in pts]
            bounds_box = [[min(lats), min(lons)], [max(lats), max(lons)]]

    if bounds_box:
        (la0, lo0), (la1, lo1) = bounds_box
        # Buffer single points / collinear pins so fit_bounds gives a city-scale view
        if la0 == la1 and lo0 == lo1:
            bounds_box = [[la0 - 0.05, lo0 - 0.05], [la1 + 0.05, lo1 + 0.05]]
        m.fit_bounds(bounds_box, padding=(30, 30))

    # Legend
    all_results = st.session_state.loc_results + st.session_state.results
    if all_results:
        def _legend_row(r):
            border = "border:2px dashed #555;" if r.get("is_location") else ""
            count  = "location" if r.get("is_location") else f"{r['poi_count']} POIs"
            return (
                f'<div style="display:flex;align-items:center;gap:8px;margin:4px 0;">'
                f'<div style="width:14px;height:14px;background:{r["color"]};'
                f'border-radius:3px;opacity:0.85;flex-shrink:0;{border}"></div>'
                f'<span style="font-size:12px;">{r["label"]} <em>({count})</em></span>'
                f'</div>'
            )

        legend_rows = "".join(_legend_row(r) for r in all_results)

        if intersection is not None and not intersection.is_empty:
            legend_rows += (
                f'<div style="display:flex;align-items:center;gap:8px;margin:8px 0 4px;">'
                f'<div style="width:14px;height:14px;background:{INTERSECTION_COLOR};'
                f'border-radius:3px;flex-shrink:0;"></div>'
                f'<strong style="font-size:12px;">Matching area (all criteria)</strong></div>'
            )

        m.get_root().html.add_child(folium.Element(
            '<div style="position:fixed;bottom:30px;left:30px;z-index:9999;'
            'background:white;padding:12px 16px;border-radius:8px;'
            'box-shadow:2px 2px 8px rgba(0,0,0,0.25);max-width:340px;">'
            '<strong style="font-size:13px;">Legend</strong>'
            f'<div style="margin-top:8px;">{legend_rows}</div>'
            '</div>'
        ))
        folium.LayerControl(collapsed=True).add_to(m)

    return m


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("⚙️ Settings")

    # ── Locations ─────────────────────────────────────────────────────────
    st.subheader("📍 Locations")
    st.caption("Each location generates a travel-time isochrone. All are intersected with POI layers.")

    to_remove_loc = None
    for i, loc in enumerate(st.session_state.locations):
        loc_label = loc.get("city") or f"{loc.get('lat', 0):.3f}, {loc.get('lon', 0):.3f}"
        color     = CRITERION_COLORS[i % len(CRITERION_COLORS)]
        dot       = (f'<span style="display:inline-block;width:10px;height:10px;'
                     f'background:{color};border-radius:50%;margin-right:6px;'
                     f'border:1px dashed #555;"></span>')

        with st.expander(f"Location {i + 1}: {loc_label}", expanded=True):
            st.markdown(dot + f"**Layer {i + 1}**", unsafe_allow_html=True)

            input_options = ["Name / address", "Coordinates", "Map pin"]
            current_input = loc.get("input_type", "Name / address")
            input_idx     = input_options.index(current_input) if current_input in input_options else 0
            loc["input_type"] = st.radio(
                "Input method",
                input_options,
                index=input_idx,
                key=f"loc_type_{i}",
                horizontal=True,
                label_visibility="collapsed",
            )

            if loc["input_type"] == "Name / address":
                loc["city"] = st.text_input(
                    "City / suburb / address",
                    value=loc.get("city", ""),
                    key=f"loc_city_{i}",
                )
            elif loc["input_type"] == "Coordinates":
                c1, c2 = st.columns(2)
                with c1:
                    loc["lat"] = st.number_input(
                        "Latitude",
                        value=float(loc.get("lat", 0.0)),
                        format="%.5f",
                        key=f"loc_lat_{i}",
                    )
                with c2:
                    loc["lon"] = st.number_input(
                        "Longitude",
                        value=float(loc.get("lon", 0.0)),
                        format="%.5f",
                        key=f"loc_lon_{i}",
                    )
            else:  # Map pin
                lat_v = float(loc.get("lat") or 0)
                lon_v = float(loc.get("lon") or 0)
                if lat_v == 0 and lon_v == 0:
                    st.caption("📍 *No pin set yet.*")
                else:
                    st.caption(f"📍 Pin at **{lat_v:.5f}, {lon_v:.5f}**")

                if st.session_state.pin_pick_idx == i:
                    st.info("👆 Click anywhere on the map to place the pin.")
                    if st.button("Cancel", key=f"cancel_pin_{i}", use_container_width=True):
                        st.session_state.pin_pick_idx = None
                        st.rerun()
                else:
                    btn_label = "📍 Move pin" if (lat_v or lon_v) else "📍 Pick on map"
                    if st.button(btn_label, key=f"pick_pin_{i}", use_container_width=True):
                        st.session_state.pin_pick_idx = i
                        st.rerun()

            col_m, col_t = st.columns(2)
            with col_m:
                mode_keys   = list(ORS_PROFILES.keys())
                mode_idx    = mode_keys.index(loc["mode"]) if loc.get("mode") in mode_keys else 2
                loc["mode"] = st.selectbox(
                    "Mode", mode_keys, index=mode_idx, key=f"loc_mode_{i}"
                )
            with col_t:
                loc["minutes"] = st.number_input(
                    "Minutes", min_value=5, max_value=720,
                    value=int(loc.get("minutes", 120)), step=5, key=f"loc_min_{i}",
                )

            if st.button("🗑 Remove location", key=f"rm_loc_{i}", use_container_width=True):
                to_remove_loc = i

    if to_remove_loc is not None:
        st.session_state.locations.pop(to_remove_loc)
        st.rerun()

    if st.button("➕ Add location", use_container_width=True):
        st.session_state.locations.append({
            "input_type": "Name / address",
            "city":       "",
            "lat":        0.0,
            "lon":        0.0,
            "mode":       "Drive",
            "minutes":    120,
        })
        st.rerun()

    st.text_input(
        "Search area (POI fallback)",
        key="search_area",
        help="Used as the POI search area when no locations are added. Ignored when locations are present.",
    )

    st.divider()

    # ── POI Criteria ──────────────────────────────────────────────────────
    st.subheader("📏 POI Criteria")
    st.caption("Same group letter = **OR**.  Different groups = **AND**.")

    to_remove = None
    for i, crit in enumerate(st.session_state.criteria):
        colour_offset = len(st.session_state.locations)
        color = CRITERION_COLORS[(i + colour_offset) % len(CRITERION_COLORS)]
        dot   = (f'<span style="display:inline-block;width:10px;height:10px;'
                 f'background:{color};border-radius:50%;margin-right:6px;"></span>')

        with st.expander(f"Criterion {i + 1}: {crit['poi_type']}", expanded=True):
            st.markdown(dot + f"**Layer {i + 1 + colour_offset}**", unsafe_allow_html=True)

            poi_keys  = list(POI_TYPES.keys())
            poi_index = poi_keys.index(crit["poi_type"]) if crit["poi_type"] in poi_keys else 0
            crit["poi_type"] = st.selectbox(
                "POI type", poi_keys, index=poi_index, key=f"poi_{i}"
            )

            col_mode, col_min = st.columns(2)
            with col_mode:
                mode_keys  = list(ORS_PROFILES.keys())
                mode_index = mode_keys.index(crit["mode"]) if crit["mode"] in mode_keys else 0
                crit["mode"] = st.selectbox(
                    "Mode", mode_keys, index=mode_index, key=f"mode_{i}"
                )
            with col_min:
                crit["minutes"] = st.number_input(
                    "Minutes", min_value=5, max_value=720,
                    value=int(crit["minutes"]), step=5, key=f"min_{i}",
                )

            grp_keys    = [chr(65 + k) for k in range(10)]   # A–J
            current_grp = crit.get("group", "A")
            grp_index   = grp_keys.index(current_grp) if current_grp in grp_keys else 0
            crit["group"] = st.selectbox(
                "Group (same letter = OR, different = AND)",
                grp_keys, index=grp_index, key=f"grp_{i}",
            )

            if st.button("🗑 Remove criterion", key=f"rm_{i}", use_container_width=True):
                to_remove = i

    if to_remove is not None:
        st.session_state.criteria.pop(to_remove)
        st.rerun()

    if st.button("➕ Add criterion", use_container_width=True):
        used_groups = {c.get("group", "A") for c in st.session_state.criteria}
        next_group  = next((chr(65 + k) for k in range(26) if chr(65 + k) not in used_groups), "A")
        st.session_state.criteria.append({
            "poi_type": "Supermarket",
            "mode":     "Walk",
            "minutes":  20,
            "group":    next_group,
        })
        st.rerun()

    st.divider()

    search_btn = st.button(
        "🔍 Find Locations",
        type="primary",
        use_container_width=True,
        disabled=(
            len(st.session_state.criteria) == 0 and
            len(st.session_state.locations) == 0
        ),
    )

    # Show cache stats + clear button only when there is something cached
    loc_cached = len(st.session_state._loc_cache)
    poi_cached = len(st.session_state._poi_cache)
    if loc_cached or poi_cached:
        st.caption(
            f"💾 Cache: {loc_cached} location isochrone(s), {poi_cached} POI layer(s)"
        )
        if st.button("🗑️ Clear cache", use_container_width=True):
            st.session_state._loc_cache   = {}
            st.session_state._poi_cache   = {}
            st.session_state.loc_results  = []
            st.session_state.results      = []
            st.session_state.intersection = None
            st.rerun()


# ---------------------------------------------------------------------------
# Main area: map (left, ~75 %) │ activity log (right, ~25 %)
# ---------------------------------------------------------------------------
map_col, log_col = st.columns([3, 1])

with log_col:
    if search_btn:
        run_search()

    all_results  = st.session_state.loc_results + st.session_state.results
    intersection = st.session_state.intersection

    if all_results:
        st.divider()
        if intersection is not None and not intersection.is_empty:
            st.success("**Areas found!** The dark overlay satisfies **all** criteria.")
        elif len(all_results) >= 2:
            st.warning(
                "No overlapping area found. Try increasing travel times or reducing criteria."
            )
        else:
            res = all_results[0]
            if res.get("is_location"):
                st.success(
                    "Location isochrone shown. "
                    "Add POI criteria or more locations to compute an intersection."
                )
            else:
                st.info("One layer shown. Add more criteria to compute an intersection.")

        for res in all_results:
            label = res["label"]
            value = "location" if res.get("is_location") else f"{res['poi_count']} POIs"
            st.metric(label, value)

    elif not search_btn:
        st.markdown("""
**How it works**

1. **Add locations** — e.g. family members' cities.
   Each generates a travel-time bubble.

2. **Add POI criteria** — e.g. *Supermarket within 20 min Walk*.

3. Click **Find Locations**.

Results are **cached** — only changed or new criteria are recomputed on the next search.

---
*Dashed outlines = location isochrones
Solid fills = POI coverage
Dark overlay = intersection of all layers*
        """)

with map_col:
    map_data = st_folium(
        build_map(),
        height=MAP_HEIGHT,
        use_container_width=True,
        returned_objects=["last_clicked"],
        key="main_map",
    )

# ---------------------------------------------------------------------------
# Map-pin click handler — consume a fresh click into the active picking slot
# ---------------------------------------------------------------------------
if (
    st.session_state.pin_pick_idx is not None
    and map_data
    and map_data.get("last_clicked")
):
    click     = map_data["last_clicked"]
    click_key = (round(click["lat"], 6), round(click["lng"], 6))
    if click_key != st.session_state.last_consumed_click:
        idx = st.session_state.pin_pick_idx
        if 0 <= idx < len(st.session_state.locations):
            st.session_state.locations[idx]["lat"] = click["lat"]
            st.session_state.locations[idx]["lon"] = click["lng"]
        st.session_state.pin_pick_idx        = None
        st.session_state.last_consumed_click = click_key
        st.rerun()
