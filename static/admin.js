const $ = s => document.querySelector(s);
const $$ = s => document.querySelectorAll(s);
const toast = $('#toast');
const adminLogState = {
  access: { page: 1, limit: 25, search: '' },
  security: { page: 1, limit: 25, search: '', event: '', severity: '' },
};

function say(t) {
  toast.textContent = t;
  toast.classList.add('show');
  setTimeout(() => toast.classList.remove('show'), 2200);
}

async function api(url, opt = {}) {
  const headers = new Headers(opt.headers || {});
  const token = localStorage.getItem('token');
  if (token && !headers.has('Authorization')) headers.set('Authorization', `Bearer ${token}`);
  const r = await fetch(url, { ...opt, headers, credentials: 'include' });
  let j = {};
  try { j = await r.json(); } catch {}
  if (!r.ok) {
    const error = new Error(j.detail || 'Lỗi hệ thống');
    error.status = r.status;
    error.url = url;
    throw error;
  }
  return j;
}

function jobDisplayName(job) {
  return job.service === 'video_generation' ? 'AI Video Creator' : !job.service ? 'AI Motion Studio' : job.model;
}

function redirectToLogin() {
  const returnTo = encodeURIComponent('/admin');
  location.href = `/app?return_to=${returnTo}#login`;
}

async function boot() {
  let me;
  try {
    me = await api('/api/me');
  } catch (error) {
    redirectToLogin();
    return;
  }
  if (me.role !== 'admin') {
    alert('Tài khoản hiện tại không phải admin.');
    location.href = '/';
    return;
  }
  initAdminTabs();
  try {
    await load();
  } catch (error) {
    say(`Không tải được một số dữ liệu quản trị: ${error.message}`);
  }
}

async function load() {
  const [s, t, u, j, aw, au, overview, affiliateSettings, affiliateRewards, accessLogs, securityLogs, securityDevices] = await Promise.all([
    api('/api/admin/stats'), api('/api/admin/topups'), api('/api/admin/users'), api('/api/admin/jobs'),
    api('/api/admin/affiliate/withdrawals'), api('/api/admin/affiliate/users'), api('/api/admin/overview'),
    api('/api/admin/affiliate/settings'), api('/api/admin/affiliate/rewards'), loadAdminAccessLogs(), loadAdminSecurityLogs(), api('/api/admin/security-devices')
  ]);
  renderAccessLogs(accessLogs);
  renderSecurityLogs(securityLogs);
  renderSecurityDevices(securityDevices);
  renderAffiliateSettings(affiliateSettings);
  renderAffiliateRewards(affiliateRewards);
  $('#stats').innerHTML = [
    ['Người dùng', overview.users_total], ['User mới hôm nay', overview.new_users.today], ['User mới 7 ngày', overview.new_users.seven_days], ['User mới 30 ngày', overview.new_users.thirty_days],
    ['Xu đang lưu hành', overview.credits_circulating], ['Doanh thu nạp Xu', Number(overview.topup_revenue_vnd || 0).toLocaleString('vi-VN') + ' đ'], ['Tổng job AI', overview.jobs_total],
    ['Waiting / Running', `${overview.job_status.waiting || 0} / ${overview.job_status.running || 0}`], ['Success / Failed', `${overview.job_status.done || 0} / ${overview.job_status.failed || 0}`]
  ].map(x => `<div class="stat"><span>${x[0]}</span><b>${x[1]}</b></div>`).join('');

  $('#topups').innerHTML = table(['ID', 'Khách', 'Gói', 'Tiền', 'Xu', 'Trạng thái', ''], t.map(x => [
    x.id, x.email, x.package, x.amount_vnd.toLocaleString('vi-VN') + ' đ', x.credits, topupStatusLabel(x),
    x.payment_method === 'PAYOS' && ['pending', 'pending_payment'].includes(x.status) ? `<button class="mini-btn approve" onclick="syncTopup(${x.id})">Đồng bộ</button>` : x.payment_method === 'MANUAL' && x.status === 'pending' ? `<button class="mini-btn approve" onclick="approve(${x.id})">Duyệt</button> <button class="mini-btn reject" onclick="rejectT(${x.id})">Từ chối</button>` : ''
  ]));

  $('#users').innerHTML = table(['ID', 'Email', 'Tên', 'Xu', 'Role', ''], u.map(x => [
    x.id, x.email, x.name, x.credits, x.role, `<button class="mini-btn" onclick="addCredits(${x.id},'${x.email}')">Cộng / trừ Xu</button>`
  ]));

  $('#jobs').innerHTML = table(['ID', 'Khách', 'Công cụ', 'Quality', 'Xu', 'Trạng thái', 'Tiến độ', 'Lỗi'], j.map(x => [
    x.id, x.email, jobDisplayName(x), x.quality + 'p', x.cost, x.status, x.progress + '%', x.error || ''
  ]));

  $('#affiliateWithdrawals').innerHTML = table(['ID', 'Khách', 'Xu', 'VND', 'Phương thức', 'Tài khoản', 'Trạng thái', ''], aw.map(x => [
    x.id, x.email, x.amount_credits, Number(x.amount_vnd).toLocaleString('vi-VN') + ' đ', x.method, x.account, x.status,
    x.status === 'pending' ? `<button class="mini-btn approve" onclick="payWithdrawal(${x.id})">Đã trả</button> <button class="mini-btn reject" onclick="rejectWithdrawal(${x.id})">Từ chối</button>` : ''
  ]));

  $('#affiliateUsers').innerHTML = table(['ID', 'Email', 'Mã', 'Hạng', 'Tỷ lệ', 'Giới thiệu', 'Doanh số', 'Thưởng', 'Có thể rút', 'Người GT'], au.map(x => [
    x.id, x.email, x.referral_code, x.tier, x.rate_percent + '%', x.direct_referrals, x.sales_credits, x.total_rewards, x.available, x.referrer?.email || ''
  ]));
  await loadAdminManagement();
}

function renderAffiliateSettings(settings) {
  if (!settings) return;
  $('#affiliateEnabled').checked = Boolean(settings.enabled);
  $('#affiliateSilverRate').value = settings.silver_rate_percent;
  $('#affiliateGoldRate').value = settings.gold_rate_percent;
  $('#affiliateBuyerBonus').value = settings.buyer_bonus_percent;
  $('#affiliateGoldThreshold').value = settings.gold_threshold_credits;
  $('#affiliateParentOverride').value = settings.parent_override_percent;
}
function renderAffiliateRewards(rows) {
  const root = $('#affiliateRewardsTable'); if (!root) return;
  root.innerHTML = table(['ID','Người nhận','Nguồn','Loại','Xu','Trạng thái',''], rows.map(row => [
    row.id, row.recipient_email, row.source_email, row.reward_type, row.amount_credits, row.status,
    row.status === 'pending' ? `<button class="mini-btn approve" onclick="approveAffiliateReward(${row.id})">Duyệt</button> <button class="mini-btn reject" onclick="rejectAffiliateReward(${row.id})">Từ chối</button>` : ''
  ]));
}
function renderAccessLogs(rows) {
  const root = $('#adminAccessLogsTable'); if (!root) return;
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
  const items = Array.isArray(rows) ? rows : rows.items || [];
  root.innerHTML = table(['Thời gian', 'IP', 'Tài khoản', 'Method', 'Đường dẫn', 'HTTP'], items.map(row => [
    escapeHtml(row.created_at), escapeHtml(row.ip_address), escapeHtml(row.email || 'Chưa đăng nhập'),
    escapeHtml(row.method), escapeHtml(row.path), escapeHtml(row.status_code)
  ]));
  renderLogPagination('access', rows.total ?? items.length);
}
function renderSecurityLogs(rows) {
  const root = $('#adminSecurityLogsTable'); if (!root) return;
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
  const eventNames = {
    google_login_success: 'Đăng nhập Google thành công', google_login_failed: 'Đăng nhập Google thất bại',
    google_token_invalid: 'Google token không hợp lệ', new_ip_login: 'Đăng nhập từ IP mới',
    new_device_login: 'Đăng nhập từ thiết bị mới', admin_access_denied: 'Truy cập Admin bị từ chối',
    admin_access: 'Truy cập Admin', logout: 'Đăng xuất'
  };
  const items = Array.isArray(rows) ? rows : rows.items || [];
  root.innerHTML = table(['Thời gian', 'IP', 'Tài khoản', 'Sự kiện', 'Thiết bị', 'Mức độ', 'HTTP'], items.map(row => [
    escapeHtml(row.created_at), escapeHtml(row.ip_address), escapeHtml(row.email || 'Chưa đăng nhập'),
    escapeHtml(eventNames[row.event] || row.event), escapeHtml(row.user_agent || '—'),
    escapeHtml(row.severity.toUpperCase()), escapeHtml(row.http_status || '—')
  ]));
  renderLogPagination('security', rows.total ?? items.length);
}
function logQuery(type) {
  const state = adminLogState[type];
  const params = new URLSearchParams({ page: state.page, limit: state.limit });
  Object.entries(state).forEach(([key, value]) => { if (key !== 'page' && key !== 'limit' && value) params.set(key, value); });
  return params;
}
function loadAdminAccessLogs() { return api(`/api/admin/access-logs?${logQuery('access')}`); }
function loadAdminSecurityLogs() { return api(`/api/admin/security-logs?${logQuery('security')}`); }
function renderLogPagination(type, total) {
  const state = adminLogState[type];
  const prefix = type === 'access' ? 'Access' : 'Security';
  const root = $(`#admin${prefix}LogsPagination`);
  const summary = $(`#admin${prefix}LogsSummary`);
  if (!root || !summary) return;
  const pages = Math.max(1, Math.ceil(total / state.limit));
  state.page = Math.min(state.page, pages);
  const start = total ? (state.page - 1) * state.limit + 1 : 0;
  const end = Math.min(state.page * state.limit, total);
  summary.textContent = total ? `Đang xem ${start}-${end} trên ${total} bản ghi` : 'Không có bản ghi phù hợp';
  root.innerHTML = `<button class="mini-btn" data-log-page="prev" ${state.page <= 1 ? 'disabled' : ''}>‹ Trước</button><span>Trang ${state.page}/${pages}</span><button class="mini-btn" data-log-page="next" ${state.page >= pages ? 'disabled' : ''}>Sau ›</button>`;
}
function renderSecurityDevices(rows) {
  const root = $('#adminSecurityDevicesTable'); if (!root) return;
  const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, character => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[character]));
  const deviceName = userAgent => /Android/i.test(userAgent) ? 'Android' : /iPhone|iPad/i.test(userAgent) ? 'iPhone/iPad' : /Windows/i.test(userAgent) ? 'Windows' : /Mac OS/i.test(userAgent) ? 'macOS' : /Linux/i.test(userAgent) ? 'Linux' : 'Thiết bị không xác định';
  const eventNames = { google_login_success: 'Đăng nhập Google thành công', new_ip_login: 'Đăng nhập từ IP mới', admin_access: 'Truy cập Admin', admin_access_denied: 'Truy cập Admin bị từ chối', logout: 'Đăng xuất' };
  root.innerHTML = table(['Tài khoản', 'Thiết bị', 'IP', 'Lần cuối', 'Số sự kiện', 'Sự kiện gần nhất'], rows.map(row => [
    escapeHtml(row.email || 'Chưa đăng nhập'), escapeHtml(deviceName(row.user_agent || '')), escapeHtml(row.ip_address),
    escapeHtml(row.last_seen), escapeHtml(row.event_count), escapeHtml(eventNames[row.last_event] || row.last_event || '—')
  ]));
}
function topupStatusLabel(row) {
  if (row.payment_method === 'PAYOS' && row.status === 'pending_payment') return 'Chờ thanh toán';
  if (row.status === 'paid' || row.status === 'completed') return 'Thành công';
  if (row.status === 'cancelled') return 'Đã hủy';
  if (row.status === 'rejected') return 'Đã từ chối';
  if (row.status === 'pending') return row.payment_method === 'MANUAL' ? 'Chờ duyệt' : 'Chờ thanh toán';
  return row.status;
}
window.approveAffiliateReward = async id => {
  try { const result = await api(`/api/admin/affiliate/rewards/${id}/approve`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({})}); say(`Đã cộng ${result.amount_credits} Xu thưởng referral`); load(); } catch (e) { say(e.message); }
};
window.rejectAffiliateReward = async id => {
  const note = prompt('Lý do từ chối (tuỳ chọn):') || '';
  try { await api(`/api/admin/affiliate/rewards/${id}/reject`, {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({admin_note:note})}); say('Đã từ chối thưởng referral'); load(); } catch (e) { say(e.message); }
};
setInterval(()=>{if(document.visibilityState==='visible')load().catch(()=>{})},15000);

async function loadAdminManagement() {
  try {
    const [users, transactions, jobs, tools] = await Promise.all([
      api('/api/admin/users'), api('/api/admin/transactions'), api('/api/admin/jobs'), api('/api/admin/tools')
    ]);
    renderAdminUsers(users);
    renderAdminTransactions(transactions);
    renderAdminJobs(jobs);
    renderAdminTools(tools);
  } catch (e) { say('Không tải được dữ liệu quản trị: ' + e.message); }
}

function renderAdminUsers(users) {
  const root = $('#adminUsersTable'); if (!root) return;
  root.innerHTML = table(['ID','Tên','Email','Xu','VIP/Role','Trạng thái',''], users.map(user => [
    user.id, user.name || '—', user.email, user.credits, user.role === 'admin' ? 'Admin' : 'User', user.is_locked ? 'Đã khóa' : 'Đang hoạt động',
    `<button class="mini-btn" data-admin-user="${user.id}">Chi tiết</button> <button class="mini-btn" data-admin-lock="${user.id}" data-locked="${user.is_locked ? 0 : 1}">${user.is_locked ? 'Mở khóa' : 'Khóa'}</button> <button class="mini-btn" onclick="addCredits(${user.id},'${String(user.email).replace(/'/g, '')}')">Cộng / trừ Xu</button>`
  ]));
}

function renderAdminTransactions(rows) {
  const root = $('#adminTransactionsTable'); if (!root) return;
  root.innerHTML = table(['ID','User','Gói','Số tiền','Xu','Mã GD','Trạng thái','Thời gian',''], rows.map(row => [
    row.id, row.email, row.package, Number(row.amount_vnd).toLocaleString('vi-VN') + ' đ', row.credits, row.order_code || '—', topupStatusLabel(row), row.created_at,
    row.payment_method === 'PAYOS' && ['pending', 'pending_payment'].includes(row.status) ? `<button class="mini-btn approve" onclick="syncTopup(${row.id})">Đồng bộ</button>` : row.payment_method === 'MANUAL' && row.status === 'pending' ? `<button class="mini-btn approve" onclick="approve(${row.id})">Duyệt</button> <button class="mini-btn reject" onclick="rejectT(${row.id})">Từ chối</button>` : ''
  ]));
}

function renderAdminJobs(rows) {
  const root = $('#adminJobsTable'); if (!root) return;
  const status = $('#adminJobStatus')?.value || '';
  const filtered = status ? rows.filter(row => row.status === status) : rows;
  root.innerHTML = table(['ID','User','Công cụ','Xu','Trạng thái','Tiến độ','Tạo lúc','Error'], filtered.map(row => [
    row.id, row.email, jobDisplayName(row), row.cost, row.status, (row.progress || 0) + '%', row.created_at, row.error || '—'
  ]));
}

async function showAdminUser(userId) {
  const root = $('#adminUserDetail'); if (!root) return;
  root.textContent = 'Đang tải...';
  try {
    const data = await api(`/api/admin/users/${userId}`);
    root.innerHTML = `<div class="admin-detail-grid"><div><b>${data.user.name || '—'}</b><p>${data.user.email}<br>Xu: ${data.user.credits}<br>Trạng thái: ${data.user.is_locked ? 'Đã khóa' : 'Đang hoạt động'}</p></div><div><h4>Lịch sử Xu</h4>${table(['Delta','Lý do','Thời gian'], data.ledger.slice(0,20).map(x => [x.delta, x.reason, x.created_at]))}</div><div><h4>Lịch sử AI Jobs</h4>${table(['ID','Công cụ','Status','Xu'], data.jobs.slice(0,20).map(x => [x.id, jobDisplayName(x), x.status, x.cost]))}</div></div>`;
  } catch (e) { root.textContent = e.message; }
}

function renderAdminTools(tools) {
  const root = $('#adminToolsGrid'); if (!root) return;
  root.innerHTML = tools.map(tool => `<form class="admin-tool-card" data-tool-key="${tool.service_key}">
    <div class="sectionbar"><h4>${tool.name}</h4><label><input name="enabled" type="checkbox" ${tool.enabled ? 'checked' : ''}> Bật</label></div>
    <label>Tên<input name="name" value="${tool.name}"></label><label>Mô tả<textarea name="description">${tool.description}</textarea></label>
    <label>Badge<input name="badge" value="${tool.badge}"></label><label>Giá Xu<input name="price_credits" type="number" min="0" value="${tool.price_credits}"></label><label><input name="is_free" type="checkbox" ${tool.is_free ? 'checked' : ''}> Miễn phí</label>
    <label>CTA<input name="cta_text" value="${tool.cta_text}"></label><button class="mini-btn approve" type="submit">Lưu công cụ</button>
  </form>`).join('');
}

function table(headers, rows) {
  return `<table class="table"><thead><tr>${headers.map(x => `<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(x => `<td>${x ?? ''}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
}

window.approve = async id => {
  if (!confirm('Duyệt giao dịch và cộng Xu cho tài khoản này?')) return;
  try {
    const j = await api(`/api/admin/topups/${id}/approve`, { method: 'POST' });
    say(`Đã duyệt • bonus ${j.buyer_bonus || 0} • commission ${j.direct_commission || 0}`);
    load();
  } catch (e) { say(e.message); }
};

window.rejectT = async id => {
  if (!confirm('Từ chối giao dịch này?')) return;
  try {
    await api(`/api/admin/topups/${id}/reject`, { method: 'POST' });
    say('Đã từ chối');
    load();
  } catch (e) { say(e.message); }
};

window.syncTopup = async id => {
  try {
    const result = await api(`/api/admin/topups/${id}/sync`, { method: 'POST' });
    say(result.settled ? 'Đã tự động duyệt và cộng Xu' : `PayOS chưa xác nhận thanh toán${result.payos_status ? ` (${result.payos_status})` : ''}`);
    load();
  } catch (e) { say(e.message); }
};

window.addCredits = async (id, email) => {
  const d = prompt(`Cộng/trừ Xu cho ${email}. Ví dụ 100 hoặc -20:`);
  if (!d) return;
  try {
    await api(`/api/admin/users/${id}/credits`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delta: Number(d), reason: 'Admin điều chỉnh' })
    });
    say('Đã cập nhật Xu');
    load();
  } catch (e) { say(e.message); }
};

window.payWithdrawal = async id => {
  const note = prompt('Ghi chú thanh toán (tuỳ chọn):') || '';
  try {
    await api(`/api/admin/affiliate/withdrawals/${id}/paid`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_note: note })
    });
    say('Đã đánh dấu thanh toán');
    load();
  } catch (e) { say(e.message); }
};

window.rejectWithdrawal = async id => {
  const note = prompt('Lý do từ chối:') || '';
  try {
    await api(`/api/admin/affiliate/withdrawals/${id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ admin_note: note })
    });
    say('Đã từ chối yêu cầu rút');
    load();
  } catch (e) { say(e.message); }
};

let wfInitialized = false;
const ADMIN_TABS = ['overview', 'users-admin', 'transactions-admin', 'jobs-admin', 'tools-admin', 'workflow-studio'];

function activateAdminTab(tab, { updateUrl = true } = {}) {
  const nextTab = ADMIN_TABS.includes(tab) ? tab : 'overview';
  $$('.admin-tab-btn').forEach(btn => btn.classList.toggle('active', btn.dataset.tab === nextTab));
  $$('.tab-pane').forEach(pane => {
    const active = pane.id === `tab-${nextTab}`;
    pane.style.display = active ? 'block' : 'none';
    pane.classList.toggle('active', active);
  });
  if (updateUrl) history.replaceState(null, '', `#${nextTab}`);
  if (nextTab === 'workflow-studio' && !wfInitialized) {
    wfInitialized = true;
    initWorkflowStudio();
  }
}

function initAdminTabs() {
  $$('.admin-tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      activateAdminTab(btn.dataset.tab);
    });
  });
  window.addEventListener('hashchange', () => activateAdminTab(location.hash.slice(1), { updateUrl: false }));
  activateAdminTab(location.hash.slice(1), { updateUrl: false });

  $('#adminUserSearch')?.addEventListener('input', async e => {
    const users = await api(`/api/admin/users?q=${encodeURIComponent(e.target.value)}`);
    renderAdminUsers(users);
  });
  $('#adminJobStatus')?.addEventListener('change', async () => renderAdminJobs(await api('/api/admin/jobs')));
  $('#adminTransactionsRefresh')?.addEventListener('click', async () => renderAdminTransactions(await api('/api/admin/transactions')));
  $('#adminUsersTable')?.addEventListener('click', async e => {
    const detail = e.target.closest('[data-admin-user]');
    const lock = e.target.closest('[data-admin-lock]');
    if (detail) await showAdminUser(detail.dataset.adminUser);
    if (lock) {
      if (!confirm(lock.dataset.locked === '1' ? 'Khóa tài khoản này?' : 'Mở khóa tài khoản này?')) return;
      await api(`/api/admin/users/${lock.dataset.adminLock}/lock`, { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({ locked: lock.dataset.locked === '1' }) });
      say('Đã cập nhật trạng thái tài khoản');
      renderAdminUsers(await api('/api/admin/users'));
    }
  });
  $('#adminToolsGrid')?.addEventListener('submit', async e => {
    const form = e.target.closest('[data-tool-key]'); if (!form) return;
    e.preventDefault();
    const data = Object.fromEntries(new FormData(form));
    data.enabled = form.elements.enabled.checked ? 1 : 0;
    data.is_free = form.elements.is_free.checked ? 1 : 0;
    data.price_credits = Number(data.price_credits || 0);
    await api(`/api/admin/tools/${form.dataset.toolKey}`, { method: 'PUT', headers: {'Content-Type':'application/json'}, body: JSON.stringify(data) });
    say('Đã lưu cấu hình công cụ');
  });
  $('#refreshAffiliateRewards')?.addEventListener('click', async () => renderAffiliateRewards(await api('/api/admin/affiliate/rewards')));
  $('#adminAccessLogsRefresh')?.addEventListener('click', async () => renderAccessLogs(await loadAdminAccessLogs()));
  $('#adminSecurityLogsRefresh')?.addEventListener('click', async () => {
    renderSecurityLogs(await loadAdminSecurityLogs());
  });
  ['access', 'security'].forEach(type => {
    const prefix = type === 'access' ? 'Access' : 'Security';
    const state = adminLogState[type];
    const search = $(`#admin${prefix}LogsSearch`);
    search?.addEventListener('change', async event => {
      state.search = event.target.value.trim(); state.page = 1;
      type === 'access' ? renderAccessLogs(await loadAdminAccessLogs()) : renderSecurityLogs(await loadAdminSecurityLogs());
    });
    $(`#admin${prefix}LogsLimit`)?.addEventListener('change', async event => {
      state.limit = Number(event.target.value) || 25; state.page = 1;
      type === 'access' ? renderAccessLogs(await loadAdminAccessLogs()) : renderSecurityLogs(await loadAdminSecurityLogs());
    });
    $(`#admin${prefix}LogsPagination`)?.addEventListener('click', async event => {
      const button = event.target.closest('[data-log-page]'); if (!button || button.disabled) return;
      state.page += button.dataset.logPage === 'next' ? 1 : -1;
      type === 'access' ? renderAccessLogs(await loadAdminAccessLogs()) : renderSecurityLogs(await loadAdminSecurityLogs());
    });
  });
  $('#adminSecurityLogsEvent')?.addEventListener('change', async event => {
    adminLogState.security.event = event.target.value; adminLogState.security.page = 1;
    renderSecurityLogs(await loadAdminSecurityLogs());
  });
  $('#adminSecurityLogsSeverity')?.addEventListener('change', async event => {
    adminLogState.security.severity = event.target.value; adminLogState.security.page = 1;
    renderSecurityLogs(await loadAdminSecurityLogs());
  });
  $('#adminSecurityDevicesRefresh')?.addEventListener('click', async () => renderSecurityDevices(await api('/api/admin/security-devices')));
  $('#affiliateSettingsForm')?.addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      enabled: $('#affiliateEnabled').checked,
      silver_rate_percent: Number($('#affiliateSilverRate').value),
      gold_rate_percent: Number($('#affiliateGoldRate').value),
      buyer_bonus_percent: Number($('#affiliateBuyerBonus').value),
      gold_threshold_credits: Number($('#affiliateGoldThreshold').value),
      parent_override_percent: Number($('#affiliateParentOverride').value),
    };
    try {
      const result = await api('/api/admin/affiliate/settings', { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload) });
      renderAffiliateSettings(result.settings);
      $('#affiliateSettingsStatus').textContent = 'Đã lưu ' + new Date().toLocaleTimeString('vi-VN');
      say('Đã cập nhật tỷ lệ hoa hồng Affiliate');
    } catch (error) { say(error.message); }
  });
}

const NODE_DEFS = {
  input_image: {
    title: "Input Image",
    icon: "▣",
    inputs: [],
    outputs: [{ id: "image", name: "Image Out", type: "IMAGE" }],
    defaultParams: { slot: "character_image", label: "Ảnh nhân vật" }
  },
  input_prompt: {
    title: "Input Prompt",
    icon: "✎",
    inputs: [],
    outputs: [{ id: "text", name: "Prompt Out", type: "STRING" }],
    defaultParams: { prompt: "A young woman smiling naturally in cinematic lighting, 4k ultra realistic" }
  },
  wan_video: {
    title: "Wan 2.1 Video",
    icon: "▶",
    inputs: [{ id: "image", name: "Image", type: "IMAGE" }, { id: "prompt", name: "Prompt", type: "STRING" }],
    outputs: [{ id: "video", name: "Video", type: "VIDEO" }],
    defaultParams: { steps: 30, cfg: 6.5, seed: 1337, denoise: 0.85, duration: 5.0 }
  },
  minimax_h3: {
    title: "MiniMax-H3",
    icon: "◈",
    inputs: [{ id: "image", name: "Image", type: "IMAGE" }, { id: "prompt", name: "Prompt", type: "STRING" }],
    outputs: [{ id: "video", name: "Video", type: "VIDEO" }],
    defaultParams: { steps: 40, cfg: 7.0, seed: 42000, motion_intensity: 1.2 }
  },
  flux2_klein: {
    title: "FLUX.2 Klein",
    icon: "◉",
    inputs: [{ id: "image", name: "Base Image", type: "IMAGE" }, { id: "reference", name: "Reference", type: "IMAGE" }, { id: "prompt", name: "Prompt", type: "STRING" }],
    outputs: [{ id: "image", name: "Image", type: "IMAGE" }],
    defaultParams: { steps: 28, cfg: 4.5, denoise: 0.75, preserve_face: true }
  },
  realesrgan: {
    title: "RealESRGAN Upscale",
    icon: "↗",
    inputs: [{ id: "input", name: "Input", type: "ANY" }],
    outputs: [{ id: "output", name: "Upscaled", type: "ANY" }],
    defaultParams: { scale: 4, restore_face: true, denoise: 0.3 }
  },
  output_video: {
    title: "Output Video",
    icon: "□",
    inputs: [{ id: "video", name: "Video In", type: "VIDEO" }, { id: "image", name: "Image In", type: "IMAGE" }],
    outputs: [],
    defaultParams: { codec: "h264", bitrate: "12M", format: "mp4" }
  }
};

let currentWorkflow = {
  id: "wf_wan21_motion",
  name: "Wan 2.1 Video Motion Studio",
  description: "Sao chép chuyển động video mẫu và tạo video chân thực từ ảnh nhân vật bằng Wan 2.1.",
  nodes: [],
  links: []
};

let allWorkflows = [];
let connectingPort = null;
let zoomLevel = 1;
let panOffset = { x: 0, y: 0 };
let selectedNodeId = null;

function createStarterWorkflow() {
  return {
    id: "wf_wan21_motion",
    name: "Wan 2.1 Video Motion Studio",
    description: "Sao chép chuyển động video mẫu và tạo video chân thực từ ảnh nhân vật bằng Wan 2.1.",
    published: true,
    nodes: [
      { id: "node_1", type: "input_image", title: "Ảnh Nhân Vật Gốc", x: 60, y: 120, params: { slot: "character_image" } },
      { id: "node_2", type: "input_prompt", title: "Prompt Đầu Vào", x: 60, y: 330, params: { prompt: "Cinematic portrait, 4k, natural motion, realistic lighting" } },
      { id: "node_3", type: "wan_video", title: "Wan 2.1 Video", x: 420, y: 200, params: { steps: 30, cfg: 6.5, seed: 1234, denoise: 0.85 } },
      { id: "node_4", type: "output_video", title: "Xuất Video", x: 820, y: 200, params: { codec: "h264", format: "mp4" } }
    ],
    links: [
      { id: "link_1", from_node: "node_1", from_port: "image", to_node: "node_3", to_port: "image" },
      { id: "link_2", from_node: "node_2", from_port: "text", to_node: "node_3", to_port: "prompt" },
      { id: "link_3", from_node: "node_3", from_port: "video", to_node: "node_4", to_port: "video" }
    ]
  };
}

function validateCurrentWorkflow({ forPublish = false } = {}) {
  const name = (currentWorkflow?.name || $('#wfTitleInput')?.value || '').trim();
  if (!name) {
    return { ok: false, message: 'Workflow cần có tên trước khi lưu hoặc xuất bản.' };
  }
  const nodeIds = new Set((currentWorkflow?.nodes || []).map(node => node.id));
  const invalidLinks = (currentWorkflow?.links || []).filter(link => !nodeIds.has(link.from_node) || !nodeIds.has(link.to_node));
  if ((currentWorkflow?.nodes || []).length === 0) {
    return { ok: false, message: forPublish ? 'Workflow trống. Thêm ít nhất 1 node trước khi xuất bản.' : 'Workflow đang trống. Thêm node trước khi lưu.' };
  }
  if (invalidLinks.length > 0) {
    return { ok: false, message: 'Có liên kết tham chiếu tới node không tồn tại. Hãy xóa hoặc sửa kết nối.' };
  }
  return { ok: true };
}

async function saveCurrentWorkflow() {
  const validation = validateCurrentWorkflow();
  if (!validation.ok) {
    say(validation.message);
    return false;
  }
  currentWorkflow.name = ($('#wfTitleInput').value || '').trim() || currentWorkflow.name || 'Workflow AI';
  try {
    const res = await api('/api/admin/workflows', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(currentWorkflow)
    });
    say('Lưu workflow thành công!');
    currentWorkflow = JSON.parse(JSON.stringify(res.workflow || currentWorkflow));
    await loadWorkflowsList();
    if ($('#wfSelector')) $('#wfSelector').value = currentWorkflow.id;
    return true;
  } catch (e) {
    say('Lỗi khi lưu: ' + e.message);
    return false;
  }
}

async function publishCurrentWorkflow() {
  const validation = validateCurrentWorkflow({ forPublish: true });
  if (!validation.ok) {
    say(validation.message);
    return false;
  }
  if (!confirm('Bạn muốn xuất bản workflow này ra trang chủ?')) return false;
  try {
    const res = await api(`/api/admin/workflows/${currentWorkflow.id}/publish`, { method: 'POST' });
    say(res.message || 'Xuất bản workflow thành công!');
    await loadWorkflowsList();
    return true;
  } catch (e) {
    say('Lỗi khi xuất bản: ' + e.message);
    return false;
  }
}

function renderTemplateCards() {
  const strip = $('#wfTemplateStrip');
  if (!strip) return;
  const workflows = Array.isArray(allWorkflows) && allWorkflows.length ? allWorkflows : [currentWorkflow].filter(Boolean);
  strip.innerHTML = workflows.map((wf) => {
    const active = currentWorkflow && wf.id === currentWorkflow.id ? 'active' : '';
    const nodeCount = Array.isArray(wf.nodes) ? wf.nodes.length : 0;
    const linkCount = Array.isArray(wf.links) ? wf.links.length : 0;
    return `
      <button type="button" class="wf-template-card ${active}" data-workflow-id="${wf.id}">
        <div class="wf-template-card-header">
          <span class="wf-template-tag">${wf.published ? 'Published' : 'Draft'}</span>
          <span class="wf-template-node-count">${nodeCount} nodes</span>
        </div>
        <strong>${(wf.name || 'Workflow').slice(0, 28)}</strong>
        <small>${(wf.description || 'Workflow AI').slice(0, 70)}</small>
        <div class="wf-template-stats"><span>${linkCount} links</span><span>${wf.published ? 'Ready' : 'Editing'}</span></div>
      </button>
    `;
  }).join('');

  strip.querySelectorAll('.wf-template-card').forEach((card) => {
    card.addEventListener('click', () => {
      const id = card.dataset.workflowId;
      const wf = allWorkflows.find(item => item.id === id) || currentWorkflow;
      if (!wf) return;
      currentWorkflow = JSON.parse(JSON.stringify(wf));
      selectedNodeId = null;
      $('#wfTitleInput').value = currentWorkflow.name || '';
      $('#wfSelector').value = currentWorkflow.id;
      renderWorkflowGraph();
      renderTemplateCards();
    });
  });
}

async function initWorkflowStudio() {
  await loadWorkflowsList();
  bindStudioEvents();
  renderWorkflowGraph();
}

async function loadWorkflowsList() {
  try {
    allWorkflows = await api('/api/admin/workflows');
    const sel = $('#wfSelector');
    if (!Array.isArray(allWorkflows) || allWorkflows.length === 0) {
      currentWorkflow = createStarterWorkflow();
      sel.innerHTML = `<option value="${currentWorkflow.id}">${currentWorkflow.name}</option>`;
      $('#wfTitleInput').value = currentWorkflow.name || '';
      renderTemplateCards();
      renderWorkflowGraph();
      return;
    }
    sel.innerHTML = allWorkflows.map(w => `<option value="${w.id}">${w.name} ${w.published ? ' (Đã xuất bản)' : ''}</option>`).join('');
    currentWorkflow = JSON.parse(JSON.stringify(allWorkflows[0]));
    $('#wfTitleInput').value = currentWorkflow.name || '';
    renderTemplateCards();
    renderWorkflowGraph();
  } catch (e) {
    say('Không tải được danh sách workflow: ' + e.message);
    currentWorkflow = createStarterWorkflow();
    $('#wfTitleInput').value = currentWorkflow.name || '';
    renderTemplateCards();
    renderWorkflowGraph();
  }
}

function bindStudioEvents() {
  $('#wfSelector').addEventListener('change', e => {
    const w = allWorkflows.find(x => x.id === e.target.value);
    if (w) {
      currentWorkflow = JSON.parse(JSON.stringify(w));
      $('#wfTitleInput').value = currentWorkflow.name || '';
      renderWorkflowGraph();
      say(`Đã nạp: ${w.name}`);
    }
  });

  $('#wfTitleInput').addEventListener('input', e => {
    currentWorkflow.name = e.target.value;
  });

  $('#wfBtnNew').addEventListener('click', () => {
    currentWorkflow = {
      id: "wf_" + Math.random().toString(36).substring(2, 8),
      name: "Workflow Mới " + new Date().toLocaleTimeString('vi-VN'),
      description: "Quy trình AI tùy chỉnh",
      nodes: [
        { id: "node_1", type: "input_image", title: "Ảnh Đầu Vào", x: 60, y: 120, params: { slot: "character_image" } },
        { id: "node_2", type: "input_prompt", title: "Prompt Đầu Vào", x: 60, y: 340, params: { prompt: "Cinematic portrait, 4k" } },
        { id: "node_3", type: "wan_video", title: "Wan 2.1 Video", x: 420, y: 180, params: { steps: 30, cfg: 6.5, seed: 1234, denoise: 0.85 } },
        { id: "node_4", type: "output_video", title: "Xuất Video", x: 800, y: 180, params: { codec: "h264", format: "mp4" } }
      ],
      links: [
        { id: "link_1", from_node: "node_1", from_port: "image", to_node: "node_3", to_port: "image" },
        { id: "link_2", from_node: "node_2", from_port: "text", to_node: "node_3", to_port: "prompt" },
        { id: "link_3", from_node: "node_3", from_port: "video", to_node: "node_4", to_port: "video" }
      ]
    };
    $('#wfTitleInput').value = currentWorkflow.name;
    renderWorkflowGraph();
    say("Đã tạo đồ thị mới");
  });

  $('#wfBtnDuplicate').addEventListener('click', () => {
    const clone = JSON.parse(JSON.stringify(currentWorkflow));
    clone.id = "wf_" + Math.random().toString(36).substring(2, 8);
    clone.name += " (Bản sao)";
    currentWorkflow = clone;
    $('#wfTitleInput').value = currentWorkflow.name;
    renderWorkflowGraph();
    say("Đã nhân bản workflow");
  });

  $('#wfBtnImport').addEventListener('click', () => $('#wfImportFile').click());
  $('#wfImportFile').addEventListener('change', async (event) => {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    try {
      await importWorkflowFile(file);
    } catch (e) {
      say('Lỗi import workflow: ' + e.message);
    } finally {
      event.target.value = '';
    }
  });
  $('#wfBtnExport').addEventListener('click', exportCurrentWorkflow);

  $('#wfBtnClear').addEventListener('click', () => {
    if (confirm('Xóa toàn bộ node và kết nối hiện tại?')) {
      currentWorkflow.nodes = [];
      currentWorkflow.links = [];
      renderWorkflowGraph();
    }
  });

  $('#wfBtnSave').addEventListener('click', async () => {
    await saveCurrentWorkflow();
  });

  $('#wfBtnPublish').addEventListener('click', async () => {
    await publishCurrentWorkflow();
  });

  $('#wfBtnRun').addEventListener('click', runWorkflowTest);

  document.addEventListener('keydown', (event) => {
    const target = event.target;
    const isTyping = target && ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName);
    if (isTyping) return;

    const metaKey = event.ctrlKey || event.metaKey;
    if (metaKey && event.key.toLowerCase() === 's') {
      event.preventDefault();
      saveCurrentWorkflow();
      return;
    }
    if (metaKey && event.key.toLowerCase() === 'p') {
      event.preventDefault();
      publishCurrentWorkflow();
      return;
    }
    if ((event.key === 'Delete' || event.key === 'Backspace') && selectedNodeId) {
      event.preventDefault();
      deleteNode(selectedNodeId);
      selectedNodeId = null;
    }
    if (event.key.toLowerCase() === 'n' && !metaKey) {
      const type = 'wan_video';
      addNodeToCanvas(type, 180 + Math.random() * 180, 160 + Math.random() * 150);
    }
  });

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
    $('#wfTerminal').innerHTML = '<div class="log-line dim">Log console đã được xóa.</div>';
  });

  $('#wfToggleLogs').addEventListener('click', () => {
    const body = $('#wfLogBody');
    body.style.display = body.style.display === 'none' ? 'block' : 'none';
  });
}

async function importWorkflowFile(file) {
  const text = await file.text();
  let json;
  try {
    json = JSON.parse(text);
  } catch {
    throw new Error('File không hợp lệ, phải là JSON workflow.');
  }

  const response = await fetch('/api/admin/workflows/import', {
    method: 'POST',
    body: (() => {
      const form = new FormData();
      form.append('file', file);
      return form;
    })()
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || 'Import workflow thất bại');
  }

  const imported = Array.isArray(payload.workflow) ? payload.workflow[0] : payload.workflow;
  if (!imported) {
    throw new Error('Không tìm thấy workflow để import');
  }

  currentWorkflow = JSON.parse(JSON.stringify(imported));
  $('#wfTitleInput').value = currentWorkflow.name || '';
  await loadWorkflowsList();
  $('#wfSelector').value = currentWorkflow.id;
  renderWorkflowGraph();
  say(`Đã import workflow: ${currentWorkflow.name}`);
}

async function exportCurrentWorkflow() {
  const workflowId = currentWorkflow?.id || $('#wfSelector')?.value;
  if (!workflowId) {
    say('Chưa có workflow chọn để xuất');
    return;
  }

  const response = await fetch(`/api/admin/workflows/export?workflow_id=${encodeURIComponent(workflowId)}`);
  const blob = await response.blob();
  if (!response.ok) {
    const text = await blob.text().catch(() => '');
    throw new Error(text || 'Xuất workflow thất bại');
  }

  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${(currentWorkflow.name || 'workflow').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'workflow'}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
  say('Đã xuất workflow JSON thành công');
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
    const schema = NODE_DEFS[node.type] || { title: node.title, icon: "•", inputs: [], outputs: [] };
    const el = document.createElement('div');
    el.className = 'wf-node' + (selectedNodeId === node.id ? ' selected' : '');
    el.id = 'dom_' + node.id;
    el.style.left = node.x + 'px';
    el.style.top = node.y + 'px';
    el.addEventListener('click', () => {
      selectedNodeId = node.id;
      renderWorkflowGraph();
    });

    const head = document.createElement('div');
    head.className = 'wf-node-head';
    head.innerHTML = `
      <div class="wf-node-title"><span>${schema.icon}</span> <span>${node.title || schema.title}</span></div>
      <button type="button" class="wf-node-close" title="Xóa Node">×</button>
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
        <label>Tỷ lệ phóng to:</label>
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
        <label>Mục đích ảnh:</label>
        <select>
          <option value="character_image">Ảnh nhân vật chính</option>
          <option value="outfit_reference">Ảnh trang phục</option>
          <option value="background_image">Ảnh bối cảnh</option>
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
  if (!head) return;
  let startX = 0, startY = 0, initialX = 0, initialY = 0;

  head.addEventListener('mousedown', e => {
    selectedNodeId = node.id;
    renderWorkflowGraph();
    startX = e.clientX;
    startY = e.clientY;
    initialX = node.x;
    initialY = node.y;
    const nodeEl = e.currentTarget.closest('.wf-node');
    if (nodeEl) nodeEl.classList.add('dragging');

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
      const nodeEl = document.getElementById('dom_' + node.id);
      if (nodeEl) nodeEl.classList.remove('dragging');
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
      path.title = 'Click để xóa đường nối này';

      path.addEventListener('click', e => {
        e.stopPropagation();
        deleteLink(link.id);
        say('Đã xóa đường liên kết');
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
  btn.textContent = 'Đang chạy pipeline...';
  status.textContent = 'Đang xử lý';
  status.style.background = 'rgba(245, 158, 11, 0.2)';
  status.style.borderColor = 'rgba(245, 158, 11, 0.5)';
  status.style.color = '#fbbf24';

  term.innerHTML = '<div class="log-line info">Đang khởi động pipeline đồ thị: ' + (currentWorkflow.name || 'Workflow') + '...</div>';

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

    if (!res.preview_url || res.status !== 'success') {
      throw new Error(res.message || 'GPU chưa trả về kết quả thật');
    }
    status.textContent = 'Thành công';
    status.style.background = 'rgba(16, 185, 129, 0.2)';
    status.style.borderColor = 'rgba(16, 185, 129, 0.5)';
    status.style.color = '#6ee7b7';

    $('#wfPreviewPlaceholder').style.display = 'none';
    $('#wfPreviewContent').style.display = 'flex';
    const video = $('#wfPreviewVideo');
    video.src = res.preview_url;
    video.poster = res.poster_url || '';
    video.load();
    video.play().catch(() => {});

    $('#wfPreviewTiming').textContent = `Thời gian xử lý: ${res.execution_time_sec || '—'}s`;
    $('#wfPreviewDownload').href = res.preview_url;

    say('Chạy thử workflow thành công');
  } catch (e) {
    const errLine = document.createElement('div');
    errLine.className = 'log-line export';
    errLine.textContent = `[ERROR] Thực thi thất bại: ${e.message}`;
    term.appendChild(errLine);
    status.textContent = 'Lỗi';
    status.style.color = '#ff7583';
    say('Lỗi test run: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = 'Chạy Thử Nghiệm (Test Run)';
  }
}

$('#refresh').onclick = load;
$('#logout').onclick = async () => {
  await fetch('/api/logout', { method: 'POST' });
  location.href = '/';
};

boot();