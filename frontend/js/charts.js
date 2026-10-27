/**
 * AirPulse AI — Chart.js Visualizations (UI/UX Pro Max)
 * Multi-Horizon Time-Series Forecasts with 90% Uncertainty Bands & Regime Radar
 */

let forecastChartInstance = null;
let radarChartInstance = null;
let currentForecastData = [];
let currentSelectedPollutant = 'aqi';
let currentHorizonHours = 24;

const POLLUTANT_CONFIG = {
  aqi: { label: 'Composite AQI', color: '#F97316', unit: 'AQI', maxScale: 350 },
  pm25: { label: 'PM2.5 Particulate', color: '#06B6D4', unit: 'µg/m³', maxScale: 150 },
  pm10: { label: 'PM10 Coarse Particulate', color: '#3B82F6', unit: 'µg/m³', maxScale: 250 },
  no2: { label: 'NO2 (Vehicular)', color: '#EF4444', unit: 'µg/m³', maxScale: 100 },
  so2: { label: 'SO2 (Industrial)', color: '#F59E0B', unit: 'µg/m³', maxScale: 80 },
  o3: { label: 'O3 (Ozone)', color: '#10B981', unit: 'µg/m³', maxScale: 120 },
  co: { label: 'CO (Carbon Monoxide)', color: '#8B5CF6', unit: 'mg/m³', maxScale: 5 }
};

function setupChartTabListeners() {
  const pollutantBtns = document.querySelectorAll('.chart-tabs .chart-tab-btn');
  pollutantBtns.forEach(btn => {
    btn.onclick = function(e) {
      pollutantBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const pollutant = btn.getAttribute('data-pollutant') || 'aqi';
      updateForecastPollutant(pollutant);
    };
  });

  const btn24 = document.getElementById('btnHorizon24');
  const btn48 = document.getElementById('btnHorizon48');
  if (btn24) {
    btn24.onclick = () => switchHorizon(24);
  }
  if (btn48) {
    btn48.onclick = () => switchHorizon(48);
  }
}

function initForecastChart(forecasts) {
  currentForecastData = forecasts || [];
  const canvas = document.getElementById('forecastChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  if (forecastChartInstance) {
    forecastChartInstance.destroy();
  }

  const labels = forecasts.map(f => f.display_time);
  const cfg = POLLUTANT_CONFIG[currentSelectedPollutant] || POLLUTANT_CONFIG.aqi;

  // Create smooth vertical gradient fill
  const gradientFill = ctx.createLinearGradient(0, 0, 0, 300);
  gradientFill.addColorStop(0, `${cfg.color}35`);
  gradientFill.addColorStop(0.7, `${cfg.color}08`);
  gradientFill.addColorStop(1, 'rgba(0, 0, 0, 0)');

  const datasets = [];

  // Primary Forecast Median Line
  datasets.push({
    label: `${cfg.label} (Forecast)`,
    data: forecasts.map(f => f[currentSelectedPollutant] !== undefined ? f[currentSelectedPollutant] : f.aqi),
    borderColor: cfg.color,
    backgroundColor: gradientFill,
    borderWidth: 3,
    pointRadius: 3.5,
    pointHoverRadius: 7,
    pointBackgroundColor: '#070B14',
    pointBorderColor: cfg.color,
    pointBorderWidth: 2.5,
    tension: 0.38,
    fill: true
  });

  // If PM2.5, add 90% Confidence Interval Bands
  if (currentSelectedPollutant === 'pm25') {
    datasets.push({
      label: '90% Upper Bound (p90)',
      data: forecasts.map(f => f.pm25_upper_90),
      borderColor: 'rgba(6, 182, 212, 0.5)',
      borderWidth: 1.5,
      borderDash: [5, 4],
      pointRadius: 0,
      fill: '+1',
      backgroundColor: 'rgba(6, 182, 212, 0.1)',
      tension: 0.38
    });

    datasets.push({
      label: '10% Lower Bound (p10)',
      data: forecasts.map(f => f.pm25_lower_90),
      borderColor: 'rgba(6, 182, 212, 0.5)',
      borderWidth: 1.5,
      borderDash: [5, 4],
      pointRadius: 0,
      fill: false,
      tension: 0.38
    });
  }

  forecastChartInstance = new Chart(ctx, {
    type: 'line',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          display: true,
          position: 'top',
          labels: {
            color: '#CBD5E1',
            boxWidth: 12,
            boxHeight: 12,
            usePointStyle: true,
            pointStyle: 'circle',
            font: { family: 'Inter', size: 11, weight: 600 }
          }
        },
        tooltip: {
          backgroundColor: 'rgba(13, 21, 39, 0.94)',
          titleColor: '#F8FAFC',
          bodyColor: '#E2E8F0',
          borderColor: 'rgba(255, 255, 255, 0.15)',
          borderWidth: 1,
          padding: 14,
          boxPadding: 6,
          usePointStyle: true,
          titleFont: { family: 'Inter', size: 12, weight: 700 },
          bodyFont: { family: 'Inter', size: 11 },
          callbacks: {
            afterBody: function(context) {
              const idx = context[0].dataIndex;
              const f = forecasts[idx];
              if (f) {
                return `\n• Category: ${f.category}\n• Dominant: ${f.dominant_pollutant}`;
              }
              return '';
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(255, 255, 255, 0.04)', drawBorder: false },
          ticks: { color: '#94A3B8', font: { size: 10.5, family: 'Inter', weight: 500 }, maxTicksLimit: 8 }
        },
        y: {
          grid: { color: 'rgba(255, 255, 255, 0.05)', drawBorder: false },
          ticks: { color: '#94A3B8', font: { size: 10.5, family: 'JetBrains Mono' } }
        }
      }
    }
  });
}

function updateForecastPollutant(pollutantKey) {
  currentSelectedPollutant = pollutantKey;
  if (currentForecastData && currentForecastData.length > 0) {
    initForecastChart(currentForecastData);
  }
}

function initRadarChart(patternPayload) {
  const canvas = document.getElementById('radarChart');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');

  if (radarChartInstance) {
    radarChartInstance.destroy();
  }

  const labels = patternPayload.radar_schema || ['PM2.5', 'NO2', 'SO2', 'Ozone', 'Traffic', 'Inversion'];
  const datasets = (patternPayload.radar_datasets || []).map(ds => ({
    label: ds.label,
    data: ds.data,
    borderColor: ds.color,
    backgroundColor: `${ds.color}20`,
    borderWidth: 2,
    pointRadius: 3.5,
    pointHoverRadius: 6,
    pointBackgroundColor: ds.color,
    pointBorderColor: '#0D1527',
    pointBorderWidth: 1.5
  }));

  radarChartInstance = new Chart(ctx, {
    type: 'radar',
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'bottom',
          labels: {
            color: '#CBD5E1',
            boxWidth: 10,
            boxHeight: 10,
            usePointStyle: true,
            font: { size: 9.5, family: 'Inter', weight: 600 },
            padding: 12
          }
        },
        tooltip: {
          backgroundColor: 'rgba(13, 21, 39, 0.94)',
          borderColor: 'rgba(255, 255, 255, 0.15)',
          borderWidth: 1,
          titleColor: '#F8FAFC',
          bodyColor: '#E2E8F0',
          padding: 10
        }
      },
      scales: {
        r: {
          grid: { color: 'rgba(255, 255, 255, 0.08)' },
          angleLines: { color: 'rgba(255, 255, 255, 0.08)' },
          pointLabels: { color: '#E2E8F0', font: { size: 10, family: 'Inter', weight: 600 } },
          ticks: { display: false, max: 100, min: 0 }
        }
      }
    }
  });
}
