import folium
import gpxpy


def get_map(file_path):
    gpx_file = open(file_path, 'r')
    gpx = gpxpy.parse(gpx_file)
    points = []
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                points.append(tuple([point.latitude, point.longitude]))
    latitude = sum(p[0] for p in points) / len(points)
    longitude = sum(p[1] for p in points) / len(points)
    folium_map = folium.Map(location=[latitude, longitude], zoom_start=10)
    folium.PolyLine(points, color="red", weight=2.5, opacity=1).add_to(folium_map)
    return folium_map._repr_html_()
