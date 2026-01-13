
import os
import pandas as pd
import geopandas as gpd
from taipy.gui import Gui

# ---------- Instellingen ----------
# Inladen data
GPKG_PATH = os.path.join("Data", "AC-gemiddelde-VB.gpkg")
MEETOBJECT_COL = "MeetobjectCode"

if not os.path.exists(GPKG_PATH):
    raise FileNotFoundError(f"GPKG-bestand niet gevonden op {GPKG_PATH}. Plaats het bestand in een 'data'-map.")

# ---------- GeoPackage inlezen ----------
try:
    layers_df = gpd.list_layers(GPKG_PATH)
    layer_name = layers_df["name"].iloc[0] if len(layers_df) > 0 else None
except Exception:
    layer_name = None

gdf = gpd.read_file(GPKG_PATH, layer=layer_name)

# Indien geen punten: gebruik centroid
if not gdf.geometry.geom_type.isin(["Point"]).all():
    gdf["geometry"] = gdf.geometry.centroid

# CRS naar WGS84
try:
    gdf = gdf.to_crs(epsg=4326)
except Exception:
    pass

# lat/lon uit geometrie
if gdf.geometry is None or gdf.geometry.is_empty.all():
    raise ValueError("Geen geometrie gevonden in GPKG.")
gdf["lat"] = gdf.geometry.y
gdf["lon"] = gdf.geometry.x

# ---------- Stof-kolommen ----------
exclude_cols = {MEETOBJECT_COL, "geometry", "lat", "lon"}
stof_cols = sorted([c for c in gdf.columns if c not in exclude_cols and pd.api.types.is_numeric_dtype(gdf[c])])
if not stof_cols:
    raise ValueError("Geen numerieke stofkolommen gevonden.")

# ---------- UI-state ----------
gekozen_stoffen = [stof_cols[0]]
selected_points = []
selected_values_str = ""
zoek_meetpunt = ""
map_style = "open-street-map"
status_msg = ""

# Kaartdata
df_stations = gdf[[MEETOBJECT_COL, "lat", "lon"]].copy()
df_stations["text"] = df_stations[MEETOBJECT_COL]

# Vaste marker-stijl
marker_dyn = {"color": "#FF3131", "size": 14, "opacity": 0.95}

# Kaartlayout
layout = {
    "dragmode": "zoom",
    "mapbox": {
        "style": map_style,
        "center": {"lat": 52.1, "lon": 5.3},
        "zoom": 6
    }
}

# ---------- Helpers ----------
def format_nl(value, decimals=3):
    """Formatteer numeriek met NL-notatie."""
    if value is None or pd.isna(value):
        return "—"
    s = f"{float(value):,.{decimals}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

# ---------- Functies ----------
def _update_selected_values(state):
    if state.selected_points and state.gekozen_stoffen and len(state.df_stations) > 0:
        idx = state.selected_points[0]
        meetcode = state.df_stations.iloc[idx][MEETOBJECT_COL]
        rij = gdf.loc[gdf[MEETOBJECT_COL] == meetcode]
        if rij.empty:
            state.selected_values_str = ""
            return
        regels = []
        for s in sorted(state.gekozen_stoffen, key=str.lower):
            waarde = rij[s].iloc[0]
            if pd.isna(waarde):
                regels.append(f"- {s} = —")
            else:
                regels.append(f"- {s} = {format_nl(waarde)} µg/l")
        state.selected_values_str = "\n".join(regels)
    else:
        state.selected_values_str = "Selecteer een meetpunt op de kaart of gebruik de zoekfunctie."

def _perform_search(state, term: str):
    term = (term or "").strip()
    if not term:
        state.selected_points = []
        _update_selected_values(state)
        state.status_msg = "Voer een MeetobjectCode in en klik op **Zoeken**."
        return

    hits = state.df_stations.index[state.df_stations[MEETOBJECT_COL] == term].tolist()
    if not hits:
        hits = state.df_stations.index[state.df_stations[MEETOBJECT_COL].str.lower() == term.lower()].tolist()
    if not hits:
        hits = state.df_stations.index[state.df_stations[MEETOBJECT_COL].str.lower().str.startswith(term.lower())].tolist()
    if not hits:
        hits = state.df_stations.index[state.df_stations[MEETOBJECT_COL].str.lower().str.contains(term.lower())].tolist()

    if hits:
        idx = hits[0]
        state.selected_points = [idx]
        lat = state.df_stations.iloc[idx]["lat"]
        lon = state.df_stations.iloc[idx]["lon"]
        state.layout["mapbox"]["center"] = {"lat": float(lat), "lon": float(lon)}
        state.layout["mapbox"]["zoom"] = 12
        _update_selected_values(state)
        state.status_msg = f"Gevonden: {state.df_stations.iloc[idx][MEETOBJECT_COL]}"
    else:
        state.selected_points = []
        _update_selected_values(state)
        state.status_msg = "Geen match gevonden."

def zoek_meetpunt_action(state):
    _perform_search(state, state.zoek_meetpunt)

def reset_map_action(state):
    state.selected_points = []
    state.layout["mapbox"]["center"] = {"lat": 52.1, "lon": 5.3}
    state.layout["mapbox"]["zoom"] = 6
    _update_selected_values(state)
    state.status_msg = "Kaart en selectie zijn gereset."

def download_values_action(state):
    if not state.selected_points or not state.gekozen_stoffen:
        state.status_msg = "Niets te downloaden: selecteer eerst een punt en stof(fen)."
        return
    idx = state.selected_points[0]
    meetcode = state.df_stations.iloc[idx][MEETOBJECT_COL]
    rij = gdf.loc[gdf[MEETOBJECT_COL] == meetcode]
    if rij.empty:
        state.status_msg = "Kon selectie niet exporteren."
        return
    export_cols = [MEETOBJECT_COL] + list(sorted(state.gekozen_stoffen, key=str.lower))
    df_out = rij[export_cols].copy()
    path = os.path.join(os.getcwd(), f"waarden_{meetcode}.csv")
    df_out.to_csv(path, index=False)
    state.status_msg = f"CSV opgeslagen als: `{path}`"

# ---------- Callback ----------
def on_change(state, var_name, var_value):
    if var_name in ("gekozen_stoffen",):
        _update_selected_values(state)
    elif var_name == "map_style":
        state.layout["mapbox"]["style"] = state.map_style
        state.layout = {**state.layout, "mapbox": {**state.layout.get("mapbox", {})}}
    elif var_name == "selected_points":
        _update_selected_values(state)

# ---------- Style ----------
chart_style = {"width": "100%", "height": "80vh"}

# ---------- Pagina ----------
page = """
# Interactieve kaart: klik op een meetpunt en kies één of meerdere stoffen

**Zoek meetpunt (MeetobjectCode):** <|{zoek_meetpunt}|input|label=MeetobjectCode|placeholder=Bijv. MO-123|> <|Zoeken|button|on_action=zoek_meetpunt_action|>
**Stoffen:** <|{gekozen_stoffen}|selector|lov={stof_cols}|multiple|dropdown|>
**Kaartstijl:** <|{map_style}|selector|lov={['open-street-map','carto-positron','stamen-terrain','carto-darkmatter']}|dropdown|>

<|Reset kaart|button|on_action=reset_map_action|>  <|Download waarden|button|on_action=download_values_action|>

<|{df_stations}|chart|type=scattermapbox|mode=markers|lat=lat|lon=lon|text=text|marker={marker_dyn}|layout={layout}|selected={selected_points}|style={chart_style}|>

**Melding:** <|{status_msg}|text|md=True|>

### Geselecteerde waarde(n)
<|{selected_values_str}|text|md=True|>
"""

# ---------- Start ----------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", "10000"))  # Render gebruikt deze poort
    Gui(page).run(host="0.0.0.0", port=port, use_reloader=False, title="AC meetpunten dashboard")
