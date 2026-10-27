/**
 * AirPulse AI — Interactive Spatial GIS Map (Leaflet.js)
 * Visualizes 42 Pan-India Urban Monitoring Stations, Live Geolocation GPS,
 * Google Satellite Hybrid Mapping, Pasquill-Gifford Gaussian Plume Dispersion,
 * and Real-World Street & Highway Road Routing.
 */

let mapInstance = null;
let stationMarkers = {};
let stationCircles = {};
let activePlumePolygon = null;
let activeCenterline = null;
let userGpsMarker = null;
let userAccuracyCircle = null;
let currentStationsList = [];

let activeDirectPolyline = null;
let activeCleanPolyline = null;
let activeRouteMarkers = [];
let activeRouteBounds = null;

// Geodesic Haversine distance formula (in km)
function calculateHaversineDistance(lat1, lon1, lat2, lon2) {
  const R = 6371.0;
  const dLat = (lat2 - lat1) * Math.PI / 180.0;
  const dLon = (lon2 - lon1) * Math.PI / 180.0;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180.0) * Math.cos(lat2 * Math.PI / 180.0) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Fetch exact real-world road geometry from OSRM driving engine
 */
async function fetchRoadGeometry(lon1, lat1, lon2, lat2, midLon = null, midLat = null) {
  let url = `https://router.project-osrm.org/route/v1/driving/${lon1},${lat1};${lon2},${lat2}?overview=full&geometries=geojson`;
  if (midLon !== null && midLat !== null) {
    url = `https://router.project-osrm.org/route/v1/driving/${lon1},${lat1};${midLon},${midLat};${lon2},${lat2}?overview=full&geometries=geojson`;
  }
  try {
    const res = await fetch(url, { signal: AbortSignal.timeout(5000) });
    if (!res.ok) throw new Error('OSRM network response error');
    const data = await res.json();
    if (data.routes && data.routes.length > 0) {
      const coords = data.routes[0].geometry.coordinates;
      // Convert [lon, lat] from GeoJSON to [lat, lon] for Leaflet
      return coords.map(c => [c[1], c[0]]);
    }
  } catch (err) {
    console.warn('OSRM direct road fetch notice:', err.message);
  }
  return null;
}

/**
 * Generates curved road-following spline coordinates if OSRM is unreachable
 */
function generateCurvedRoadPath(start, end, curvatureOffset = 0.02) {
  const points = [];
  const steps = 30;
  const lat1 = start[0], lon1 = start[1];
  const lat2 = end[0], lon2 = end[1];

  const midLat = (lat1 + lat2) / 2 + curvatureOffset;
  const midLon = (lon1 + lon2) / 2 - curvatureOffset * 0.7;

  for (let i = 0; i <= steps; i++) {
    const t = i / steps;
    // Quadratic Bezier Curve interpolation
    const lat = (1 - t) * (1 - t) * lat1 + 2 * (1 - t) * t * midLat + t * t * lat2;
    const lon = (1 - t) * (1 - t) * lon1 + 2 * (1 - t) * t * midLon + t * t * lon2;
    points.push([lat, lon]);
  }
  return points;
}

function initMap(stations) {
  currentStationsList = stations || [];
  if (!stations || stations.length === 0) return;

  const mapContainer = document.getElementById('map');
  if (!mapContainer) return;

  if (mapInstance) {
    mapInstance.remove();
  }

  // Default focus on active/first station (e.g. Delhi NCR)
  const initialLat = stations[0].lat || 28.6469;
  const initialLon = stations[0].lon || 77.3160;

  mapInstance = L.map('map', {
    center: [initialLat, initialLon],
    zoom: 11,
    zoomControl: true,
    attributionControl: true
  });

  // 1. Google Default Roads & Streets Map (Default Layer)
  const defaultRoadMap = L.tileLayer(
    'https://mt{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}',
    {
      maxZoom: 20,
      subdomains: ['0', '1', '2', '3'],
      attribution: '&copy; Google Maps Roads | AirPulse AI'
    }
  );

  // 2. Satellite (Google Hybrid: Satellite Imagery + Roads & City Labels)
  const satelliteMap = L.tileLayer(
    'https://mt{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    {
      maxZoom: 20,
      subdomains: ['0', '1', '2', '3'],
      attribution: '&copy; Google Maps Satellite | AirPulse AI'
    }
  );

  // 3. Terrain
  const terrainMap = L.tileLayer(
    'https://mt{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}',
    {
      maxZoom: 20,
      subdomains: ['0', '1', '2', '3'],
      attribution: '&copy; Google Maps Terrain | AirPulse AI'
    }
  );

  // Add Default Road Map by default
  defaultRoadMap.addTo(mapInstance);

  // Add Interactive Layer Switcher: Default, Satellite, Terrain
  L.control.layers(
    {
      '🗺️ Default': defaultRoadMap,
      '🛰️ Satellite': satelliteMap,
      '⛰️ Terrain': terrainMap
    },
    {},
    { position: 'topright', collapsed: false }
  ).addTo(mapInstance);

  stationMarkers = {};
  stationCircles = {};

  stations.forEach(stn => {
    const aqi = stn.aqi_summary ? stn.aqi_summary.aqi : 100;
    const color = stn.aqi_summary ? stn.aqi_summary.color_hex : '#F97316';
    const category = stn.aqi_summary ? stn.aqi_summary.category : 'Moderate';
    const dominant = stn.aqi_summary ? stn.aqi_summary.dominant_pollutant : 'PM2.5';
    const readings = stn.current_readings || {};

    // Custom HTML Pin Marker with Outer Glow
    const iconHtml = `
      <div class="custom-station-pin" style="background: ${color}; color: #FFF; box-shadow: 0 0 16px ${color}AA;" title="${stn.name}">
        <span>${Math.round(aqi)}</span>
      </div>
    `;

    const customIcon = L.divIcon({
      className: 'station-div-icon',
      html: iconHtml,
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -20]
    });

    const marker = L.marker([stn.lat, stn.lon], { icon: customIcon }).addTo(mapInstance);

    // Dynamic Sensor Coverage Radius
    const circle = L.circle([stn.lat, stn.lon], {
      color: color,
      fillColor: color,
      fillOpacity: 0.08,
      weight: 1.5,
      dashArray: '4, 4',
      radius: (stn.coverage_radius_km || 4.5) * 1000
    }).addTo(mapInstance);

    // Enhanced Glassmorphic Popup Card
    const popupContent = `
      <div style="font-family: 'Inter', sans-serif; padding: 4px; min-width: 210px;">
        <div style="font-weight: 800; font-size: 0.95rem; color: #F8FAFC; margin-bottom: 2px;">${stn.name}</div>
        <div style="font-size: 0.74rem; color: #94A3B8; margin-bottom: 8px;">
          ${stn.id} • ${stn.city || 'India'} (${stn.state || ''}) • <span style="color: #06B6D4;">${stn.land_use}</span>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; background: rgba(255, 255, 255, 0.04); padding: 6px 10px; border-radius: 8px;">
          <span style="font-size: 1.35rem; font-weight: 800; color: ${color}; font-family: 'JetBrains Mono';">${Math.round(aqi)} <span style="font-size: 0.75rem;">AQI</span></span>
          <span style="font-size: 0.75rem; font-weight: 700; color: ${color};">${category}</span>
        </div>
        <div style="font-size: 0.74rem; color: #CBD5E1; line-height: 1.5;">
          <div>• Dominant: <strong style="color: #F8FAFC;">${dominant}</strong></div>
          <div>• Wind Speed: <strong style="color: #F8FAFC;">${readings.wind_speed || 2.0} m/s</strong></div>
          <div>• Temperature: <strong style="color: #F8FAFC;">${readings.temperature || 28.0} °C</strong></div>
        </div>
        <div style="margin-top: 8px; font-size: 0.7rem; color: #06B6D4; text-align: center; font-weight: 600;">
          Click marker to load full forecast & drivers
        </div>
      </div>
    `;

    marker.bindPopup(popupContent);
    marker.on('click', () => {
      const select = document.getElementById('stationSelect');
      if (select) {
        select.value = stn.id;
        window.dispatchEvent(new CustomEvent('stationChanged', { detail: { stationId: stn.id } }));
      }
    });

    stationMarkers[stn.id] = marker;
    stationCircles[stn.id] = circle;
  });

  // Setup GPS Button and All India Button listeners
  setupMapControlButtons();

  // Invalidate size after layout rendering
  setTimeout(() => {
    if (mapInstance) mapInstance.invalidateSize();
  }, 200);
}

function setupMapControlButtons() {
  const btnGps = document.getElementById('btnGpsLocate');
  if (btnGps) {
    btnGps.onclick = locateUserGps;
  }

  const btnAll = document.getElementById('btnAllIndia');
  if (btnAll) {
    btnAll.onclick = fitAllIndiaBounds;
  }
}

function fitAllIndiaBounds() {
  if (!mapInstance || currentStationsList.length === 0) return;
  const bounds = L.latLngBounds(currentStationsList.map(s => [s.lat, s.lon]));
  mapInstance.fitBounds(bounds, { padding: [30, 30], maxZoom: 12 });
}

function applyUserLocation(userLat, userLon, accuracy = 200, sourceLabel = 'Live GPS') {
  const banner = document.getElementById('gpsStatusBanner');
  const btnGps = document.getElementById('btnGpsLocate');
  if (btnGps) btnGps.innerHTML = `<span>📍</span> My Location (${sourceLabel})`;

  // Remove existing GPS layers
  if (userGpsMarker && mapInstance.hasLayer(userGpsMarker)) mapInstance.removeLayer(userGpsMarker);
  if (userAccuracyCircle && mapInstance.hasLayer(userAccuracyCircle)) mapInstance.removeLayer(userAccuracyCircle);

  // Create glowing user GPS Pin
  const gpsIcon = L.divIcon({
    className: 'user-gps-div-icon',
    html: `
      <div style="width: 22px; height: 22px; background: #06B6D4; border: 3px solid #FFF; border-radius: 50%; box-shadow: 0 0 18px #06B6D4; animation: pulse 1.8s infinite;"></div>
    `,
    iconSize: [22, 22],
    iconAnchor: [11, 11]
  });

  userGpsMarker = L.marker([userLat, userLon], { icon: gpsIcon, zIndexOffset: 2000 }).addTo(mapInstance);
  userGpsMarker.bindPopup(`
    <div style="font-family: 'Inter', sans-serif; padding: 4px;">
      <strong style="color: #06B6D4; font-size: 13px;">📍 You Are Here</strong>
      <div style="font-size: 11px; color: #CBD5E1; margin-top: 3px;"><strong>Coordinates:</strong> ${userLat.toFixed(4)}° N, ${userLon.toFixed(4)}° E</div>
      <div style="font-size: 11px; color: #94A3B8;">Source: ${sourceLabel} (±${Math.round(accuracy)}m)</div>
      <div style="font-size: 10.5px; color: #10B981; margin-top: 4px;">💡 Click anywhere on map to reposition pin</div>
    </div>
  `).openPopup();

  userAccuracyCircle = L.circle([userLat, userLon], {
    radius: Math.min(accuracy, 6000),
    color: '#06B6D4',
    fillColor: '#06B6D4',
    fillOpacity: 0.12,
    weight: 1.5
  }).addTo(mapInstance);

  // DIRECTLY FLY AND CENTER ON USER'S EXACT LOCATION
  mapInstance.flyTo([userLat, userLon], 14, { duration: 1.2 });

  // Find nearest station in India for background data context without moving map away
  if (currentStationsList.length > 0) {
    let nearestStation = null;
    let minDistance = Infinity;

    currentStationsList.forEach(stn => {
      const dist = calculateHaversineDistance(userLat, userLon, stn.lat, stn.lon);
      if (dist < minDistance) {
        minDistance = dist;
        nearestStation = stn;
      }
    });

    if (nearestStation) {
      const distStr = minDistance < 1.0 ? `${Math.round(minDistance * 1000)} meters` : `${minDistance.toFixed(1)} km`;

      if (banner) {
        banner.style.display = 'block';
        banner.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 6px;">
            <span>📍 <strong>Centered on Your Location:</strong> Lat ${userLat.toFixed(4)}°, Lon ${userLon.toFixed(4)}° (${sourceLabel})</span>
            <span style="color: #10B981; font-weight: 700;">Nearest Sensor: ${nearestStation.name} (${distStr} away)</span>
          </div>
        `;
      }

      // Update station telemetry in background without panning map away from user
      const select = document.getElementById('stationSelect');
      if (select && select.value !== nearestStation.id) {
        select.value = nearestStation.id;
        if (typeof loadStationData === 'function') {
          loadStationData(nearestStation.id);
        }
      }
    }
  }
}

async function locateUserGps() {
  const banner = document.getElementById('gpsStatusBanner');
  const btnGps = document.getElementById('btnGpsLocate');

  if (btnGps) btnGps.innerHTML = '<span>📍</span> Locating...';
  if (banner) {
    banner.style.display = 'block';
    banner.innerHTML = '<span style="color: var(--accent-cyan);"><span class="pulse-dot" style="display:inline-block; margin-right:6px;"></span> Requesting high-precision GPS positioning...</span>';
  }

  // Fallback network helper if hardware GPS is not available on desktop
  async function fallbackToIpLocation() {
    try {
      const res = await fetch('https://ipwho.is/');
      if (res.ok) {
        const d2 = await res.json();
        if (d2.latitude && d2.longitude) {
          applyUserLocation(d2.latitude, d2.longitude, 2500, d2.city ? `${d2.city} Area` : 'Network IP');
          return;
        }
      }
    } catch (_) {}

    try {
      const res2 = await fetch('/api/locate-ip');
      if (res2.ok) {
        const d = await res2.json();
        if (d.lat && d.lon) {
          applyUserLocation(d.lat, d.lon, 3000, d.city ? `${d.city} Area` : 'Network IP');
          return;
        }
      }
    } catch (_) {}

    if (banner) {
      banner.innerHTML = '<span style="color: #F59E0B;">GPS not detected. Click anywhere on the map to pinpoint your location.</span>';
    }
    if (btnGps) btnGps.innerHTML = '<span>📍</span> My GPS';
  }

  if (navigator.geolocation) {
    // 1. First attempt true high-accuracy GPS
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const userLat = position.coords.latitude;
        const userLon = position.coords.longitude;
        const accuracy = position.coords.accuracy || 20;
        applyUserLocation(userLat, userLon, accuracy, 'High-Accuracy GPS');
      },
      (err) => {
        console.warn('High-accuracy GPS returned notice, trying standard positioning:', err.message);
        // 2. Second attempt: standard device Wi-Fi positioning
        navigator.geolocation.getCurrentPosition(
          (pos2) => {
            applyUserLocation(pos2.coords.latitude, pos2.coords.longitude, pos2.coords.accuracy || 80, 'Device Location');
          },
          (err2) => {
            console.warn('Device location unavailable, attempting network geolocation:', err2.message);
            fallbackToIpLocation();
          },
          { enableHighAccuracy: false, timeout: 6000, maximumAge: 60000 }
        );
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  } else {
    fallbackToIpLocation();
  }
}

function renderPlumeOnMap(plumeData) {
  if (!mapInstance || !plumeData) return;

  // Remove existing plume layers
  if (activePlumePolygon) {
    mapInstance.removeLayer(activePlumePolygon);
    activePlumePolygon = null;
  }
  if (activeCenterline) {
    mapInstance.removeLayer(activeCenterline);
    activeCenterline = null;
  }

  const polyCoords = plumeData.plume_polygon;
  if (!polyCoords || polyCoords.length === 0) return;

  // Draw Gaussian Plume Polygon
  activePlumePolygon = L.polygon(polyCoords, {
    color: '#EF4444',
    weight: 1.5,
    dashArray: '3, 4',
    fillColor: '#EF4444',
    fillOpacity: 0.16
  }).addTo(mapInstance);

  // Draw Centerline Advection Vector
  if (plumeData.centerline_path && plumeData.centerline_path.length > 0) {
    activeCenterline = L.polyline(plumeData.centerline_path, {
      color: '#F59E0B',
      weight: 2.5,
      dashArray: '6, 6',
      opacity: 0.9
    }).addTo(mapInstance);
  }

  // Update Plume Info Bar
  const plumeInfoEl = document.getElementById('plumeInfo');
  if (plumeInfoEl) {
    const heading = plumeData.advection_bearing_deg;
    const speed = plumeData.wind_speed_ms;
    const receptors = plumeData.downwind_receptors_at_risk || [];

    let receptorText = '<span style="color: #10B981; font-weight: 600;">✓ No downstream monitoring zones in direct toxic path.</span>';
    if (receptors.length > 0) {
      receptorText = receptors.map(r =>
        `<strong style="color: #F87171;">⚠️ ${r.station_name}</strong> (${r.distance_km} km downwind, +${r.estimated_influx_pm25} µg/m³ influx)`
      ).join('; ');
    }

    plumeInfoEl.innerHTML = `
      <div style="background: rgba(239, 68, 68, 0.08); border: 1px solid rgba(239, 68, 68, 0.25); border-radius: var(--radius-sm); padding: 10px 14px; margin-top: 8px;">
        <div style="font-weight: 700; color: #F87171; font-size: 0.82rem; margin-bottom: 2px;">
          🌪️ Gaussian Plume Advection Footprint:
        </div>
        <div style="font-size: 0.75rem; color: #CBD5E1;">
          Wind carrying emissions toward bearing <strong style="color: #F8FAFC;">${heading}°</strong> at <strong style="color: #F8FAFC;">${speed} m/s</strong>.
        </div>
        <div style="margin-top: 4px; font-size: 0.74rem; color: #E2E8F0;">
          Downwind Impact: ${receptorText}
        </div>
      </div>
    `;
  }
}

/**
 * Renders Visual Clean-Air vs Direct Highway Routes on the Leaflet Map
 * Uses real-world road geometries from OSRM driving engine
 */
async function renderRouteOnMap(routeData) {
  if (!mapInstance || !routeData) return;

  // Clear previous route layers
  if (activeDirectPolyline) {
    mapInstance.removeLayer(activeDirectPolyline);
    activeDirectPolyline = null;
  }
  if (activeCleanPolyline) {
    mapInstance.removeLayer(activeCleanPolyline);
    activeCleanPolyline = null;
  }
  activeRouteMarkers.forEach(m => mapInstance.removeLayer(m));
  activeRouteMarkers = [];

  const direct = routeData.direct_route;
  const clean = routeData.clean_air_route;

  if (!direct || !clean) return;

  const directWaypoints = direct.waypoints || [];
  const cleanWaypoints = clean.waypoints || [];
  if (directWaypoints.length === 0) return;

  const startCoord = directWaypoints[0];
  const endCoord = directWaypoints[directWaypoints.length - 1];

  const startLat = startCoord[0], startLon = startCoord[1];
  const endLat = endCoord[0], endLon = endCoord[1];

  // Calculate clean bypass offset waypoint
  const midLat = (startLat + endLat) / 2.0;
  const midLon = (startLon + endLon) / 2.0;
  const cleanMidLat = midLat + 0.018;
  const cleanMidLon = midLon - 0.015;

  // 1. Fetch real-world road network paths from OSRM
  let directRoadCoords = await fetchRoadGeometry(startLon, startLat, endLon, endLat);
  let cleanRoadCoords = await fetchRoadGeometry(startLon, startLat, endLon, endLat, cleanMidLon, cleanMidLat);

  // Fallback to curved road splines if network OSRM is unreachable
  if (!directRoadCoords || directRoadCoords.length === 0) {
    directRoadCoords = generateCurvedRoadPath(startCoord, endCoord, 0.012);
  }
  if (!cleanRoadCoords || cleanRoadCoords.length === 0) {
    cleanRoadCoords = generateCurvedRoadPath(startCoord, endCoord, -0.024);
  }

  // 2. Draw Arterial Highway Road Route (Red)
  activeDirectPolyline = L.polyline(directRoadCoords, {
    color: '#EF4444',
    weight: 5.5,
    opacity: 0.92,
    dashArray: '8, 6'
  }).addTo(mapInstance);

  activeDirectPolyline.bindPopup(`
    <div style="font-family: 'Inter', sans-serif; padding: 4px;">
      <strong style="color: #EF4444;">🚗 Arterial Highway Route (High Traffic & Exposure)</strong>
      <div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;">
        Distance: ${direct.distance_km} km • Avg AQI: ${Math.round(direct.avg_aqi)}
      </div>
      <div style="font-size: 11px; color: #F87171;">
        Inhaled PM2.5: <strong>${direct.inhalation_pm25_ug} µg</strong>
      </div>
    </div>
  `);

  // 3. Draw Clean-Air Green Corridor Road Route (Luminous Green)
  activeCleanPolyline = L.polyline(cleanRoadCoords, {
    color: '#10B981',
    weight: 6,
    opacity: 0.95
  }).addTo(mapInstance);

  activeCleanPolyline.bindPopup(`
    <div style="font-family: 'Inter', sans-serif; padding: 4px;">
      <strong style="color: #10B981;">🛡️ Recommended Green Road Corridor</strong>
      <div style="font-size: 11px; color: #CBD5E1; margin-top: 2px;">
        Distance: ${clean.distance_km} km • Avg AQI: ${Math.round(clean.avg_aqi)}
      </div>
      <div style="font-size: 11px; color: #10B981; font-weight: 700;">
        ✓ ${clean.inhalation_reduction_pct}% Inhalation Reduction (${clean.inhalation_pm25_ug} µg PM2.5)
      </div>
    </div>
  `);

  // 4. Add Custom Origin (A) and Destination (B) Pin Markers
  const startIcon = L.divIcon({
    className: 'route-pin-icon',
    html: `<div style="background: #3B82F6; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 12px; border: 2px solid white; box-shadow: 0 0 14px #3B82F6;">A</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  });

  const endIcon = L.divIcon({
    className: 'route-pin-icon',
    html: `<div style="background: #10B981; color: white; width: 28px; height: 28px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 12px; border: 2px solid white; box-shadow: 0 0 14px #10B981;">B</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14]
  });

  const startM = L.marker(startCoord, { icon: startIcon }).addTo(mapInstance).bindPopup(`<strong>Origin:</strong> ${routeData.origin}`);
  const endM = L.marker(endCoord, { icon: endIcon }).addTo(mapInstance).bindPopup(`<strong>Destination:</strong> ${routeData.destination}`);
  activeRouteMarkers.push(startM, endM);

  // 5. Fit map bounds to show the complete road route
  const allCoords = [...directRoadCoords, ...cleanRoadCoords];
  if (allCoords.length > 0) {
    activeRouteBounds = L.latLngBounds(allCoords);
    mapInstance.fitBounds(activeRouteBounds, { padding: [50, 50], maxZoom: 14 });
  }

  // 6. Update Map Info bar with Clean Route legend
  const plumeInfoEl = document.getElementById('plumeInfo');
  if (plumeInfoEl) {
    plumeInfoEl.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: var(--radius-sm); padding: 10px 14px; margin-top: 8px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
          <span style="font-weight: 700; color: #10B981; font-size: 0.82rem;">
            🗺️ Active Navigation Routes:
          </span>
          <span style="font-size: 0.72rem; color: var(--text-muted);">
            <span style="color: #EF4444; font-weight: 700;">╍╍ Arterial Highway</span> vs
            <span style="color: #10B981; font-weight: 700;">━ Green Road Route</span>
          </span>
        </div>
        <div style="font-size: 0.76rem; color: #CBD5E1; margin-top: 4px;">
          From <strong>${routeData.origin}</strong> to <strong>${routeData.destination}</strong>:
          Arterial Highway (Red) vs Recommended Clean-Air Corridor (Green with <strong style="color: #10B981;">${clean.inhalation_reduction_pct}% less PM2.5 inhalation</strong>).
        </div>
      </div>
    `;
  }
}

function highlightStationOnMap(stationId) {
  if (stationMarkers[stationId] && mapInstance) {
    const marker = stationMarkers[stationId];
    mapInstance.flyTo(marker.getLatLng(), 13, { duration: 0.8 });
    marker.openPopup();
  }
}
