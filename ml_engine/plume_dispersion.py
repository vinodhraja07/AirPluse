"""
AirPulse AI - Gaussian Plume Dispersion & Atmospheric Advection Engine
Implements Pasquill-Gifford atmospheric dispersion equations to simulate
pollutant advection plumes, downwind footprint polygons, and downstream receptor exposure.
"""

import math
import numpy as np
from typing import Dict, Any, List, Tuple


class GaussianPlumeDispersionEngine:
    def __init__(self):
        # Pasquill-Gifford Dispersion Coefficients for Neutral/Slightly Stable Atmosphere (Class D/C)
        # sigma_y = a * x^b, sigma_z = c * x^d  (x in km, sigma in meters)
        self.a = 68.0
        self.b = 0.894
        self.c = 33.2
        self.d = 0.725

    def calculate_dispersion_footprint(
        self,
        source_lat: float,
        source_lon: float,
        source_pm25: float,
        wind_speed_ms: float,
        wind_dir_deg: float,
        stack_height_m: float = 15.0,
        max_distance_km: float = 8.0,
        all_stations: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Computes the physical Gaussian plume geometry and downwind concentration decay.
        Wind direction is where wind comes FROM; advection travels in (wind_dir + 180) % 360.
        """
        wind_speed = max(0.4, float(wind_speed_ms))
        advection_bearing_deg = (float(wind_dir_deg) + 180.0) % 360.0
        advection_rad = math.radians(advection_bearing_deg)

        # Emission rate proxy Q (proportional to measured concentration and source area)
        q_emission = max(10.0, float(source_pm25) * 45.0)

        # 1. Generate Plume Boundary Polygon (Left & Right expansion cones)
        distances_km = np.linspace(0.1, max_distance_km, 25)
        left_boundary = []
        right_boundary = []
        centerline_points = []
        centerline_concentrations = []

        # Conversion factor: 1 deg lat ~ 111.0 km, 1 deg lon ~ 111.0 * cos(lat) km
        km_per_lat = 111.0
        km_per_lon = 111.0 * math.cos(math.radians(source_lat))

        for x_km in distances_km:
            # Dispersion sigmas in meters
            sigma_y_m = self.a * (x_km ** self.b)
            sigma_z_m = self.c * (x_km ** self.d)

            # Ground level centerline concentration (y=0, z=0)
            # C = Q / (pi * u * sigma_y * sigma_z) * exp(-H^2 / (2 * sigma_z^2))
            c_ground = (q_emission / (math.pi * wind_speed * sigma_y_m * sigma_z_m)) * math.exp(
                -(stack_height_m ** 2) / (2.0 * (sigma_z_m ** 2))
            )
            centerline_concentrations.append(round(float(c_ground), 1))

            # Plume crosswind half-width (where concentration drops to 10% of centerline: y = 2.15 * sigma_y)
            half_width_km = (2.15 * sigma_y_m) / 1000.0

            # Centerline position
            dx_km = x_km * math.sin(advection_rad)
            dy_km = x_km * math.cos(advection_rad)

            center_lat = source_lat + (dy_km / km_per_lat)
            center_lon = source_lon + (dx_km / km_per_lon)
            centerline_points.append([round(center_lat, 5), round(center_lon, 5)])

            # Normal vector to advection direction for lateral boundary expansion
            normal_rad = advection_rad + math.pi / 2.0
            ndx_km = half_width_km * math.sin(normal_rad)
            ndy_km = half_width_km * math.cos(normal_rad)

            left_lat = center_lat + (ndy_km / km_per_lat)
            left_lon = center_lon + (ndx_km / km_per_lon)
            left_boundary.append([round(left_lat, 5), round(left_lon, 5)])

            right_lat = center_lat - (ndy_km / km_per_lat)
            right_lon = center_lon - (ndx_km / km_per_lon)
            right_boundary.append([round(right_lat, 5), round(right_lon, 5)])

        # Construct closed polygon: source -> left boundary forward -> right boundary backward -> source
        plume_polygon = [[round(source_lat, 5), round(source_lon, 5)]] + left_boundary + right_boundary[::-1] + [[round(source_lat, 5), round(source_lon, 5)]]

        # 2. Downwind Receptor Impact Analysis
        # Check which other urban stations lie in the active plume cone
        downwind_receptors = []
        if all_stations:
            for stn in all_stations:
                stn_lat = stn["lat"]
                stn_lon = stn["lon"]
                if abs(stn_lat - source_lat) < 1e-4 and abs(stn_lon - source_lon) < 1e-4:
                    continue # Skip source station itself

                # Vector from source to target
                dy_km = (stn_lat - source_lat) * km_per_lat
                dx_km = (stn_lon - source_lon) * km_per_lon
                dist_km = math.sqrt(dx_km**2 + dy_km**2)

                if dist_km > max_distance_km:
                    continue

                # Target bearing from source
                target_bearing_rad = math.atan2(dx_km, dy_km)
                angle_diff_deg = abs(math.degrees(target_bearing_rad - advection_rad)) % 360.0
                if angle_diff_deg > 180:
                    angle_diff_deg = 360.0 - angle_diff_deg

                # Check if inside plume half-angle
                sigma_y_m = self.a * (max(0.1, dist_km) ** self.b)
                plume_half_angle_deg = math.degrees(math.atan2((2.15 * sigma_y_m) / 1000.0, dist_km))

                if angle_diff_deg <= plume_half_angle_deg:
                    # In direct plume path!
                    y_crosswind_m = dist_km * 1000.0 * math.sin(math.radians(angle_diff_deg))
                    sigma_z_m = self.c * (max(0.1, dist_km) ** self.d)
                    conc_added = (q_emission / (math.pi * wind_speed * sigma_y_m * sigma_z_m)) * math.exp(
                        -(y_crosswind_m ** 2) / (2.0 * (sigma_y_m ** 2)) - (stack_height_m ** 2) / (2.0 * (sigma_z_m ** 2))
                    )
                    impact_pct = min(100.0, round((conc_added / max(source_pm25, 1.0)) * 100.0, 1))

                    downwind_receptors.append({
                        "station_id": stn["id"],
                        "station_name": stn["name"],
                        "distance_km": round(dist_km, 2),
                        "bearing_deg": round(math.degrees(target_bearing_rad) % 360.0, 1),
                        "estimated_influx_pm25": round(conc_added, 1),
                        "exposure_risk": "HIGH" if impact_pct > 30 else "MODERATE"
                    })

        return {
            "source_lat": source_lat,
            "source_lon": source_lon,
            "wind_speed_ms": wind_speed,
            "wind_direction_deg": wind_dir_deg,
            "advection_bearing_deg": round(advection_bearing_deg, 1),
            "max_reach_km": max_distance_km,
            "plume_polygon": plume_polygon,
            "centerline_path": centerline_points,
            "centerline_concentrations": centerline_concentrations,
            "downwind_receptors_at_risk": downwind_receptors
        }
