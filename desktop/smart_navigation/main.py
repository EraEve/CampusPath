"""Smart Navigation (智慧导航) — Application bootstrap.

Initializes the core services and launches the tkinter GUI.
"""

import sys
import os


def main():
    """Launch the Smart Navigation application."""
    # Lazy imports so --help / version checks are fast
    from .core.map_manager import MapManager
    from .services.path_service import PathService
    from .services.search_service import SearchService
    from .services.traffic_service import TrafficService
    from .services.vehicle_service import VehicleService
    from .services.navigation_service import NavigationService
    from .gui_wx.app_window import AppWindow

    # Initialize services
    map_manager = MapManager()
    path_service = PathService()
    search_service = SearchService()
    traffic_service = TrafficService()
    vehicle_service = VehicleService()
    navigation_service = NavigationService()

    # Load demo maps
    try:
        map_manager.load_all_demo_maps()
    except Exception as e:
        print(f"Warning: some maps failed to load: {e}")

    if not map_manager.list_scenes():
        print("Error: No maps loaded. Check data/maps/ directory.")
        return 1

    # Launch GUI
    app = AppWindow(
        map_manager=map_manager,
        path_service=path_service,
        search_service=search_service,
        traffic_service=traffic_service,
        vehicle_service=vehicle_service,
        navigation_service=navigation_service,
    )
    app.run()

    return 0


if __name__ == "__main__":
    sys.exit(main())
