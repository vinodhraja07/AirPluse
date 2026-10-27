/**
 * AirPulse AI - What-If Policy Simulator (SDG 13 Municipal Climate Intervention)
 * Provides real-time interactive slider calculations and animated delta feedback.
 */

let simulationDebounceTimer = null;

function updateSliderProgress(slider, color = '#06B6D4') {
  if (!slider) return;
  const min = parseFloat(slider.min) || 0;
  const max = parseFloat(slider.max) || 100;
  const val = parseFloat(slider.value) || 0;
  const percentage = ((val - min) / (max - min)) * 100;
  slider.style.background = `linear-gradient(to right, ${color} 0%, ${color} ${percentage}%, rgba(255, 255, 255, 0.12) ${percentage}%, rgba(255, 255, 255, 0.12) 100%)`;
}

function initSimulator() {
  const sliderTraffic = document.getElementById('sliderTraffic');
  const sliderIndustrial = document.getElementById('sliderIndustrial');
  const sliderMisting = document.getElementById('sliderMisting');

  const trafficValLabel = document.getElementById('trafficValLabel');
  const indValLabel = document.getElementById('indValLabel');
  const mistValLabel = document.getElementById('mistValLabel');

  function onSliderInput() {
    if (sliderTraffic && trafficValLabel) {
      trafficValLabel.textContent = `-${sliderTraffic.value}%`;
      updateSliderProgress(sliderTraffic, '#06B6D4');
    }
    if (sliderIndustrial && indValLabel) {
      indValLabel.textContent = `-${sliderIndustrial.value}%`;
      updateSliderProgress(sliderIndustrial, '#3B82F6');
    }
    if (sliderMisting && mistValLabel) {
      mistValLabel.textContent = `${sliderMisting.value}% Coverage`;
      updateSliderProgress(sliderMisting, '#10B981');
    }

    clearTimeout(simulationDebounceTimer);
    simulationDebounceTimer = setTimeout(triggerSimulation, 100);
  }

  if (sliderTraffic) {
    sliderTraffic.addEventListener('input', onSliderInput);
    updateSliderProgress(sliderTraffic, '#06B6D4');
  }
  if (sliderIndustrial) {
    sliderIndustrial.addEventListener('input', onSliderInput);
    updateSliderProgress(sliderIndustrial, '#3B82F6');
  }
  if (sliderMisting) {
    sliderMisting.addEventListener('input', onSliderInput);
    updateSliderProgress(sliderMisting, '#10B981');
  }
}

async function triggerSimulation() {
  const select = document.getElementById('stationSelect');
  const stationId = select ? select.value : 'DEL-01';

  const sliderTraffic = document.getElementById('sliderTraffic');
  const sliderIndustrial = document.getElementById('sliderIndustrial');
  const sliderMisting = document.getElementById('sliderMisting');

  const trafficCut = sliderTraffic ? parseFloat(sliderTraffic.value) || 0 : 0;
  const indCut = sliderIndustrial ? parseFloat(sliderIndustrial.value) || 0 : 0;
  const misting = sliderMisting ? parseFloat(sliderMisting.value) || 0 : 0;

  try {
    const res = await fetch('/api/simulate-policy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        station_id: stationId,
        traffic_reduction_pct: trafficCut,
        industrial_curb_pct: indCut,
        road_misting_pct: misting
      })
    });

    if (!res.ok) return;
    const data = await res.json();

    const simAqiOutput = document.getElementById('simAqiOutput');
    const simHealthOutput = document.getElementById('simHealthOutput');
    const simCo2Output = document.getElementById('simCo2Output');

    if (data.aqi_reduction_pts > 0) {
      if (simAqiOutput) {
        simAqiOutput.innerHTML = `
          <span style="color: #94A3B8; font-size: 0.95rem; text-decoration: line-through;">${Math.round(data.baseline_aqi)}</span>
          <span style="color: var(--text-muted); margin: 0 4px;">→</span>
          <span style="color: ${data.simulated_color}; font-weight: 800; font-size: 1.25rem;">${Math.round(data.simulated_aqi)} AQI</span>
          <span style="font-size: 0.76rem; color: #10B981; font-weight: 700; background: rgba(16, 185, 129, 0.12); padding: 2px 6px; border-radius: 4px; margin-left: 6px;">
            -${data.aqi_reduction_pct}%
          </span>
        `;
      }
      if (simHealthOutput) {
        simHealthOutput.innerHTML = `<span style="color: #06B6D4; font-weight: 700;">+${data.avoided_emergency_admissions_est}</span> <span style="font-size: 0.78rem; color: var(--text-muted);">/ 100k pop</span>`;
      }
      if (simCo2Output) {
        simCo2Output.innerHTML = `<span style="color: #10B981; font-weight: 700;">${data.co2_mitigation_kg_est.toLocaleString()}</span> <span style="font-size: 0.78rem; color: var(--text-muted);">kg / day</span>`;
      }
    } else {
      if (simAqiOutput) {
        simAqiOutput.innerHTML = `<span style="color: ${data.baseline_color}; font-weight: 800;">${Math.round(data.baseline_aqi)} AQI</span> <span style="font-size: 0.75rem; color: var(--text-muted);">(Baseline)</span>`;
      }
      if (simHealthOutput) {
        simHealthOutput.innerHTML = `<span style="color: var(--text-muted);">+0 / 100k pop</span>`;
      }
      if (simCo2Output) {
        simCo2Output.innerHTML = `<span style="color: var(--text-muted);">0 kg / day</span>`;
      }
    }

  } catch (err) {
    console.error('Simulation error:', err);
  }
}
