from shapely.ops import unary_union
from shapely.geometry import mapping


def union_polygons(polygons: list):
    """
    Merge all isochrone polygons for one criterion into a single geometry.
    Returns None if the list is empty or the result is empty.
    """
    if not polygons:
        return None
    result = unary_union(polygons)
    return None if result.is_empty else result


def intersect_all(geometries: list):
    """
    Progressively intersect a list of Shapely geometries (one per criterion).
    Short-circuits and returns None as soon as the intersection becomes empty.
    Returns None if the input list is empty.
    """
    if not geometries:
        return None

    result = geometries[0]
    for geom in geometries[1:]:
        result = result.intersection(geom)
        if result.is_empty:
            return None

    return result


def shapely_to_geojson(geom) -> dict:
    """
    Convert any Shapely geometry to a GeoJSON Feature dict
    ready for folium.GeoJson().
    """
    return {
        "type":       "Feature",
        "geometry":   mapping(geom),
        "properties": {},
    }
