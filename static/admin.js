const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const toast = $('#toast');

function say(t) {
  toast.textContent = t;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}

async function api(url, opt = {}) {
  const r = await fetch(url, opt);
  let j = {};
  try { j = await r.json(); } catch {}
  if (!r.ok) throw new Error(j.detail || 'L?i h? th?ng');
  return j;
}

function jobDisplayName(job) {
  return job.service === 'video_generation' ? 'AI Video Creator' : !job.service ? 'AI Motion Studio' : job.model;
}

async function boot() {
  try {
    const me = await api('/api/me');
    if (me.role !== 'admin') throw new Error('Kh?ng c? quy?n admin');
    initAdminTabs();
    await load();
  } catch (e) {
    alert(e.message);
    location.href = '/';
  }
}

async function load() {
  const [s, t, u, j, aw, au] = await Promise.all([
    api('/api/admin/stats'), api('/api/admin/topups'), api('/api/admin/users'), api('/api/admin/jobs'),
    api('/api/admin/affiliate/withdrawals'), api('/api/admin/affiliate/users')
  ]);
  $('#stats').innerHTML = [
    ['Ng??i d?ng', s.users], ['Waiting', s.waiting], ['Running', s.running], ['Done', s.done],
    ['Topup ch?', s.pending_topups], ['R?t ch?', s.pending_withdrawals], ['Affiliate th??ng', s.affiliate_rewards]
  ].map(x => `<div class="stat"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('');

  $('#topups').innerHTML = table(['ID', 'Kh?ch', 'G?i', 'Ti?n', 'L??t', 'Tr?ng th?i', ''], t.map(x => [
    x.id, x.email, x.package, x.amount_vnd.toLocaleString('vi-VN') + '?', x.credits, x.status,
    x.status === 'pending' ? `<button class="mini-btn approve" onclick="approve(${x.id})">Duy?t</button> <button class="mini-btn reject" onclick="rejectT(${x.id})">T? ch?i</button>` : ''
  ]));

  $('#users').innerHTML = table(['ID', 'Email', 'T?n', 'L??t', 'Role', ''], u.map(x => [
    x.id, x.email, x.name, x.credits, x.role, `<button class="mini-btn" onclick="addCredits(${x.id},'${x.email}')">? L??t</button>`
  ]));

  $('#jobs').innerHTML = table(['ID', 'Kh?ch', 'Model', 'Quality', 'Cost', 'Status', 'Progress', 'Error'], j.map(x => [
    x.id, x.email, jobDisplayName(x), x.quality + 'p', x.cost, x.status, x.progress + '%', x.error || ''
  ]));

  $('#affiliateWithdrawals').innerHTML = table(['ID', 'Kh?ch', 'L??t', 'VND', 'Method', 'Account', 'Status', ''], aw.map(x => [
    x.id, x.email, x.amount_credits, Number(x.amount_vnd).toLocaleString('vi-VN') + '?', x.method, x.account, x.status,
    x.status === 'pending' ? `<button class="mini-btn approve" onclick="payWithdrawal(${x.id})">?? tr?</button> <button class="mini-btn reject" onclick="rejectWithdrawal(${x.id})">T? ch?i</button>` : ''
  ]));

  $('#affiliateUsers').innerHTML = table(['ID', 'Email', 'M?', 'H?ng', 'Rate', 'Refs', 'Doanh s?', 'Th??ng', 'C? th? r?t', 'Ng??i GT'], au.map(x => [
    x.id, x.email, x.referral_code, x.tier, x.rate_percent + '%', x.direct_referrals, x.sales_credits, x.total_rewards, x.available, x.referrer?.email || ''
  ]));
}

function table(headers, rows) {
  return `<table class="table"><thead><tr>${headers.map(x => `<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(x => `<td>${x ?? ''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

window.approve = async id => {
  try {
    const j = await api(`/api/admin/topups/${id}/approve`, { method: 'POST' });
    say(`?? duy?t ? bonus ${j.buyer_bonus || 0} ? commission ${j.direct_commission || 0}`);
    load();
  } catch (e) { say(e.message); }
};

window.rejectT = async id => {
  try {
    await api(`/api/admin/topups/${id}/reject`, { method: 'POST' });
    say('?? t? ch?i');
    load();
  } catch (e) { say(e.message); }
};

window.addCredits = async (id, email) => {
  const d = prompt(`C?ng/tr? l??t cho ${email}. V? d? 100 ho?c -20:`);
  if (!d) return;
  try {
    await api(`/api/admin/users/${id}/credits`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delta: Number(d), reason: 'Admin ?i?u ch?nh' })
    });
    say('?? c?p nh?t l??t');
    load();
  } catch (e) { say(e.message); }
};

window.payWithdrawal = async id => {
  const note = prompt('Ghi ch? thanh to?n (tu? ch?n):') || '';
  try {
    await api(`/api/admin/affiliate/withdrawals/${id}/paid`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_note: note })
    });
    say('?? ??nh d?u thanh to?n');
    load();
  } catch (e) { say(e.message); }
};

window.rejectWithdrawal = async id => {
  const note = prompt('L? do t? ch?i:') || '';
  try {
    await api(`/api/admin/affiliate/withdrawals/${id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_note: note })
    });
    say('?? t? ch?i y?u c?u r?t');
    load();
  } catch (e) { say(e.message); }
};

let wfInitialized = false;
function initAdminTabs() {
  $$('.admin-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      $$('.admin-tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      const tab = btn.dataset.tab;
      if (tab === 'overview') {
        $('#tab-overview').style.display = 'block';
        $('#tab-workflow-studio').style.display = 'none';
      } else if (tab === 'workflow-studio') {
        $('#tab-overview').style.display = 'none';
        $('#tab-workflow-studio').style.display = 'block';
        if (!wfInitialized) {
          initWorkflowStudio();
          wfInitialized = true;
        }
      }
    });
  });
}

const NODE_DEFS = {
  input_image: {
    title: "Input Image",
    icon: "??",
    inputs: [],
    outputs: [{ id: "image", name: "Image Out", type: "IMAGE" }],
    defaultParams: { slot: "character_image", label: "?nh nh?n v?t" }
  },
  input_prompt: {
    title: "Input Prompt",
    icon: "??",
    inputs: [],
    outputs: [{ id: "text", name: "Prompt Out", type: "STRING" }],
    defaultParams: { prompt: "A young woman smiling naturally in cinematic lighting, 4k ultra realistic" }
  },
  wan_video: {
    title: "Wan 2.1 Video",
    icon: "??",
    inputs: [{ id: "image", name: "Image", type: "IMAGE" }, { id: "prompt", name: "Prompt", type: "STRING" }],
    outputs: [{ id: "video", name: "Video", type: "VIDEO" }],
    defaultParams: { steps: 30, cfg: 6.5, seed: 1337, denoise: 0.85, duration: 5.0 }
  },
  minimax_h3: {
    title: "MiniMax-H3",
    icon: "?",
    inputs: [{ id: "image", name: "Image", type: "IMAGE" }, { id: "prompt", name: "Prompt", type: "STRING" }],
    outputs: [{ id: "video", name: "Video", type: "VIDEO" }],
    defaultParams: { steps: 40, cfg: 7.0, seed: 42000, motion_intensity: 1.2 }
  },
  flux2_klein: {
    title: "FLUX.2 Klein",
    icon: "??",
    inputs: [{ id: "image", name: "Base Image", type: "IMAGE" }, { id: "reference", name: "Reference", type: "IMAGE" }, { id: "prompt", name: "Prompt", type: "STRING" }],
    outputs: [{ id: "image", name: "Image", type: "IMAGE" }],
    defaultParams: { steps: 28, cfg: 4.5, denoise: 0.75, preserve_face: true }
  },
  realesrgan: {
    title: "RealESRGAN Upscale",
    icon: "??",
    inputs: [{ id: "input", name: "Input", type: "ANY" }],
    outputs: [{ id: "output", name: "Upscaled", type: "ANY" }],
    defaultParams: { scale: 4, restore_face: true, denoise: 0.3 }
  },
  output_video: {
    title: "Output Video",
    icon: "??",
    inputs: [{ id: "video", name: "Video In", type: "VIDEO" }, { id: "image", name: "Image In", type: "IMAGE" }],
    outputs: [],
    defaultParams: { codec: "h264", bitrate: "12M", format: "mp4" }
  }
};

let currentWorkflow = {
  id: "wf_wan21_motion",
  name: "Wan 2.1 Video Motion Studio",
  description: "Sao ch?p chuy?n ??ng video m?u v? t?o video ch?n th?c t? ?nh nh?n v?t b?ng Wan 2.1.",
  nodes: [],
  links: []
};

let allWorkflows = [];
let connectingPort = null;
let zoomLevel = 1;
let panOffset = { x: 0, y: 0 };

async function initWorkflowStudio() {
  await loadWorkflowsList();
  bindStudioEvents();
  renderWorkflowGraph();
}

async function loadWorkflowsList() {
  try {
    allWorkflows = await api('/api/admin/workflows');
    const sel = $('#wfSelector');
    sel.innerHTML = allWorkflows.map(w => `<option value="${w.id}">${w.name} ${w.published ? ' (?? xu?t b?n)' : ''}</option>`).join('');
    if (allWorkflows.length > 0) {
      currentWorkflow = JSON.parse(JSON.stringify(allWorkflows[0]));
      $('#wfTitleInput').value = currentWorkflow.name || '';
      renderWorkflowGraph();
    }
  } catch (e) {
    say('Kh?ng t?i ???c danh s?ch workflow: ' + e.message);
  }
}

function bindStudioEvents() {
  $('#wfSelector').addEventListener('change', e => {
    const w = allWorkflows.find(x => x.id === e.target.value);
    if (w) {
      currentWorkflow = JSON.parse(JSON.stringify(w));
      $('#wfTitleInput').value = currentWorkflow.name || '';
      renderWorkflowGraph();
      say(`?? n?p: ${w.name}`);
    }
  });

  $('#wfTitleInput').addEventListener('input', e => {
    currentWorkflow.name = e.target.value;
  });

  $('#wfBtnNew').addEventListener('click', () => {
    currentWorkflow = {
      id: "wf_" + Math.random().toString(36).substring(2, 8),
      name: "Workflow M?i " + new Date().toLocaleTimeString('vi-VN'),
      description: "Quy tr?nh AI t?y ch?nh",
      nodes: [
        { id: "node_1", type: "input_image", title: "?nh ??u V?o", x: 60, y: 120, params: { slot: "character_image" } },
        { id: "node_2", type: "input_prompt", title: "Prompt ??u V?o", x: 60, y: 340, params: { prompt: "Cinematic portrait, 4k" } },
        { id: "node_3", type: "wan_video", title: "Wan 2.1 Video", x: 420, y: 180, params: { steps: 30, cfg: 6.5, seed: 1234, denoise: 0.85 } },
        { id: "node_4", type: "output_video", title: "Xu?t Video", x: 800, y: 180, params: { codec: "h264", format: "mp4" } }
      ],
      links: [
        { id: "link_1", from_node: "node_1", from_port: "image", to_node: "node_3", to_port: "image" },
        { id: "link_2", from_node: "node_2", from_port: "text", to_node: "node_3", to_port: "prompt" },
        { id: "link_3", from_node: "node_3", from_port: "video", to_node: "node_4", to_port: "video" }
      ]
    };
    $('#wfTitleInput').value = currentWorkflow.name;
    renderWorkflowGraph();
    say("?? t?o ?? th? m?i");
  });

  $('#wfBtnDuplicate').addEventListener('click', () => {
    const clone = JSON.parse(JSON.stringify(currentWorkflow));
    clone.id = "wf_" + Math.random().toString(36).substring(2, 8);
    clone.name += " (B?n sao)";
    currentWorkflow = clone;
    $('#wfTitleInput').value = currentWorkflow.name;
    renderWorkflowGraph();
    say("?? nh?n b?n workflow");
  });

  $('#wfBtnClear').addEventListener('click', () => {
    if (confirm('X?a to?n b? nodes v? k?t n?i hi?n t?i?')) {
      currentWorkflow.nodes = [];
      currentWorkflow.links = [];
      renderWorkflowGraph();
    }
  });

  $('#wfBtnSave').addEventListener('click', async () => {
    try {
      currentWorkflow.name = $('#wfTitleInput').value || 'Workflow AI';
      await api('/api/admin/workflows', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(currentWorkflow)
      });
      say('?? l?u workflow th?nh c?ng!');
      await loadWorkflowsList();
      $('#wfSelector').value = currentWorkflow.id;
    } catch (e) {
      say('L?i khi l?u: ' + e.message);
    }
  });

  $('#wfBtnPublish').addEventListener('click', async () => {
    try {
      if (!currentWorkflow.id) await $('#wfBtnSave').click();
      const res = await api(`/api/admin/workflows/${currentWorkflow.id}/publish`, { method: 'POST' });
      say(res.message || '?? xu?t b?n template ra trang ch? th?nh c?ng!');
      await loadWorkflowsList();
    } catch (e) {
      say('L?i khi xu?t b?n: ' + e.message);
    }
  });

  $('#wfBtnRun').addEventListener('click', runWorkflowTest);

  $$('.add-node-btn').forEach(b => {
    b.addEventListener('click', e => {
      const type = e.target.closest('.wf-node-item').dataset.type;
      addNodeToCanvas(type, 100 + Math.random() * 200, 100 + Math.random() * 150);
    });
  });

  $$('.wf-node-item').forEach(item => {
    item.addEventListener('dragstart', e => {
      e.dataTransfer.setData('node-type', item.dataset.type);
    });
  });

  const container = $('#wfCanvasContainer');
  container.addEventListener('dragover', e => e.preventDefault());
  container.addEventListener('drop', e => {
    e.preventDefault();
    const type = e.dataTransfer.getData('node-type');
    if (type) {
      const rect = container.getBoundingClientRect();
      const x = (e.clientX - rect.left - panOffset.x) / zoomLevel;
      const y = (e.clientY - rect.top - panOffset.y) / zoomLevel;
      addNodeToCanvas(type, Math.max(20, x), Math.max(20, y));
    }
  });

  $('#wfZoomIn').addEventListener('click', () => setZoom(zoomLevel + 0.15));
  $('#wfZoomOut').addEventListener('click', () => setZoom(zoomLevel - 0.15));
  $('#wfZoomReset').addEventListener('click', () => { zoomLevel = 1; panOffset = { x: 0, y: 0 }; updateCanvasTransform(); });

  document.addEventListener('mousemove', e => {
    if (connectingPort) {
      const stageRect = $('#wfCanvasStage').getBoundingClientRect();
      const x2 = (e.clientX - stageRect.left) / zoomLevel;
      const y2 = (e.clientY - stageRect.top) / zoomLevel;
      const x1 = connectingPort.x;
      const y1 = connectingPort.y;
      const pathStr = createBezierPath(x1, y1, x2, y2);
      const tempWire = $('#wfTempWire');
      tempWire.setAttribute('d', pathStr);
      tempWire.style.display = 'block';
    }
  });

  document.addEventListener('mouseup', () => {
    if (connectingPort) {
      connectingPort = null;
      $('#wfTempWire').style.display = 'none';
    }
  });

  $('#wfClearLogs').addEventListener('click', () => {
    $('#wfTerminal').innerHTML = '<div class="log-line dim">Log console ?? ???c x?a.</div>';
  });

  $('#wfToggleLogs').addEventListener('click', () => {
    const body = $('#wfLogBody');
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
  });
}

function setZoom(lvl) {
  zoomLevel = Math.max(0.4, Math.min(1.8, lvl));
  updateCanvasTransform();
}

function updateCanvasTransform() {
  $('#wfCanvasStage').style.transform = `translate(${panOffset.x}px, ${panOffset.y}px) scale(${zoomLevel})`;
  $('#wfZoomReset').textContent = Math.round(zoomLevel * 100) + '%';
}

function addNodeToCanvas(type, x = 100, y = 100) {
  const schema = NODE_DEFS[type];
  if (!schema) return;
  const nodeId = "node_" + (currentWorkflow.nodes.length + 1) + "_" + Math.random().toString(36).substring(2, 5);
  const newNode = {
    id: nodeId,
    type: type,
    title: schema.title,
    x: Math.round(x),
    y: Math.round(y),
    params: JSON.parse(JSON.stringify(schema.defaultParams || {}))
  };
  currentWorkflow.nodes.push(newNode);
  renderWorkflowGraph();
}

function renderWorkflowGraph() {
  const nodesContainer = $('#wfNodesLayer');
  nodesContainer.innerHTML = '';

  currentWorkflow.nodes.forEach(node => {
    const schema = NODE_DEFS[node.type] || { title: node.title, icon: "??", inputs: [], outputs: [] };
    const el = document.createElement('div');
    el.className = 'wf-node';
    el.id = 'dom_' + node.id;
    el.style.left = node.x + 'px';
    el.style.top = node.y + 'px';

    const head = document.createElement('div');
    head.className = 'wf-node-head';
    head.innerHTML = `
      <div class="wf-node-title"><span>${schema.icon}</span> <span>${node.title || schema.title}</span></div>
      <button type="button" class="wf-node-close" title="X?a Node">?</button>
    `;
    head.querySelector('.wf-node-close').addEventListener('click', e => {
      e.stopPropagation();
      deleteNode(node.id);
    });

    bindNodeDraggable(el, node);

    const body = document.createElement('div');
    body.className = 'wf-node-body';

    const portsRow = document.createElement('div');
    portsRow.className = 'wf-ports-row';

    const inCol = document.createElement('div');
    inCol.className = 'wf-ports-in';
    (schema.inputs || []).forEach(inp => {
      const port = document.createElement('div');
      port.className = 'wf-port in-port';
      port.dataset.nodeId = node.id;
      port.dataset.portId = inp.id;
      port.innerHTML = `<span class="wf-port-dot"></span><span>${inp.name}</span>`;
      port.addEventListener('mouseup', e => {
        e.stopPropagation();
        if (connectingPort && connectingPort.nodeId !== node.id) {
          createLink(connectingPort.nodeId, connectingPort.portId, node.id, inp.id);
          connectingPort = null;
          $('#wfTempWire').style.display = 'none';
        }
      });
      inCol.appendChild(port);
    });

    const outCol = document.createElement('div');
    outCol.className = 'wf-ports-out';
    (schema.outputs || []).forEach(outp => {
      const port = document.createElement('div');
      port.className = 'wf-port out-port';
      port.dataset.nodeId = node.id;
      port.dataset.portId = outp.id;
      port.innerHTML = `<span class="wf-port-dot"></span><span>${outp.name}</span>`;
      port.addEventListener('mousedown', e => {
        e.stopPropagation();
        const dot = port.querySelector('.wf-port-dot');
        const r = dot.getBoundingClientRect();
        const stageRect = $('#wfCanvasStage').getBoundingClientRect();
        connectingPort = {
          nodeId: node.id,
          portId: outp.id,
          x: (r.left + r.width / 2 - stageRect.left) / zoomLevel,
          y: (r.top + r.height / 2 - stageRect.top) / zoomLevel
        };
      });
      outCol.appendChild(port);
    });

    portsRow.appendChild(inCol);
    portsRow.appendChild(outCol);
    body.appendChild(portsRow);

    const paramsDiv = document.createElement('div');
    paramsDiv.className = 'wf-node-params';
    renderNodeParams(paramsDiv, node);
    body.appendChild(paramsDiv);

    el.appendChild(head);
    el.appendChild(body);
    nodesContainer.appendChild(el);
  });

  $('#wfNodeCount').textContent = currentWorkflow.nodes.length;
  $('#wfLinkCount').textContent = currentWorkflow.links.length;

  setTimeout(renderWires, 10);
}

function renderNodeParams(container, node) {
  if (node.type === 'input_prompt') {
    container.innerHTML = `
      <div class="wf-node-param">
        <label>Prompt:</label>
        <textarea rows="3">${node.params.prompt || ''}</textarea>
      </div>
    `;
    container.querySelector('textarea').addEventListener('input', e => {
      node.params.prompt = e.target.value;
    });
  } else if (node.type === 'wan_video') {
    container.innerHTML = `
      <div class="wf-node-param">
        <label>Steps: <b class="val-steps">${node.params.steps || 30}</b></label>
        <input type="range" min="15" max="50" value="${node.params.steps || 30}">
      </div>
      <div class="wf-node-param">
        <label>CFG Scale: <b class="val-cfg">${node.params.cfg || 6.5}</b></label>
        <input type="range" min="1.0" max="12.0" step="0.5" value="${node.params.cfg || 6.5}">
      </div>
      <div class="wf-node-param">
        <label>Denoise: <b class="val-denoise">${node.params.denoise || 0.85}</b></label>
        <input type="range" min="0.1" max="1.0" step="0.05" value="${node.params.denoise || 0.85}">
      </div>
    `;
    const inputs = container.querySelectorAll('input');
    inputs[0].addEventListener('input', e => { node.params.steps = Number(e.target.value); container.querySelector('.val-steps').textContent = e.target.value; });
    inputs[1].addEventListener('input', e => { node.params.cfg = Number(e.target.value); container.querySelector('.val-cfg').textContent = e.target.value; });
    inputs[2].addEventListener('input', e => { node.params.denoise = Number(e.target.value); container.querySelector('.val-denoise').textContent = e.target.value; });
  } else if (node.type === 'minimax_h3') {
    container.innerHTML = `
      <div class="wf-node-param">
        <label>Steps: <b class="val-steps">${node.params.steps || 40}</b></label>
        <input type="range" min="20" max="60" value="${node.params.steps || 40}">
      </div>
      <div class="wf-node-param">
        <label>Motion Intensity: <b class="val-motion">${node.params.motion_intensity || 1.2}</b></label>
        <input type="range" min="0.5" max="2.0" step="0.1" value="${node.params.motion_intensity || 1.2}">
      </div>
    `;
    const inputs = container.querySelectorAll('input');
    inputs[0].addEventListener('input', e => { node.params.steps = Number(e.target.value); container.querySelector('.val-steps').textContent = e.target.value; });
    inputs[1].addEventListener('input', e => { node.params.motion_intensity = Number(e.target.value); container.querySelector('.val-motion').textContent = e.target.value; });
  } else if (node.type === 'flux2_klein') {
    container.innerHTML = `
      <div class="wf-node-param">
        <label>Steps: <b class="val-steps">${node.params.steps || 28}</b></label>
        <input type="range" min="15" max="40" value="${node.params.steps || 28}">
      </div>
      <div class="wf-node-param">
        <label>CFG: <b class="val-cfg">${node.params.cfg || 4.5}</b></label>
        <input type="range" min="1.0" max="8.0" step="0.5" value="${node.params.cfg || 4.5}">
      </div>
    `;
    const inputs = container.querySelectorAll('input');
    inputs[0].addEventListener('input', e => { node.params.steps = Number(e.target.value); container.querySelector('.val-steps').textContent = e.target.value; });
    inputs[1].addEventListener('input', e => { node.params.cfg = Number(e.target.value); container.querySelector('.val-cfg').textContent = e.target.value; });
  } else if (node.type === 'realesrgan') {
    container.innerHTML = `
      <div class="wf-node-param">
        <label>T? l? ph?ng to:</label>
        <select>
          <option value="2" ${node.params.scale == 2 ? 'selected' : ''}>2x HD</option>
          <option value="4" ${node.params.scale == 4 ? 'selected' : ''}>4x Ultra HD</option>
        </select>
      </div>
    `;
    container.querySelector('select').addEventListener('change', e => {
      node.params.scale = Number(e.target.value);
    });
  } else if (node.type === 'input_image') {
    container.innerHTML = `
      <div class="wf-node-param">
        <label>M?c ??ch ?nh:</label>
        <select>
          <option value="character_image">?nh nh?n v?t ch?nh</option>
          <option value="outfit_reference">?nh trang ph?c</option>
          <option value="background_image">?nh b?i c?nh</option>
        </select>
      </div>
    `;
    container.querySelector('select').addEventListener('change', e => {
      node.params.slot = e.target.value;
    });
  }
}

function bindNodeDraggable(el, node) {
  const head = el.querySelector('.wf-node-head');
  let startX = 0, startY = 0, initialX = 0, initialY = 0;

  head.addEventListener('mousedown', e => {
    startX = e.clientX;
    startY = e.clientY;
    initialX = node.x;
    initialY = node.y;

    const onMove = ev => {
      const dx = (ev.clientX - startX) / zoomLevel;
      const dy = (ev.clientY - startY) / zoomLevel;
      node.x = Math.max(10, initialX + dx);
      node.y = Math.max(10, initialY + dy);
      el.style.left = node.x + 'px';
      el.style.top = node.y + 'px';
      renderWires();
    };

    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };

    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
}

function deleteNode(nodeId) {
  currentWorkflow.nodes = currentWorkflow.nodes.filter(n => n.id !== nodeId);
  currentWorkflow.links = currentWorkflow.links.filter(l => l.from_node !== nodeId && l.to_node !== nodeId);
  renderWorkflowGraph();
}

function createLink(fromNode, fromPort, toNode, toPort) {
  const exists = currentWorkflow.links.some(l => l.from_node === fromNode && l.from_port === fromPort && l.to_node === toNode && l.to_port === toPort);
  if (!exists) {
    currentWorkflow.links.push({
      id: "link_" + Math.random().toString(36).substring(2, 7),
      from_node: fromNode,
      from_port: fromPort,
      to_node: toNode,
      to_port: toPort
    });
    renderWorkflowGraph();
  }
}

function deleteLink(linkId) {
  currentWorkflow.links = currentWorkflow.links.filter(l => l.id !== linkId);
  renderWires();
}

function renderWires() {
  const group = $('#wfWiresGroup');
  group.innerHTML = '';
  const stageRect = $('#wfCanvasStage').getBoundingClientRect();

  currentWorkflow.links.forEach(link => {
    const fromEl = $(`#dom_${link.from_node} .out-port[data-port-id="${link.from_port}"] .wf-port-dot`);
    const toEl = $(`#dom_${link.to_node} .in-port[data-port-id="${link.to_port}"] .wf-port-dot`);

    if (fromEl && toEl) {
      const r1 = fromEl.getBoundingClientRect();
      const r2 = toEl.getBoundingClientRect();

      const x1 = (r1.left + r1.width / 2 - stageRect.left) / zoomLevel;
      const y1 = (r1.top + r1.height / 2 - stageRect.top) / zoomLevel;
      const x2 = (r2.left + r2.width / 2 - stageRect.left) / zoomLevel;
      const y2 = (r2.top + r2.height / 2 - stageRect.top) / zoomLevel;

      const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
      path.setAttribute('d', createBezierPath(x1, y1, x2, y2));
      path.className.baseVal = 'wf-wire';
      path.setAttribute('data-link-id', link.id);
      path.title = 'Click ?? x?a ???ng n?i n?y';

      path.addEventListener('click', e => {
        e.stopPropagation();
        deleteLink(link.id);
        say('?? x?a ???ng li?n k?t');
      });

      group.appendChild(path);
    }
  });

  $('#wfLinkCount').textContent = currentWorkflow.links.length;
}

function createBezierPath(x1, y1, x2, y2) {
  const dx = Math.abs(x2 - x1) * 0.55;
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

async function runWorkflowTest() {
  const btn = $('#wfBtnRun');
  const term = $('#wfTerminal');
  const status = $('#wfRunStatus');

  btn.disabled = true;
  btn.textContent = '? ?ang Ch?y Pipeline...';
  status.textContent = '?ang x? l?';
  status.style.background = 'rgba(245, 158, 11, 0.2)';
  status.style.borderColor = 'rgba(245, 158, 11, 0.5)';
  status.style.color = '#fbbf24';

  term.innerHTML = '<div class="log-line info">?? Kh?i ??ng pipeline ?? th?: ' + (currentWorkflow.name || 'Workflow') + '...</div>';

  try {
    const res = await api('/api/admin/workflows/test-run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentWorkflow)
    });

    const logs = res.logs || [];
    for (let i = 0; i < logs.length; i++) {
      await new Promise(r => setTimeout(r, 260));
      const log = logs[i];
      const line = document.createElement('div');
      line.className = `log-line ${log.level.toLowerCase()}`;
      line.textContent = `[${log.time}] [${log.level}] ${log.msg}`;
      term.appendChild(line);
      term.scrollTop = term.scrollHeight;
    }

    status.textContent = 'Th?nh c?ng';
    status.style.background = 'rgba(16, 185, 129, 0.2)';
    status.style.borderColor = 'rgba(16, 185, 129, 0.5)';
    status.style.color = '#6ee7b7';

    $('#wfPreviewPlaceholder').style.display = 'none';
    $('#wfPreviewContent').style.display = 'flex';
    const video = $('#wfPreviewVideo');
    video.src = res.preview_url || '/static/videos/card_motion.mp4';
    video.poster = res.poster_url || '/static/images/card_motion.png';
    video.load();
    video.play().catch(() => {});

    $('#wfPreviewTiming').textContent = `? Th?i gian x? l?: ${res.execution_time_sec || 10.5}s`;
    $('#wfPreviewDownload').href = res.preview_url || '/static/videos/card_motion.mp4';

    say('Ch?y test run ho?n t?t th?nh c?ng!');
  } catch (e) {
    const errLine = document.createElement('div');
    errLine.className = 'log-line export';
    errLine.textContent = `[ERROR] Th?c thi th?t b?i: ${e.message}`;
    term.appendChild(errLine);
    status.textContent = 'L?i';
    status.style.color = '#ff7583';
    say('L?i test run: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = '? Ch?y Th? Nghi?m (Test Run)';
  }
}

$('#refresh').onclick = load;
$('#logout').onclick = async () => {
  await fetch('/api/logout', { method: 'POST' });
  location.href = '/';
};

boot();