const API = '/api';
const el = (id) => document.getElementById(id);
let lastSnapshot = null;
let trend = [];
let progressTimer = 0;

function setClock() {
  el('clock').textContent = new Date().toLocaleTimeString('en-GB', {hour12: false});
}
setInterval(setClock, 1000); setClock();

async function apiCall(endpoint, body = {}) {
  try {
    const response = await fetch(`${API}/${endpoint}`, {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
    });
    const data = await response.json();
    toast(data.message, !data.ok);
    return data;
  } catch (error) {
    toast(`Communication error: ${error.message}`, true);
    return {ok: false};
  }
}

function toast(message, isError = false) {
  const node = el('toast');
  node.textContent = message;
  node.classList.toggle('error', isError);
  node.classList.add('visible');
  clearTimeout(node._timer);
  node._timer = setTimeout(() => node.classList.remove('visible'), 2600);
}

document.querySelectorAll('[data-action]').forEach(button => {
  button.addEventListener('click', async () => {
    const action = button.dataset.action;
    const result = await apiCall(action);
    if (result.ok) await refresh();
  });
});

const speedRange = el('speedRange');
const defectRange = el('defectRange');
speedRange.addEventListener('input', () => el('speedOutput').value = `${Number(speedRange.value).toFixed(2)}×`);
defectRange.addEventListener('input', () => el('defectOutput').value = `${defectRange.value}%`);
el('applySettings').addEventListener('click', async () => {
  await apiCall('settings', {
    machine_speed: Number(speedRange.value),
    defect_probability: Number(defectRange.value) / 100
  });
  await refresh();
});

function updateState(snapshot) {
  const state = snapshot.state;
  const pill = el('statePill');
  pill.className = `status-pill ${state.toLowerCase()}`;
  el('machineState').textContent = state.replace('_', ' ');
  el('alertBanner').classList.toggle('hidden', !snapshot.fault_message);
  el('faultText').textContent = snapshot.fault_message || '';
  document.querySelector('.operation-dot').style.color = state === 'RUNNING' ? 'var(--green)' : state.includes('FAULT') || state === 'EMERGENCY_STOP' ? 'var(--red)' : 'var(--muted)';
}

function updateProcess(snapshot) {
  document.querySelectorAll('.stage').forEach((stage, index) => {
    stage.classList.toggle('active', snapshot.state === 'RUNNING' && index === snapshot.stage_index);
    stage.classList.toggle('done', snapshot.current_product_id && index < snapshot.stage_index);
  });
  el('currentStage').textContent = snapshot.stage;
  el('productId').textContent = snapshot.current_product_id ? `#${snapshot.current_product_id}` : '—';
  const progress = snapshot.stage_index < 0 ? 0 : ((snapshot.stage_index + (snapshot.state === 'RUNNING' ? .45 : 0)) / 6 * 100);
  el('stageProgress').style.width = `${Math.max(0, Math.min(100, progress))}%`;
}

function updateMetrics(snapshot) {
  el('totalCount').textContent = snapshot.total_count;
  el('goodCount').textContent = snapshot.good_count;
  el('defectCount').textContent = snapshot.defect_count;
  el('yieldPercent').textContent = Number(snapshot.yield_percent).toFixed(1);
  el('defectReason').textContent = snapshot.last_defect_reason === 'None' ? 'No defects recorded' : snapshot.last_defect_reason;
  el('temperature').textContent = Number(snapshot.temperature_c).toFixed(1);
  el('cycleTime').textContent = Number(snapshot.last_cycle_time_s).toFixed(2);
  el('speedValue').textContent = Number(snapshot.machine_speed).toFixed(2);
  el('tempGauge').style.width = `${Math.min(100, Math.max(0, (snapshot.temperature_c - 20) / 40 * 100))}%`;
  el('cycleGauge').style.width = `${Math.min(100, snapshot.last_cycle_time_s / 10 * 100)}%`;
  el('speedGauge').style.width = `${(snapshot.machine_speed - .5) / 1.5 * 100}%`;
  const connected = snapshot.database_connected;
  el('dbDot').classList.toggle('connected', connected);
  el('dbStatus').textContent = connected ? 'Connected · writing time-series data' : 'Offline preview · start Docker stack';
}

function updateSettings(snapshot) {
  if (document.activeElement !== speedRange) speedRange.value = snapshot.machine_speed;
  if (document.activeElement !== defectRange) defectRange.value = Math.round(snapshot.defect_probability * 100);
  el('speedOutput').value = `${Number(speedRange.value).toFixed(2)}×`;
  el('defectOutput').value = `${defectRange.value}%`;
}

function updateTable(products) {
  const tbody = el('productTable');
  if (!products.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="4">No completed products yet</td></tr>';
    return;
  }
  tbody.innerHTML = products.map(p => {
    const cls = p.result.toLowerCase();
    const detail = p.result === 'GOOD' ? 'All measurements within tolerance' : p.defect_reason;
    return `<tr><td>#${p.product_id}</td><td><span class="result-badge ${cls}">${p.result}</span></td><td>${Number(p.cycle_time_s).toFixed(2)} s</td><td title="${escapeHtml(detail)}">${escapeHtml(detail)}</td></tr>`;
  }).join('');
}

function updateLog(events) {
  el('eventLog').innerHTML = events.map(item => `<div class="log-item ${item.level.toLowerCase()}"><time>${item.time}</time><i></i><p>${escapeHtml(item.message)}</p></div>`).join('');
}

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char]));
}

function updateTrend(snapshot) {
  if (!lastSnapshot || snapshot.total_count !== lastSnapshot.total_count || trend.length === 0) {
    trend.push({good: snapshot.good_count, bad: snapshot.defect_count});
    if (trend.length > 30) trend.shift();
    drawChart();
  }
}

function drawChart() {
  const canvas = el('historyChart');
  const rect = canvas.getBoundingClientRect();
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.max(500, rect.width * ratio);
  canvas.height = 180 * ratio;
  const ctx = canvas.getContext('2d');
  ctx.scale(ratio, ratio);
  const w = rect.width, h = 180, pad = {l:36,r:12,t:12,b:24};
  ctx.clearRect(0,0,w,h);
  ctx.strokeStyle = '#213147'; ctx.lineWidth = 1;
  ctx.fillStyle = '#687b91'; ctx.font = '9px system-ui';
  const maxY = Math.max(5, ...trend.map(p => Math.max(p.good,p.bad)));
  for (let i=0;i<=4;i++) {
    const y = pad.t + (h-pad.t-pad.b) * i/4;
    ctx.beginPath(); ctx.moveTo(pad.l,y); ctx.lineTo(w-pad.r,y); ctx.stroke();
    ctx.fillText(String(Math.round(maxY*(1-i/4))), 8, y+3);
  }
  const drawLine = (key, color) => {
    if (!trend.length) return;
    ctx.strokeStyle=color; ctx.lineWidth=2; ctx.beginPath();
    trend.forEach((p,i) => {
      const x = pad.l + (w-pad.l-pad.r) * (trend.length === 1 ? 0 : i/(trend.length-1));
      const y = h-pad.b - (p[key]/maxY)*(h-pad.t-pad.b);
      i===0 ? ctx.moveTo(x,y) : ctx.lineTo(x,y);
    }); ctx.stroke();
  };
  drawLine('good','#28d19c'); drawLine('bad','#ff5263');
  ctx.fillStyle='#687b91'; ctx.fillText('Recent completed products', w/2-55, h-5);
}
window.addEventListener('resize', drawChart);

async function refresh() {
  try {
    const response = await fetch(`${API}/status`, {cache:'no-store'});
    const snapshot = await response.json();
    updateState(snapshot); updateProcess(snapshot); updateMetrics(snapshot); updateSettings(snapshot);
    updateTable(snapshot.recent_products); updateLog(snapshot.event_log); updateTrend(snapshot);
    lastSnapshot = snapshot;
  } catch (error) {
    el('dbStatus').textContent = 'HMI server unavailable';
    el('dbDot').classList.remove('connected');
  }
}
setInterval(refresh, 500); refresh();
