"""GUI styles, color constants, and theme configuration.

Defines the visual design system for the Smart Navigation application:
- Road type colors (for edge rendering on canvas)
- Node type colors and shapes
- POI category emoji/colors
- ttk theme configuration
"""

# ---------------------------------------------------------------------------
# Road type colors (for canvas edge rendering)
# ---------------------------------------------------------------------------
ROAD_COLORS = {
    "path": "#95a5a6",          # gray
    "main_road": "#3498db",     # blue
    "highway": "#e67e22",       # orange
    "one_way": "#e74c3c",       # red
    "walking": "#2ecc71",       # green
    "bus_lane": "#9b59b6",      # purple
    "subway": "#8e44ad",        # dark purple
    "train": "#795548",         # brown
}

ROAD_WIDTHS = {
    "path": 1,
    "main_road": 2,
    "highway": 3,
    "one_way": 2,
    "walking": 1,
    "bus_lane": 2,
    "subway": 2,
    "train": 3,
}

ROAD_DASH = {
    "path": (),
    "main_road": (),
    "highway": (),
    "one_way": (),
    "walking": (4, 4),          # dashed
    "bus_lane": (8, 3),         # dash-dot effect
    "subway": (2, 4),           # dotted
    "train": (10, 4),           # long dash
}

# ---------------------------------------------------------------------------
# Node type colors
# ---------------------------------------------------------------------------
NODE_COLORS = {
    "room": "#3498db",
    "corridor": "#bdc3c7",
    "stair": "#f39c12",
    "elevator": "#1abc9c",
    "entrance": "#27ae60",
    "poi": "#e91e63",
    "intersection": "#7f8c8d",
    "bus_stop": "#9b59b6",
    "subway_station": "#8e44ad",
    "train_station": "#795548",
    "parking": "#3498db",
    "hospital": "#e74c3c",
    "restaurant": "#e67e22",
    "scenic_spot": "#2ecc71",
}

NODE_RADIUS = {
    "room": 8,
    "corridor": 3,
    "stair": 6,
    "elevator": 6,
    "entrance": 7,
    "poi": 8,
    "intersection": 4,
    "bus_stop": 7,
    "subway_station": 7,
    "train_station": 8,
    "parking": 7,
    "hospital": 8,
    "restaurant": 7,
    "scenic_spot": 8,
}

# ---------------------------------------------------------------------------
# POI emoji/labels
# ---------------------------------------------------------------------------
POI_EMOJI = {
    "scenic": "🏛",
    "food": "🍽",
    "parking": "🅿",
    "hospital": "🏥",
}

POI_COLORS = {
    "scenic": "#2ecc71",
    "food": "#e67e22",
    "parking": "#3498db",
    "hospital": "#e74c3c",
}

# ---------------------------------------------------------------------------
# Path display colors
# ---------------------------------------------------------------------------
PATH_COLOR = "#f1c40f"          # gold — the found path
PATH_WIDTH = 3
START_COLOR = "#2ecc71"         # green
GOAL_COLOR = "#e74c3c"          # red
WAYPOINT_COLOR = "#f39c12"      # orange
VEHICLE_COLOR = "#e74c3c"       # red
CONGESTION_COLORS = {
    "normal": "#2ecc71",
    "moderate": "#f39c12",
    "heavy": "#e67e22",
    "blocked": "#e74c3c",
}

# ---------------------------------------------------------------------------
# Theme colors
# ---------------------------------------------------------------------------
BG_COLOR = "#1a1a2e"
PANEL_BG = "#16213e"
CANVAS_BG = "#0f0f23"
TEXT_COLOR = "#ecf0f1"
ACCENT_COLOR = "#3498db"
SUCCESS_COLOR = "#2ecc71"
WARNING_COLOR = "#f39c12"
DANGER_COLOR = "#e74c3c"

# ---------------------------------------------------------------------------
# Transport mode icons
# ---------------------------------------------------------------------------
MODE_EMOJI = {
    "driving": "🚗",
    "walking": "🚶",
    "bus": "🚌",
    "train": "🚄",
    "subway": "🚇",
}
