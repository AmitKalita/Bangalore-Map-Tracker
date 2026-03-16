"""
Bangalore Public Transport Route Finder
Finds the fastest route between two locations using Namma Metro and BMTC buses.
"""

import heapq
import math
import os
import time as time_module

import requests
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__, static_folder="static")

# ── Speed constants (km/h) ──────────────────────────────────────────
METRO_SPEED = 35
BUS_SPEED   = 15
WALK_SPEED  = 4

# ── Wait / overhead times (minutes) ────────────────────────────────
METRO_WAIT  = 4   # average wait at metro station
BUS_WAIT    = 8   # average wait at bus stop (half of ~15-min headway)
TRANSFER    = 3   # penalty for switching between metro and bus

# ── Maximum walking distance to board transit (km) ─────────────────
MAX_WALK_KM = 1.5


def haversine(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    R = 6371
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a  = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def walk_mins(dist_km):
    return (dist_km / WALK_SPEED) * 60


# ═══════════════════════════════════════════════════════════════════
# NAMMA METRO NETWORK DATA
# ═══════════════════════════════════════════════════════════════════

METRO_STATIONS = {}


def _s(sid, name, lat, lon, lines):
    METRO_STATIONS[sid] = {"id": sid, "name": name, "lat": lat, "lon": lon, "lines": lines}


# ── Purple Line ─────────────────────────────────────────────────────
# Phase 2 West extension
_s("challaghatta",          "Challaghatta",                12.9104, 77.4687, ["purple"])
_s("kengeri",               "Kengeri",                     12.9197, 77.4794, ["purple"])
_s("kengeri_bus_terminal",  "Kengeri Bus Terminal",         12.9278, 77.4882, ["purple"])
_s("udayagiri",             "Udayagiri",                   12.9348, 77.4990, ["purple"])
_s("pantharapalya",         "Pantharapalya",               12.9425, 77.5081, ["purple"])
# Phase 1 West
_s("mysuru_road",           "Mysuru Road",                 12.9488, 77.5161, ["purple"])
_s("deepanjali_nagar",      "Deepanjali Nagar",            12.9567, 77.5234, ["purple"])
_s("attiguppe",             "Attiguppe",                   12.9638, 77.5316, ["purple"])
_s("vijayanagar",           "Vijayanagar",                 12.9699, 77.5397, ["purple"])
_s("magadi_road",           "Magadi Road",                 12.9742, 77.5506, ["purple"])
_s("city_railway_station",  "City Railway Station",        12.9773, 77.5607, ["purple"])
# Interchange (both lines)
_s("majestic",              "Majestic (KSR Bengaluru)",    12.9767, 77.5713, ["purple", "green"])
# Phase 1 East
_s("sir_m_visvesvaraya",    "Sir M Visvesvaraya",          12.9766, 77.5754, ["purple"])
_s("vidhana_soudha",        "Vidhana Soudha",              12.9784, 77.5900, ["purple"])
_s("cubbon_park",           "Cubbon Park",                 12.9762, 77.5967, ["purple"])
_s("mg_road",               "MG Road",                     12.9759, 77.6062, ["purple"])
_s("trinity",               "Trinity",                     12.9735, 77.6168, ["purple"])
_s("halasuru",              "Halasuru",                    12.9760, 77.6256, ["purple"])
_s("indiranagar",           "Indiranagar",                 12.9784, 77.6408, ["purple"])
_s("swami_vivekananda_road","Swami Vivekananda Road",      12.9836, 77.6397, ["purple"])
_s("baiyappanahalli",       "Baiyappanahalli",             12.9857, 77.6488, ["purple"])
# Phase 2 East extension (Whitefield)
_s("seetharampalya",        "Seetharampalya",              12.9902, 77.6590, ["purple"])
_s("hoodi_junction",        "Hoodi Junction",              12.9941, 77.6694, ["purple"])
_s("garudacharpalya",       "Garudacharpalya",             13.0000, 77.6789, ["purple"])
_s("devasandra",            "Devasandra",                  13.0031, 77.6875, ["purple"])
_s("kr_puram",              "KR Puram",                    13.0050, 77.6954, ["purple"])
_s("benniganahalli",        "Benniganahalli",              13.0011, 77.7032, ["purple"])
_s("singayyanapalya",       "Singayyanapalya",             12.9975, 77.7106, ["purple"])
_s("hope_farm",             "Hope Farm (Whitefield)",      12.9909, 77.7166, ["purple"])
_s("kadugodi",              "Kadugodi",                    12.9855, 77.7243, ["purple"])
_s("pattandur_agrahara",    "Pattandur Agrahara",          12.9807, 77.7320, ["purple"])
_s("whitefield",            "Whitefield (Kadugodi)",       12.9748, 77.7451, ["purple"])

# ── Green Line ──────────────────────────────────────────────────────
# Phase 2 North extension
_s("biec",                  "BIEC",                        13.0556, 77.4960, ["green"])
# Phase 1 North
_s("nagasandra",            "Nagasandra",                  13.0488, 77.5197, ["green"])
_s("dasarahalli",           "Dasarahalli",                 13.0380, 77.5197, ["green"])
_s("jalahalli",             "Jalahalli",                   13.0276, 77.5190, ["green"])
_s("peenya_industry",       "Peenya Industry",             13.0251, 77.5249, ["green"])
_s("peenya",                "Peenya",                      13.0218, 77.5319, ["green"])
_s("goraguntepalya",        "Goraguntepalya",              13.0178, 77.5407, ["green"])
_s("yeshwanthpur",          "Yeshwanthpur",                13.0211, 77.5505, ["green"])
_s("sandal_soap_factory",   "Sandal Soap Factory",         13.0177, 77.5605, ["green"])
_s("mahalakshmi",           "Mahalakshmi",                 13.0074, 77.5678, ["green"])
_s("rajajinagar",           "Rajajinagar",                 12.9985, 77.5564, ["green"])
_s("kuvempu_road",          "Kuvempu Road",                12.9945, 77.5581, ["green"])
_s("srirampura",            "Srirampura",                  12.9885, 77.5608, ["green"])
_s("sampige_road",          "Sampige Road",                12.9855, 77.5686, ["green"])
# majestic is shared above
# Phase 1 South
_s("chickpete",             "Chickpete",                   12.9695, 77.5727, ["green"])
_s("kr_market",             "Krishna Rajendra Market",     12.9657, 77.5760, ["green"])
_s("national_college",      "National College",            12.9614, 77.5809, ["green"])
_s("lalbagh",               "Lalbagh",                     12.9527, 77.5840, ["green"])
_s("south_end_circle",      "South End Circle",            12.9467, 77.5826, ["green"])
_s("jayanagar",             "Jayanagar",                   12.9395, 77.5829, ["green"])
_s("rv_road",               "RV Road",                     12.9338, 77.5855, ["green"])
_s("banashankari",          "Banashankari",                12.9274, 77.5892, ["green"])
_s("jp_nagar",              "JP Nagar",                    12.9132, 77.5850, ["green"])
_s("yelachenahalli",        "Yelachenahalli",              12.8994, 77.5792, ["green"])
# Phase 2 South extension
_s("konanakunte_cross",     "Konanakunte Cross",           12.8874, 77.5763, ["green"])
_s("doddakallasandra",      "Doddakallasandra",            12.8782, 77.5723, ["green"])
_s("vajrahalli",            "Vajrahalli",                  12.8636, 77.5654, ["green"])
_s("thalaghattapura",       "Thalaghattapura",             12.8530, 77.5584, ["green"])
_s("silk_institute",        "Silk Institute (Anjanapura)", 12.8418, 77.5512, ["green"])


METRO_EDGES = [
    # Purple Line – West ↔ East (travel time in minutes)
    ("challaghatta",         "kengeri",              3),
    ("kengeri",              "kengeri_bus_terminal", 2),
    ("kengeri_bus_terminal", "udayagiri",            3),
    ("udayagiri",            "pantharapalya",        3),
    ("pantharapalya",        "mysuru_road",          3),
    ("mysuru_road",          "deepanjali_nagar",     3),
    ("deepanjali_nagar",     "attiguppe",            3),
    ("attiguppe",            "vijayanagar",          2),
    ("vijayanagar",          "magadi_road",          3),
    ("magadi_road",          "city_railway_station", 3),
    ("city_railway_station", "majestic",             2),
    ("majestic",             "sir_m_visvesvaraya",   2),
    ("sir_m_visvesvaraya",   "vidhana_soudha",       3),
    ("vidhana_soudha",       "cubbon_park",          2),
    ("cubbon_park",          "mg_road",              2),
    ("mg_road",              "trinity",              2),
    ("trinity",              "halasuru",             2),
    ("halasuru",             "indiranagar",          3),
    ("indiranagar",          "swami_vivekananda_road", 2),
    ("swami_vivekananda_road","baiyappanahalli",     3),
    ("baiyappanahalli",      "seetharampalya",       3),
    ("seetharampalya",       "hoodi_junction",       3),
    ("hoodi_junction",       "garudacharpalya",      2),
    ("garudacharpalya",      "devasandra",           2),
    ("devasandra",           "kr_puram",             2),
    ("kr_puram",             "benniganahalli",       2),
    ("benniganahalli",       "singayyanapalya",      2),
    ("singayyanapalya",      "hope_farm",            2),
    ("hope_farm",            "kadugodi",             3),
    ("kadugodi",             "pattandur_agrahara",   2),
    ("pattandur_agrahara",   "whitefield",           3),
    # Green Line – North ↔ South
    ("biec",                 "nagasandra",           5),
    ("nagasandra",           "dasarahalli",          3),
    ("dasarahalli",          "jalahalli",            3),
    ("jalahalli",            "peenya_industry",      2),
    ("peenya_industry",      "peenya",               2),
    ("peenya",               "goraguntepalya",       2),
    ("goraguntepalya",       "yeshwanthpur",         2),
    ("yeshwanthpur",         "sandal_soap_factory",  3),
    ("sandal_soap_factory",  "mahalakshmi",          3),
    ("mahalakshmi",          "rajajinagar",          3),
    ("rajajinagar",          "kuvempu_road",         2),
    ("kuvempu_road",         "srirampura",           2),
    ("srirampura",           "sampige_road",         2),
    ("sampige_road",         "majestic",             3),
    ("majestic",             "chickpete",            2),
    ("chickpete",            "kr_market",            2),
    ("kr_market",            "national_college",     2),
    ("national_college",     "lalbagh",              3),
    ("lalbagh",              "south_end_circle",     2),
    ("south_end_circle",     "jayanagar",            2),
    ("jayanagar",            "rv_road",              2),
    ("rv_road",              "banashankari",         3),
    ("banashankari",         "jp_nagar",             4),
    ("jp_nagar",             "yelachenahalli",       4),
    ("yelachenahalli",       "konanakunte_cross",    3),
    ("konanakunte_cross",    "doddakallasandra",     3),
    ("doddakallasandra",     "vajrahalli",           4),
    ("vajrahalli",           "thalaghattapura",      4),
    ("thalaghattapura",      "silk_institute",       4),
]


# ═══════════════════════════════════════════════════════════════════
# BMTC BUS ROUTES
# ═══════════════════════════════════════════════════════════════════

BUS_ROUTES = [
    {
        "id": "500C", "name": "BMTC 500C", "freq": 20,
        "stops": [
            {"name": "Majestic",          "lat": 12.9767, "lon": 77.5713},
            {"name": "Richmond Circle",   "lat": 12.9620, "lon": 77.5988},
            {"name": "Domlur",            "lat": 12.9609, "lon": 77.6390},
            {"name": "Marathahalli",      "lat": 12.9591, "lon": 77.7009},
            {"name": "Whitefield",        "lat": 12.9748, "lon": 77.7451},
        ],
    },
    {
        "id": "335E", "name": "BMTC 335E", "freq": 15,
        "stops": [
            {"name": "Shivajinagar",         "lat": 12.9856, "lon": 77.6012},
            {"name": "Domlur Junction",      "lat": 12.9609, "lon": 77.6390},
            {"name": "Ejipura",              "lat": 12.9457, "lon": 77.6199},
            {"name": "Koramangala",          "lat": 12.9352, "lon": 77.6245},
            {"name": "Silk Board",           "lat": 12.9172, "lon": 77.6225},
            {"name": "Electronic City Ph 1", "lat": 12.8445, "lon": 77.6645},
            {"name": "Electronic City Ph 2", "lat": 12.8350, "lon": 77.6720},
        ],
    },
    {
        "id": "201R", "name": "BMTC 201R", "freq": 10,
        "stops": [
            {"name": "Majestic",   "lat": 12.9767, "lon": 77.5713},
            {"name": "Hebbal",     "lat": 13.0358, "lon": 77.5972},
            {"name": "Yelahanka",  "lat": 13.1007, "lon": 77.5963},
        ],
    },
    {
        "id": "400GA", "name": "BMTC 400GA", "freq": 25,
        "stops": [
            {"name": "Majestic",         "lat": 12.9767, "lon": 77.5713},
            {"name": "Lalbagh",          "lat": 12.9527, "lon": 77.5840},
            {"name": "Jayanagar 4T",     "lat": 12.9308, "lon": 77.5830},
            {"name": "Bannerghatta Rd",  "lat": 12.8990, "lon": 77.5998},
            {"name": "Bannerghatta",     "lat": 12.8100, "lon": 77.5800},
        ],
    },
    {
        "id": "V2", "name": "BMTC V2 (Vajra – Airport)", "freq": 30,
        "stops": [
            {"name": "Kempegowda Int'l Airport", "lat": 13.1986, "lon": 77.7066},
            {"name": "Hebbal Flyover",            "lat": 13.0358, "lon": 77.5972},
            {"name": "Mehkri Circle",             "lat": 13.0031, "lon": 77.5811},
            {"name": "MG Road",                   "lat": 12.9759, "lon": 77.6062},
            {"name": "Majestic",                  "lat": 12.9767, "lon": 77.5713},
        ],
    },
    {
        "id": "356F", "name": "BMTC 356F", "freq": 20,
        "stops": [
            {"name": "Shivajinagar", "lat": 12.9856, "lon": 77.6012},
            {"name": "Koramangala",  "lat": 12.9352, "lon": 77.6245},
            {"name": "HSR Layout",   "lat": 12.9121, "lon": 77.6465},
            {"name": "Sarjapur",     "lat": 12.8679, "lon": 77.6712},
        ],
    },
    {
        "id": "G5", "name": "BMTC G5", "freq": 15,
        "stops": [
            {"name": "Majestic",        "lat": 12.9767, "lon": 77.5713},
            {"name": "Yeshwanthpur",    "lat": 13.0211, "lon": 77.5505},
            {"name": "Peenya",          "lat": 13.0218, "lon": 77.5319},
            {"name": "Tumkur Road",     "lat": 13.0500, "lon": 77.5100},
        ],
    },
    {
        "id": "KBS_ITPL", "name": "BMTC KBS–ITPL", "freq": 15,
        "stops": [
            {"name": "Kempegowda Bus Station", "lat": 12.9767, "lon": 77.5713},
            {"name": "Shivajinagar",           "lat": 12.9856, "lon": 77.6012},
            {"name": "Tin Factory",            "lat": 12.9994, "lon": 77.6484},
            {"name": "ITPL",                   "lat": 12.9814, "lon": 77.7261},
        ],
    },
    {
        "id": "BTM_WF", "name": "BMTC BTM–Whitefield", "freq": 25,
        "stops": [
            {"name": "BTM Layout",   "lat": 12.9122, "lon": 77.6117},
            {"name": "Koramangala",  "lat": 12.9352, "lon": 77.6245},
            {"name": "Domlur",       "lat": 12.9609, "lon": 77.6390},
            {"name": "Marathahalli", "lat": 12.9591, "lon": 77.7009},
            {"name": "Whitefield",   "lat": 12.9748, "lon": 77.7451},
        ],
    },
    {
        "id": "500K", "name": "BMTC 500K", "freq": 20,
        "stops": [
            {"name": "Kempegowda Bus Station", "lat": 12.9767, "lon": 77.5713},
            {"name": "HAL Airport Road",       "lat": 12.9666, "lon": 77.6506},
            {"name": "Marathahalli",           "lat": 12.9591, "lon": 77.7009},
            {"name": "Kundalahalli Gate",      "lat": 12.9726, "lon": 77.7129},
            {"name": "Whitefield",             "lat": 12.9748, "lon": 77.7451},
        ],
    },
]


# ═══════════════════════════════════════════════════════════════════
# GRAPH BUILDING + DIJKSTRA
# ═══════════════════════════════════════════════════════════════════

def _get_metro_line(s1, s2):
    """Return the shared metro line between two adjacent stations."""
    l1 = set(METRO_STATIONS[s1]["lines"])
    l2 = set(METRO_STATIONS[s2]["lines"])
    common = l1 & l2
    return list(common)[0] if common else "purple"


def build_graph(slat, slon, elat, elon):
    """
    Build a weighted directed graph. Returns (adj, nodes) where:
      adj[node_id]  -> list of edge dicts
      nodes[node_id] -> info dict with lat/lon/name/type
    """
    nodes = {}
    adj   = {}

    def add_node(nid, info):
        nodes[nid] = info
        adj.setdefault(nid, [])

    def add_edge(frm, to, time_mins, mode, **kw):
        adj[frm].append({"to": to, "time": time_mins, "mode": mode, **kw})

    # ── Metro stations ────────────────────────────────────────────
    for sid, st in METRO_STATIONS.items():
        add_node(sid, {"lat": st["lat"], "lon": st["lon"],
                       "name": st["name"], "type": "metro", "lines": st["lines"]})

    for s1, s2, t in METRO_EDGES:
        line = _get_metro_line(s1, s2)
        add_edge(s1, s2, t, "metro", line=line,
                 from_name=METRO_STATIONS[s1]["name"],
                 to_name=METRO_STATIONS[s2]["name"])
        add_edge(s2, s1, t, "metro", line=line,
                 from_name=METRO_STATIONS[s2]["name"],
                 to_name=METRO_STATIONS[s1]["name"])

    # ── Bus stops ─────────────────────────────────────────────────
    for route in BUS_ROUTES:
        stops = route["stops"]
        for i, stop in enumerate(stops):
            nid = f"bus_{route['id']}_{i}"
            add_node(nid, {"lat": stop["lat"], "lon": stop["lon"],
                           "name": stop["name"], "type": "bus",
                           "route": route["name"], "freq": route["freq"]})
            if i > 0:
                prev_nid = f"bus_{route['id']}_{i-1}"
                prev_stop = stops[i - 1]
                dist = haversine(prev_stop["lat"], prev_stop["lon"],
                                 stop["lat"], stop["lon"])
                t = (dist / BUS_SPEED) * 60
                add_edge(prev_nid, nid, t, "bus",
                         route=route["name"], route_id=route["id"],
                         from_name=prev_stop["name"], to_name=stop["name"])
                add_edge(nid, prev_nid, t, "bus",
                         route=route["name"], route_id=route["id"],
                         from_name=stop["name"], to_name=prev_stop["name"])

    # ── Virtual start / end ───────────────────────────────────────
    add_node("__start__", {"lat": slat, "lon": slon, "name": "Your start", "type": "virtual"})
    add_node("__end__",   {"lat": elat, "lon": elon, "name": "Destination", "type": "virtual"})

    # Walking from start → transit + direct end
    for nid, nd in list(nodes.items()):
        if nid in ("__start__", "__end__"):
            continue
        # start → node
        d = haversine(slat, slon, nd["lat"], nd["lon"])
        if d <= MAX_WALK_KM:
            wait = METRO_WAIT if nd["type"] == "metro" else nd.get("freq", BUS_WAIT) / 2
            add_edge("__start__", nid, walk_mins(d) + wait, "walk",
                     dist_km=round(d, 2),
                     from_name="Your starting point", to_name=nd["name"])
        # node → end
        d2 = haversine(nd["lat"], nd["lon"], elat, elon)
        if d2 <= MAX_WALK_KM:
            add_edge(nid, "__end__", walk_mins(d2), "walk",
                     dist_km=round(d2, 2),
                     from_name=nd["name"], to_name="Your destination")

    # Direct walking start → end
    d_direct = haversine(slat, slon, elat, elon)
    add_edge("__start__", "__end__", walk_mins(d_direct), "walk",
             dist_km=round(d_direct, 2),
             from_name="Your starting point", to_name="Your destination")

    # Walking between nearby transit nodes (transfers within 400 m)
    transit_nodes = [(nid, nd) for nid, nd in nodes.items()
                     if nd["type"] in ("metro", "bus")]
    for i in range(len(transit_nodes)):
        nid1, nd1 = transit_nodes[i]
        for j in range(i + 1, len(transit_nodes)):
            nid2, nd2 = transit_nodes[j]
            d = haversine(nd1["lat"], nd1["lon"], nd2["lat"], nd2["lon"])
            if 0 < d <= 0.4:
                wait2 = METRO_WAIT if nd2["type"] == "metro" else nd2.get("freq", BUS_WAIT) / 2
                wait1 = METRO_WAIT if nd1["type"] == "metro" else nd1.get("freq", BUS_WAIT) / 2
                add_edge(nid1, nid2, walk_mins(d) + wait2, "walk",
                         dist_km=round(d, 2),
                         from_name=nd1["name"], to_name=nd2["name"])
                add_edge(nid2, nid1, walk_mins(d) + wait1, "walk",
                         dist_km=round(d, 2),
                         from_name=nd2["name"], to_name=nd1["name"])

    return adj, nodes


def dijkstra(adj, nodes, start, end):
    """
    Returns (total_minutes, path_edges) or (None, None).
    State = (node_id, last_mode) to correctly apply transfer penalties.
    """
    INF = float("inf")
    best   = {}   # (node, mode) -> best time
    prev   = {}   # (node, mode) -> ((prev_node, prev_mode), edge)

    init_state = (start, "none")
    best[init_state] = 0.0
    # heap: (time, counter, node, mode)
    heap = [(0.0, 0, start, "none")]
    ctr  = 1

    while heap:
        t, _, node, mode = heapq.heappop(heap)
        state = (node, mode)

        if best.get(state, INF) < t:
            continue

        if node == end:
            # Reconstruct
            path = []
            cur = state
            while cur in prev:
                pstate, edge = prev[cur]
                path.append(edge)
                cur = pstate
            path.reverse()
            return t, path

        for edge in adj.get(node, []):
            nxt   = edge["to"]
            emode = edge["mode"]
            # Transfer penalty when switching between metro and bus
            penalty = 0.0
            if mode not in ("none", "walk") and emode not in ("none", "walk") and mode != emode:
                penalty = TRANSFER

            nt = t + edge["time"] + penalty
            nstate = (nxt, emode)

            if nt < best.get(nstate, INF):
                best[nstate]  = nt
                prev[nstate]  = (state, {**edge, "penalty": penalty})
                heapq.heappush(heap, (nt, ctr, nxt, emode))
                ctr += 1

    return None, None


# ═══════════════════════════════════════════════════════════════════
# ROUTE FORMATTING
# ═══════════════════════════════════════════════════════════════════

def _fmt_mins(m):
    m = round(m)
    if m < 60:
        return f"{m} min"
    return f"{m // 60} hr {m % 60} min"


def format_route(total_mins, path_edges, nodes, slat, slon, elat, elon):
    """Merge consecutive edges of same mode+line into steps."""
    if not path_edges:
        return None

    steps     = []
    segments  = []   # for map polylines: [{mode, color, coords:[{lat,lon}]}]
    MODE_COLOR = {"metro_purple": "#9B59B6", "metro_green": "#27AE60",
                  "bus": "#2980B9", "walk": "#7F8C8D"}

    def flush(buf):
        if not buf:
            return
        mode = buf[0]["mode"]
        first, last = buf[0], buf[-1]
        coords = []
        for e in buf:
            fn = e.get("from_name", "")
            tn = e.get("to_name", "")
            fn_node = e.get("from_node_id", "")
            tn_node = e.get("to_node_id", "")
            if fn_node in nodes:
                coords.append({"lat": nodes[fn_node]["lat"], "lon": nodes[fn_node]["lon"]})
            if tn_node in nodes:
                coords.append({"lat": nodes[tn_node]["lat"], "lon": nodes[tn_node]["lon"]})

        seg_time = sum(e["time"] for e in buf) + sum(e.get("penalty", 0) for e in buf)

        if mode == "metro":
            line      = first.get("line", "purple")
            color_key = f"metro_{line}"
            color     = MODE_COLOR.get(color_key, "#9B59B6")
            stops_n   = len(buf)
            steps.append({
                "mode": "metro", "line": line.capitalize(), "color": color,
                "instruction": (f"Take {line.capitalize()} Line metro from "
                                f"{first['from_name']} to {last['to_name']} "
                                f"({stops_n} stop{'s' if stops_n > 1 else ''})"),
                "time": round(seg_time),
                "from": first["from_name"], "to": last["to_name"],
                "stops": stops_n,
            })
        elif mode == "bus":
            color = MODE_COLOR["bus"]
            steps.append({
                "mode": "bus", "color": color,
                "route": first.get("route", "Bus"),
                "instruction": (f"Take {first.get('route','Bus')} from "
                                f"{first['from_name']} to {last['to_name']}"),
                "time": round(seg_time),
                "from": first["from_name"], "to": last["to_name"],
            })
        else:  # walk
            dist = sum(e.get("dist_km", 0) for e in buf)
            color = MODE_COLOR["walk"]
            steps.append({
                "mode": "walk", "color": color,
                "instruction": (f"Walk {round(dist * 1000)} m from "
                                f"{first['from_name']} to {last['to_name']}"),
                "time": round(seg_time),
                "dist_m": round(dist * 1000),
                "from": first["from_name"], "to": last["to_name"],
            })

        segments.append({"mode": mode, "color": color, "coords": coords})

    buf = []
    for edge in path_edges:
        # tag from/to node IDs
        if buf and (buf[-1]["mode"] != edge["mode"] or
                    buf[-1].get("line") != edge.get("line") or
                    buf[-1].get("route_id") != edge.get("route_id")):
            flush(buf)
            buf = []
        buf.append(edge)
    flush(buf)

    modes_used = list(dict.fromkeys(s["mode"] for s in steps))

    return {
        "total_time":    round(total_mins),
        "total_time_fmt": _fmt_mins(total_mins),
        "steps":         steps,
        "segments":      segments,
        "modes_used":    modes_used,
        "start":         {"lat": slat, "lon": slon},
        "end":           {"lat": elat, "lon": elon},
    }


# ═══════════════════════════════════════════════════════════════════
# GEOCODING  (OpenStreetMap Nominatim)
# ═══════════════════════════════════════════════════════════════════

_geo_cache = {}


def geocode(query):
    key = query.lower().strip()
    if key in _geo_cache:
        return _geo_cache[key]

    url    = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": f"{query}, Bangalore, Karnataka, India",
        "format": "json",
        "limit": 1,
        "viewbox": "77.4,13.2,77.8,12.8",
        "bounded": 1,
    }
    headers = {"User-Agent": "BangaloreRouteFinderApp/1.0"}

    try:
        resp = requests.get(url, params=params, headers=headers, timeout=8)
        data = resp.json()
        if data:
            result = {"lat": float(data[0]["lat"]), "lon": float(data[0]["lon"]),
                      "display_name": data[0]["display_name"]}
            _geo_cache[key] = result
            return result
    except Exception:
        pass

    return None


# ═══════════════════════════════════════════════════════════════════
# FLASK ROUTES
# ═══════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory("static", filename)


@app.route("/api/stations")
def api_stations():
    return jsonify(list(METRO_STATIONS.values()))


@app.route("/api/geocode")
def api_geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query"}), 400
    result = geocode(q)
    if result:
        return jsonify(result)
    return jsonify({"error": "Location not found"}), 404


@app.route("/api/route", methods=["POST"])
def api_route():
    body  = request.get_json(force=True)
    start = body.get("start", "").strip()
    end   = body.get("end", "").strip()

    if not start or not end:
        return jsonify({"error": "Please provide both start and end locations."}), 400

    # Geocode
    sg = geocode(start)
    if not sg:
        return jsonify({"error": f"Could not find '{start}' in Bangalore."}), 404
    eg = geocode(end)
    if not eg:
        return jsonify({"error": f"Could not find '{end}' in Bangalore."}), 404

    slat, slon = sg["lat"], sg["lon"]
    elat, elon = eg["lat"], eg["lon"]

    # Avoid duplicate geocode hits
    time_module.sleep(0.1)

    adj, nodes = build_graph(slat, slon, elat, elon)

    # Tag each edge with its from/to node IDs (needed for coordinates)
    for nid in list(adj.keys()):
        for edge in adj[nid]:
            edge["from_node_id"] = nid
            edge["to_node_id"]   = edge["to"]

    total_mins, path = dijkstra(adj, nodes, "__start__", "__end__")

    if total_mins is None:
        return jsonify({"error": "No public-transport route found between these locations."}), 404

    route = format_route(total_mins, path, nodes, slat, slon, elat, elon)
    route["start_name"] = sg.get("display_name", start).split(",")[0]
    route["end_name"]   = eg.get("display_name", end).split(",")[0]

    return jsonify(route)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
