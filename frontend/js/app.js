/**
 * AirPulse AI — $10,000+ Enterprise Multi-Dashboard Controller (UI/UX Pro Max)
 * Coordinates 5 Executive Intelligence Sub-Dashboards:
 * 1. Command Center & Pan-India Spatial GIS
 * 2. Predictive AI, Uncertainty Bands & XAI Drivers
 * 3. SDG 13 Municipal Policy Simulation Lab
 * 4. SDG 3 Clean-Air Navigation & Vulnerable Health Matrix
 * 5. Governance, GRAP Protocols & SQLite Audit Trail
 */

let allStations = [];
let currentStationId = 'DEL-01';

document.addEventListener('DOMContentLoaded', () => {
  initApp();
});

async function initApp() {
  initSimulator();
  if (typeof setupChartTabListeners === 'function') {
    setupChartTabListeners();
  }
  setupEventListeners();
  setupViewNavigation();
  await loadInitialData();
}

function setupViewNavigation() {
  const viewBtns = document.querySelectorAll('.luxury-view-tabs .view-tab-btn');
  viewBtns.forEach(btn => {
    btn.onclick = function() {
      const targetViewId = btn.getAttribute('data-view');
      switchView(targetViewId);
    };
  });
}

function switchView(viewId) {
  if (!viewId) return;

  // 1. Update Tab Buttons
  document.querySelectorAll('.luxury-view-tabs .view-tab-btn').forEach(btn => {
    const isTarget = btn.getAttribute('data-view') === viewId;
    btn.classList.toggle('active', isTarget);
    btn.setAttribute('aria-selected', isTarget ? 'true' : 'false');
  });

  // 2. Update View Sections
  document.querySelectorAll('.app-view').forEach(view => {
    const isTarget = view.id === viewId;
    view.classList.toggle('active', isTarget);
  });

  // 3. View-Specific Dimension & Data Refreshes
  if (viewId === 'view-command-center') {
    setTimeout(() => {
      if (typeof mapInstance !== 'undefined' && mapInstance) {
        mapInstance.invalidateSize();
        if (typeof activeRouteBounds !== 'undefined' && activeRouteBounds) {
          mapInstance.fitBounds(activeRouteBounds, { padding: [50, 50], maxZoom: 14 });
        }
      }
    }, 120);
  } else if (viewId === 'view-forecaster') {
    setTimeout(() => {
      if (typeof forecastChartInstance !== 'undefined' && forecastChartInstance) {
        forecastChartInstance.resize();
      }
      if (typeof radarChartInstance !== 'undefined' && radarChartInstance) {
        radarChartInstance.resize();
      }
    }, 120);
  } else if (viewId === 'view-governance-audit') {
    loadAuditLogs();
  }
}

async function loadAuditLogs() {
  const tableBody = document.getElementById('auditLogTableBody');
  if (!tableBody) return;

  try {
    const res = await fetch('/api/audit-log?limit=30');
    if (!res.ok) throw new Error('Failed to load audit logs');
    const logs = await res.json();

    if (!logs || logs.length === 0) {
      tableBody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted); padding: 24px;">No operational audit logs recorded yet.</td></tr>';
      return;
    }

    tableBody.innerHTML = logs.map(l => {
      const aqiVal = l.aqi ? Math.round(l.aqi) : '--';
      let eventColor = 'var(--accent-cyan)';
      if (l.event_type && l.event_type.includes('CRITICAL')) eventColor = '#EF4444';
      else if (l.event_type && l.event_type.includes('POLICY')) eventColor = '#10B981';
      else if (l.event_type && l.event_type.includes('ALERT')) eventColor = '#F59E0B';

      const detailsStr = l.details ? (typeof l.details === 'string' ? l.details : JSON.stringify(l.details)) : '{}';

      return `
        <tr>
          <td style="font-family: var(--font-mono); color: var(--text-muted); font-size: 0.74rem;">${l.timestamp}</td>
          <td><strong style="color: var(--text-primary); font-family: var(--font-mono);">${l.station_id}</strong></td>
          <td><span style="font-size: 0.72rem; padding: 2px 8px; border-radius: 4px; background: rgba(255,255,255,0.06); color: ${eventColor}; font-weight: 700; border: 1px solid rgba(255,255,255,0.1);">${l.event_type}</span></td>
          <td><strong style="color: var(--aqi-usg); font-family: var(--font-mono); font-size: 0.88rem;">${aqiVal} AQI</strong></td>
          <td style="font-size: 0.74rem; color: var(--text-secondary); max-width: 320px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" title="${detailsStr.replace(/"/g, '&quot;')}">${detailsStr}</td>
        </tr>
      `;
    }).join('');
  } catch (err) {
    tableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: #F87171; padding: 20px;">Could not load audit logs: ${err.message}</td></tr>`;
  }
}

function setupEventListeners() {
  const stationSelect = document.getElementById('stationSelect');
  if (stationSelect) {
    stationSelect.addEventListener('change', (e) => {
      currentStationId = e.target.value;
      loadStationData(currentStationId);
      highlightStationOnMap(currentStationId);
    });
  }

  const refreshBtn = document.getElementById('refreshBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
      const originalText = refreshBtn.innerHTML;
      refreshBtn.innerHTML = '<span class="pulse-dot" style="display:inline-block;"></span> Syncing Live...';
      refreshBtn.style.opacity = '0.75';

      // Trigger OpenAQ live sync
      try {
        await fetch('/api/sync-openaq', { method: 'POST' });
      } catch (_) {}

      await loadStationData(currentStationId);
      setTimeout(() => {
        refreshBtn.innerHTML = originalText;
        refreshBtn.style.opacity = '1';
      }, 400);
    });
  }

  const calcRouteBtn = document.getElementById('calcRouteBtn');
  if (calcRouteBtn) {
    calcRouteBtn.addEventListener('click', calculateCleanRoute);
  }

  window.addEventListener('stationChanged', (e) => {
    currentStationId = e.detail.stationId;
    loadStationData(currentStationId);
  });
}

async function loadInitialData() {
  try {
    // 1. Fetch Stations across India
    const stnRes = await fetch('/api/stations');
    if (!stnRes.ok) throw new Error('Failed to load stations');
    allStations = await stnRes.json();

    // Group stations by city
    const stationsByCity = {};
    allStations.forEach(s => {
      const city = s.city || 'Other';
      if (!stationsByCity[city]) stationsByCity[city] = [];
      stationsByCity[city].push(s);
    });

    // Populate station dropdown with optgroups
    const select = document.getElementById('stationSelect');
    if (select) {
      select.innerHTML = Object.keys(stationsByCity).map(city => `
        <optgroup label="${city}">
          ${stationsByCity[city].map(s => `
            <option value="${s.id}" ${s.id === currentStationId ? 'selected' : ''}>
              ${s.id}: ${s.name}
            </option>
          `).join('')}
        </optgroup>
      `).join('');
    }

    // Populate Route origin and destination dropdowns
    const routeOrig = document.getElementById('routeOriginSelect');
    const routeDest = document.getElementById('routeDestSelect');
    if (routeOrig && routeDest) {
      const optionsHtml = Object.keys(stationsByCity).map(city => `
        <optgroup label="${city}">
          ${stationsByCity[city].map(s => `<option value="${s.id}">${s.id}: ${s.name}</option>`).join('')}
        </optgroup>
      `).join('');
      routeOrig.innerHTML = optionsHtml;
      routeDest.innerHTML = optionsHtml;
      if (allStations.length > 3) {
        routeDest.value = allStations[3].id;
      }
    }

    // Initialize Map with all Indian stations
    initMap(allStations);

    // 2. Fetch Patterns (Radar)
    const patRes = await fetch('/api/patterns');
    if (patRes.ok) {
      const patData = await patRes.json();
      initRadarChart(patData);
    }

    // 3. Load active station data
    await loadStationData(currentStationId);

    // 4. Initial audit log load
    loadAuditLogs();

  } catch (err) {
    console.error('Initial data load error:', err);
  }
}

async function loadStationData(stationId) {
  try {
    const station = allStations.find(s => s.id === stationId);
    if (station && station.current_readings) {
      updateKpis(station);
    }

    // 1. Fetch Forecasts (24h or 48h) + Prediction Details
    const fcRes = await fetch(`/api/forecast?station_id=${stationId}&hours=${currentHorizonHours}`);
    if (fcRes.ok) {
      const fcData = await fcRes.json();
      initForecastChart(fcData.forecasts);
      renderPredictionDetails(fcData.prediction_details);
    }

    // 2. Fetch Explainability
    const expRes = await fetch(`/api/explain?station_id=${stationId}`);
    if (expRes.ok) {
      const expData = await expRes.json();
      renderExplainability(expData);
    }

    // 3. Fetch Alerts
    const altRes = await fetch(`/api/alerts?station_id=${stationId}`);
    if (altRes.ok) {
      const altData = await altRes.json();
      renderAlerts(altData.alerts);
    }

    // 4. Fetch Health Advisories
    const advRes = await fetch(`/api/health-advisory?station_id=${stationId}`);
    if (advRes.ok) {
      const advData = await advRes.json();
      renderHealthAdvisory(advData);
    }

    // 5. Fetch Plume Dispersion
    const plumeRes = await fetch(`/api/plume-dispersion?station_id=${stationId}`);
    if (plumeRes.ok) {
      const plumeData = await plumeRes.json();
      renderPlumeOnMap(plumeData);
    }

    // Trigger simulator baseline update
    triggerSimulation();

  } catch (err) {
    console.error(`Error loading data for ${stationId}:`, err);
  }
}

function renderPredictionDetails(details) {
  if (!details) return;

  const peakEl = document.getElementById('predPeakTime');
  if (peakEl && details.peak_pollution_hour) {
    peakEl.textContent = `${details.peak_pollution_hour} (${details.peak_aqi} AQI)`;
  }

  const cleanEl = document.getElementById('predCleanestTime');
  if (cleanEl && details.cleanest_hour) {
    cleanEl.textContent = `${details.cleanest_hour} (${details.cleanest_aqi} AQI)`;
  }

  const trendEl = document.getElementById('predTrendDelta');
  if (trendEl && details.trend_24h_delta_pts !== undefined) {
    const sign = details.trend_24h_delta_pts > 0 ? '+' : '';
    trendEl.textContent = `${sign}${details.trend_24h_delta_pts} pts (${details.trend_direction || 'stable'})`;
    trendEl.style.color = details.trend_24h_delta_pts > 5 ? '#F87171' : (details.trend_24h_delta_pts < -5 ? '#10B981' : '#06B6D4');
  }

  const excEl = document.getElementById('predExceedanceHours');
  if (excEl && details.exceedance_hours_count !== undefined) {
    excEl.textContent = `${details.exceedance_hours_count} hrs / 24h`;
  }
}

async function calculateCleanRoute() {
  const originSelect = document.getElementById('routeOriginSelect');
  const destSelect = document.getElementById('routeDestSelect');
  const output = document.getElementById('cleanRouteOutput');

  if (!originSelect || !destSelect || !output) return;
  if (originSelect.value === destSelect.value) {
    output.innerHTML = '<div style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); border-radius: var(--radius-sm); padding: 8px 12px; color: #FBBF24; font-size: 0.8rem;">Please choose two distinct monitoring stations to compare routes.</div>';
    return;
  }

  output.innerHTML = '<div style="font-size: 0.8rem; color: var(--accent-cyan); padding: 8px;"><span class="pulse-dot" style="display:inline-block; margin-right: 6px;"></span> Optimizing green inhalation corridor...</div>';
  try {
    const res = await fetch(`/api/clean-route?origin_id=${originSelect.value}&destination_id=${destSelect.value}`);
    if (!res.ok) throw new Error('Route calculation failed');
    const route = await res.json();
    const direct = route.direct_route;
    const clean = route.clean_air_route;

    // Render the visual route lines on Leaflet map immediately
    if (typeof renderRouteOnMap === 'function') {
      renderRouteOnMap(route);
    }

    output.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.28); border-radius: var(--radius-md); padding: 14px 16px; margin-top: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
          <span style="font-weight: 800; color: var(--aqi-good); font-size: 0.88rem; display: flex; align-items: center; gap: 6px;">
            <span>🛡️</span> ${clean.inhalation_reduction_pct}% Inhalation Reduction on Green Route
          </span>
          <span style="font-size: 0.72rem; padding: 3px 8px; border-radius: 9999px; background: rgba(16, 185, 129, 0.15); color: #10B981; font-weight: 700;">
            SDG 3 Optimal
          </span>
        </div>
        <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 0.76rem;">
          <div style="background: rgba(255, 255, 255, 0.03); padding: 8px 10px; border-radius: 6px; border: 1px solid var(--border-subtle);">
            <div style="color: var(--text-muted); font-weight: 600;">DIRECT / HIGHWAY ROUTE</div>
            <div style="color: #F8FAFC; margin-top: 2px;">
              <strong>${direct.distance_km} km</strong> • <span style="color: #F97316; font-weight: 700;">${Math.round(direct.avg_aqi)} AQI</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 0.72rem;">Inhalation: <strong>${direct.inhalation_pm25_ug} µg PM2.5</strong></div>
          </div>
          <div style="background: rgba(16, 185, 129, 0.06); padding: 8px 10px; border-radius: 6px; border: 1px solid rgba(16, 185, 129, 0.25);">
            <div style="color: #10B981; font-weight: 700;">RECOMMENDED GREEN CORRIDOR</div>
            <div style="color: #F8FAFC; margin-top: 2px;">
              <strong>${clean.distance_km} km</strong> • <span style="color: #10B981; font-weight: 700;">${Math.round(clean.avg_aqi)} AQI</span>
            </div>
            <div style="color: var(--text-secondary); font-size: 0.72rem;">Inhalation: <strong style="color: #10B981;">${clean.inhalation_pm25_ug} µg PM2.5</strong></div>
          </div>
        </div>
        <button class="btn-action" style="margin-top: 12px; width: 100%; justify-content: center; background: linear-gradient(135deg, #10B981, #059669); font-size: 0.8rem; padding: 9px 16px;" onclick="switchView('view-command-center')">
          <span>🗺️</span> View Visual Routes on Spatial GIS Map
        </button>
      </div>
    `;
  } catch (err) {
    output.innerHTML = `<div style="color: #F87171; font-size: 0.8rem; padding: 6px;">Could not calculate clean route: ${err.message}</div>`;
  }
}

function updateKpis(stn) {
  const aqi = stn.aqi_summary ? stn.aqi_summary.aqi : 100;
  const color = stn.aqi_summary ? stn.aqi_summary.color_hex : '#F97316';
  const category = stn.aqi_summary ? stn.aqi_summary.category : 'Moderate';
  const dominant = stn.aqi_summary ? stn.aqi_summary.dominant_pollutant : 'PM2.5';
  const readings = stn.current_readings || {};
  const regime = stn.active_regime || {};

  // KPI 1: AQI
  const kpiAqiVal = document.getElementById('kpiAqiVal');
  if (kpiAqiVal) {
    kpiAqiVal.innerHTML = `${Math.round(aqi)} <span class="kpi-unit">AQI</span>`;
    kpiAqiVal.style.color = color;
  }

  const kpiAqiBadge = document.getElementById('kpiAqiBadge');
  if (kpiAqiBadge) {
    kpiAqiBadge.textContent = category;
    kpiAqiBadge.style.color = color;
    kpiAqiBadge.style.background = `${color}25`;
    kpiAqiBadge.style.borderColor = `${color}40`;
  }

  // KPI 2: Dominant Pollutant
  const domVal = readings[dominant.toLowerCase().replace('.', '')] || readings.pm25 || 35.0;
  const kpiDomVal = document.getElementById('kpiDominantVal');
  if (kpiDomVal) {
    kpiDomVal.innerHTML = `${domVal.toFixed(1)} <span class="kpi-unit">µg/m³</span>`;
  }
  const kpiDomBadge = document.getElementById('kpiDominantBadge');
  if (kpiDomBadge) {
    kpiDomBadge.textContent = `${dominant} (${stn.dominant_emission_source || 'Primary Source'})`;
  }

  const exceedanceRatio = (domVal / 15.0).toFixed(1);
  const kpiExceedance = document.getElementById('kpiExceedance');
  if (kpiExceedance) {
    kpiExceedance.textContent = `${exceedanceRatio}x WHO 24h Threshold`;
  }

  // KPI 3: Regime
  const kpiRegIcon = document.getElementById('kpiRegimeIcon');
  if (kpiRegIcon) kpiRegIcon.textContent = regime.icon || '🚗';

  const kpiRegName = document.getElementById('kpiRegimeName');
  if (kpiRegName) {
    kpiRegName.textContent = regime.short_name || 'Traffic Surge';
    kpiRegName.style.color = regime.color || '#F97316';
  }

  const kpiRegDesc = document.getElementById('kpiRegimeDesc');
  if (kpiRegDesc) {
    kpiRegDesc.textContent = regime.description || 'Elevated urban atmospheric emissions.';
  }

  // KPI 4: Meteo
  const kpiWind = document.getElementById('kpiWindSpeed');
  if (kpiWind) {
    kpiWind.innerHTML = `${readings.wind_speed || 2.0} m/s <span style="font-size: 0.72rem; color: #94A3B8;">(${getWindCategory(readings.wind_speed)})</span>`;
  }
  const kpiTemp = document.getElementById('kpiTemp');
  if (kpiTemp) kpiTemp.textContent = `${readings.temperature || 28.0} °C`;

  const kpiHum = document.getElementById('kpiHumidity');
  if (kpiHum) kpiHum.textContent = `${readings.humidity || 65.0} %`;

  const invStrength = readings.inversion_strength || 0.1;
  const invEl = document.getElementById('kpiInversion');
  if (invEl) {
    if (invStrength > 0.4) {
      invEl.textContent = 'High (Trapped)';
      invEl.style.color = '#EF4444';
    } else if (invStrength > 0.15) {
      invEl.textContent = 'Moderate';
      invEl.style.color = '#FBBF24';
    } else {
      invEl.textContent = 'Low (Dispersing)';
      invEl.style.color = '#10B981';
    }
  }
}

function getWindCategory(speed) {
  if (speed < 1.5) return 'Calm';
  if (speed < 4.0) return 'Moderate';
  return 'Breezy';
}

function renderExplainability(exp) {
  const xaiSummary = document.getElementById('xaiSummaryText');
  if (xaiSummary) {
    xaiSummary.textContent = exp.executive_summary || 'Analyzing drivers...';
  }

  const container = document.getElementById('driverBarsContainer');
  if (!container) return;
  const drivers = exp.drivers || [];

  container.innerHTML = drivers.map(d => `
    <div class="driver-bar-item">
      <div class="driver-bar-header">
        <span class="driver-name">${d.name}</span>
        <span class="driver-pct">${d.contribution_pct}%</span>
      </div>
      <div class="driver-progress-bg">
        <div class="driver-progress-fill" style="width: ${d.contribution_pct}%;"></div>
      </div>
      <div class="driver-desc">${d.explanation}</div>
    </div>
  `).join('');
}

function renderAlerts(alerts) {
  const container = document.getElementById('alertsContainer');
  if (!container) return;

  if (!alerts || alerts.length === 0) {
    container.innerHTML = `
      <div style="background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: var(--radius-md); padding: 16px; text-align: center;">
        <span style="color: var(--aqi-good); font-weight: 700; font-size: 0.88rem;">✓ No Active High-Risk Windows</span>
        <p style="font-size: 0.76rem; color: var(--text-secondary); margin-top: 4px;">Air quality forecast remains within acceptable operational thresholds.</p>
      </div>
    `;
    return;
  }

  container.innerHTML = alerts.map(a => `
    <div class="alert-card" style="border-left-color: ${a.severity_color || '#EF4444'};">
      <div class="alert-title">
        <span>⚠️</span> ${a.title}
      </div>
      <div style="font-size: 0.74rem; font-family: var(--font-mono); color: var(--text-muted); margin-top: 2px;">
        Window: ${a.time_window} • Peak: ${Math.round(a.peak_aqi)} AQI
      </div>
      <div class="alert-desc">${a.action_trigger}</div>
    </div>
  `).join('');
}

function renderHealthAdvisory(data) {
  const act = data.activity_windows || {};
  const cleanTime = document.getElementById('cleanWindowTime');
  if (cleanTime && act.optimal_outdoor_window) {
    cleanTime.textContent = act.optimal_outdoor_window.time_range;
  }
  const peakTime = document.getElementById('peakWindowTime');
  if (peakTime && act.peak_pollution_window) {
    peakTime.textContent = act.peak_pollution_window.time_range;
  }

  const adv = data.advisory || {};
  const groups = adv.groups || {};
  const grid = document.getElementById('healthDemographicsGrid');
  if (!grid) return;

  grid.innerHTML = Object.values(groups).map(g => `
    <div class="health-card">
      <div class="health-card-header">
        <span>${g.icon} ${g.title}</span>
        <span style="font-size: 0.7rem; padding: 2px 8px; border-radius: 9999px; background: rgba(255,255,255,0.06); color: ${g.status === 'Safe' ? '#10B981' : '#F97316'}; font-weight: 700;">
          ${g.status}
        </span>
      </div>
      <div class="health-card-guidance">${g.guidance}</div>
    </div>
  `).join('');
}

function switchHorizon(hours) {
  currentHorizonHours = hours;
  const btn24 = document.getElementById('btnHorizon24');
  const btn48 = document.getElementById('btnHorizon48');
  if (btn24) btn24.classList.toggle('active', hours === 24);
  if (btn48) btn48.classList.toggle('active', hours === 48);
  loadStationData(currentStationId);
}
