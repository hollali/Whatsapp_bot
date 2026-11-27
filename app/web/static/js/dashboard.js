const API = '/api/v1';
const MONTHLY_LIMIT = 1000;
const state = {
  mode: 'now',
  days: 7,
  jobs: [],
  contacts: [],
  groups: [],
  templates: [],
  messageFilter: 'all',
  modalType: null,
  editingId: null,
  seenFailures: loadSeen(),
  socket: null,
  polling: false,
  manualMessage: false,
  lastSilent: 0,
};

const $ = id => document.getElementById(id);

function loadSeen() {
  try { return new Set(JSON.parse(localStorage.getItem('wappulse.seenFailures') || '[]')); }
  catch (e) { return new Set(); }
}

function saveSeen() {
  try { localStorage.setItem('wappulse.seenFailures', JSON.stringify([...state.seenFailures])); }
  catch (e) { /* storage disabled */ }
}

async function api(path, options = {}) {
  const opts = {
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    ...options,
  };
  const res = await fetch(API + path, opts);
  let data = null;
  try { data = await res.json(); } catch (e) { /* no body */ }
  if (res.status === 401 && !path.startsWith('/auth/login')) {
    window.location.href = '/login';
    throw new Error('Session expired');
  }
  if (!res.ok) throw new Error((data && (data.error || data.message)) || 'Request failed (' + res.status + ')');
  return data;
}

function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[c]));
}

function fmt(iso) {
  if (!iso) return '—';
  const d = new Date(String(iso).replace(' ', 'T'));
  if (isNaN(d)) return esc(iso);
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function badge(status) {
  const map = {
    success: ['badge-success', 'Delivered'], completed: ['badge-success', 'Completed'],
    failed: ['badge-danger', 'Failed'], running: ['badge-info', 'Running'],
    pending: ['badge-warning', 'Pending'], scheduled: ['badge-info', 'Scheduled'], paused: ['badge-warning', 'Paused'],
    cancelled: ['badge-accent', 'Cancelled'], draft: ['', 'Draft'],
  };
  const [cls, label] = map[status] || ['', status || '—'];
  return '<span class="badge ' + cls + '"><i class="dot"></i>' + esc(label) + '</span>';
}

function emptyBox(title, text, action) {
  const button = action && action.goto
    ? '<button class="btn btn-primary btn-sm" data-goto="' + esc(action.goto) + '">' + esc(action.label) + '</button>'
    : '';
  return '<div class="empty"><div class="empty-icon"><svg class="icon icon-lg"><use href="#i-message-square"></use></svg></div>' +
    '<h3>' + esc(title) + '</h3><p>' + esc(text) + '</p>' +
    (button ? '<div style="margin-top:16px">' + button + '</div>' : '') + '</div>';
}

function emptyRow(colspan, title, text, action) {
  return '<tr><td colspan="' + colspan + '">' + emptyBox(title, text, action) + '</td></tr>';
}

function loadingRow(colspan) {
  return '<tr><td colspan="' + colspan + '"><div class="table-loading"><div class="loading-line"></div><span>Loading…</span></div></td></tr>';
}

function setTableLoading(id, colspan) {
  const el = $(id);
  if (el) el.innerHTML = loadingRow(colspan);
}

function shortId(id) { return id ? String(id).slice(0, 8) : '—'; }

/* ---------- Charts & providers ---------- */
function renderChart(elementId, buckets, days) {
  const el = $(elementId);
  if (!el) return;
  const today = new Date();
  const points = [];
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(Date.UTC(today.getUTCFullYear(), today.getUTCMonth(), today.getUTCDate() - i));
    const key = d.toISOString().slice(0, 10);
    const label = days <= 7
      ? d.toLocaleDateString(undefined, { weekday: 'short', timeZone: 'UTC' })
      : d.toLocaleDateString(undefined, { month: 'numeric', day: 'numeric', timeZone: 'UTC' });
    points.push({ key, label, success: b.success || 0, failed: b.failed || 0 });
  }
  if (!points.some(p => p.success || p.failed)) {
    el.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--muted);font-size:12.5px;text-align:center">No deliveries yet — messages you send will show up here.</div>';
    return;
  }
  const max = Math.max(1, ...points.map(p => p.success + p.failed));
  el.innerHTML = points.map(p => {
    const s = Math.max(p.success ? 4 : 2, Math.round(p.success / max * 100));
    const f = Math.max(p.failed ? 4 : 2, Math.round(p.failed / max * 100));
    const title = p.key + ' — ' + p.success + ' delivered, ' + p.failed + ' failed';
    return '<div class="chart-col"><div class="chart-bars">' +
      '<span class="chart-bar success" style="height:' + s + '%" title="' + esc(title) + '"></span>' +
      '<span class="chart-bar failed" style="height:' + f + '%" title="' + esc(title) + '"></span>' +
      '</div><span class="chart-label">' + esc(p.label) + '</span></div>';
  }).join('');
}

function renderProviders(elementId, list) {
  const el = $(elementId);
  if (!el) return;
  if (!list || !list.length) {
    el.innerHTML = emptyBox('No providers', 'Provider status is unavailable right now.');
    return;
  }
  el.innerHTML = list.map(p => {
    const ok = !!p.ok;
    const name = String(p.provider || 'Provider').replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
    const detail = String(p.detail || p.error || p.message || (ok ? 'Ready to send' : 'Not configured'))
      .replace(/\\n/g, ' ').replace(/\s+/g, ' ').trim();
    const short = detail.length > 64 ? detail.slice(0, 64) + '…' : detail;
    return '<div class="provider"><span class="provider-icon"><svg class="icon icon-sm"><use href="#i-zap"></use></svg></span>' +
      '<span><strong>' + esc(name) + '</strong><small title="' + esc(detail) + '">' + esc(short) + '</small></span>' +
      '<span class="status-dot ' + (ok ? 'status-ok' : 'status-bad') + '"><i></i>' + (ok ? 'Online' : 'Offline') + '</span></div>';
  }).join('');
}

/* ---------- Job tables ---------- */
function jobActions(j, kind) {
  let html = '<div class="cell-actions">';
  html += '<button class="icon-action" title="Details" data-action="detail" data-kind="' + esc(kind) + '" data-id="' + esc(j.id) + '"><svg class="icon icon-sm"><use href="#i-eye"></use></svg></button>';
  if (j.status === 'failed') html += '<button class="icon-action" title="Retry" data-action="retry" data-id="' + esc(j.id) + '"><svg class="icon icon-sm"><use href="#i-refresh"></use></svg></button>';
  if (j.status === 'pending') html += '<button class="icon-action danger" title="Cancel" data-action="cancel" data-id="' + esc(j.id) + '"><svg class="icon icon-sm"><use href="#i-x"></use></svg></button>';
  html += '<button class="icon-action" title="Copy ID" data-action="copy" data-id="' + esc(j.id) + '"><svg class="icon icon-sm"><use href="#i-copy"></use></svg></button>';
  return html + '</div>';
}

function jobRows(jobs) {
  if (!jobs.length) return emptyRow(5, 'Nothing here yet', 'Messages you send will show up here.', { label: 'Compose a message', goto: 'composer' });
  return jobs.map(j =>
    '<tr><td><div class="cell-main">' + esc(j.phone) + '</div><div class="cell-sub">' + esc(shortId(j.id)) + '</div></td>' +
    '<td>' + badge(j.status) + (j.last_error ? '<div class="cell-sub error-text" title="' + esc(j.last_error) + '">' + esc(String(j.last_error).slice(0, 48)) + '…</div>' : '') + '</td>' +
    '<td>' + (j.attempts || 0) + ' / ' + (j.max_attempts || 3) + '</td><td>' + fmt(j.run_at) + '</td>' +
    '<td>' + jobActions(j, 'messages') + '</td></tr>' +
    '<tr class="detail-row" id="detail-messages-' + esc(j.id) + '" hidden><td colspan="5"><div class="detail-grid">' +
    '<div><span>Message</span><p>' + esc(j.message || '—') + '</p></div>' +
    '<div><span>Provider</span><p>' + esc(j.provider || '—') + '</p></div>' +
    '<div><span>Last error</span><p>' + esc(j.last_error || 'None') + '</p></div>' +
    '</div></td></tr>'
  ).join('');
}

function toggleDetail(kind, id) {
  const row = $('detail-' + kind + '-' + id);
  if (row) row.hidden = !row.hidden;
}

/* ---------- Loaders ---------- */
async function loadOverview() {
  setTableLoading('recentJobsBody', 5);
  const [summary, timeline, providers, monthly, jobs] = await Promise.all([
    api('/analytics/summary'),
    api('/analytics/timeline?days=7'),
    api('/analytics/providers'),
    api('/analytics/timeline?days=30'),
    api('/messages/jobs'),
  ]);
  $('statPending').textContent = summary.pending_jobs ?? 0;
  $('statDelivered').textContent = summary.delivery?.success ?? 0;
  $('statFailed').textContent = summary.delivery?.failed ?? 0;
  $('statCampaigns').textContent = summary.campaigns ?? 0;
  $('composerDelivered').textContent = summary.delivery?.success ?? 0;
  renderChart('overviewChart', timeline, 7);
  renderProviders('overviewProviders', providers);
  $('recentJobsBody').innerHTML = jobRows(jobs.slice(0, 5));
  updatePlanUsage(monthly);
  state.jobs = jobs;
  renderNotifications();
}

function updatePlanUsage(buckets) {
  const used = Object.values(buckets || {}).reduce((n, b) => n + (b.success || 0) + (b.failed || 0), 0);
  const pct = Math.min(100, Math.round(used / MONTHLY_LIMIT * 100));
  $('planUsage').textContent = used.toLocaleString() + ' of ' + MONTHLY_LIMIT.toLocaleString() + ' monthly messages';
  $('planBar').style.width = pct + '%';
}

function renderNotifications() {
  const list = $('notifList');
  if (!list) return;
  const failed = state.jobs.filter(j => j.status === 'failed');
  const pending = state.jobs.filter(j => j.status === 'pending' || j.status === 'running');
  const unseen = failed.filter(j => !state.seenFailures.has(j.id));
  $('notifDot').hidden = unseen.length === 0;
  const items = [];
  if (unseen.length) {
    items.push('<div class="notif-item"><span class="notif-icon fi-rose"><svg class="icon icon-sm"><use href="#i-x-circle"></use></svg></span>' +
      '<span><strong>' + unseen.length + ' delivery' + (unseen.length === 1 ? '' : 'ies') + ' failed</strong>' +
      '<small>' + esc(String(unseen[0].last_error || 'Check the message details').slice(0, 70)) + '</small></span></div>');
  }
  if (pending.length) {
    items.push('<div class="notif-item"><span class="notif-icon fi-amber"><svg class="icon icon-sm"><use href="#i-clock"></use></svg></span>' +
      '<span><strong>' + pending.length + ' message' + (pending.length === 1 ? '' : 's') + ' in the queue</strong><small>Workers are picking these up automatically</small></span></div>');
  }
  if (!items.length) {
    list.innerHTML = '<div class="dropdown-empty">You are all caught up.</div>';
    return;
  }
  list.innerHTML = items.join('') +
    '<button class="dropdown-foot" data-goto="messages">View messages <svg class="icon icon-sm"><use href="#i-arrow-right"></use></svg></button>';
}

async function loadComposer() {
  const [templates, providers] = await Promise.all([api('/templates'), api('/analytics/providers')]);
  state.templates = templates;
  const select = $('templateSelect');
  const selected = select.value;
  select.innerHTML = '<option value="">Write your own message</option>' + templates.map(t =>
    '<option value="' + esc(t.id) + '" data-body="' + esc(t.body) + '">' + esc(t.name) + '</option>'
  ).join('');
  select.value = selected;
  const provider = $('providerSelect');
  provider.innerHTML = '';
  providers.forEach(p => {
    const opt = document.createElement('option');
    opt.value = p.provider;
    opt.textContent = p.provider.replace(/_/g, ' ') + (p.ok ? '' : ' (offline)');
    opt.disabled = !p.ok;
    provider.appendChild(opt);
  });
  if (!provider.value) {
    const fallback = document.createElement('option');
    fallback.value = 'pywhatkit';
    fallback.textContent = 'pywhatkit';
    provider.appendChild(fallback);
  }
  const offline = providers.filter(p => !p.ok).map(p => p.provider.replace(/_/g, ' '));
  $('providerHint').textContent = offline.length
    ? 'Unavailable right now: ' + offline.join(', ') + '. Configure them to enable sending.'
    : 'All providers are online.';
  renderTemplateVariables();
}

function templateContext() {
  const ctx = {};
  document.querySelectorAll('#templateVarsFields .var-input').forEach(input => {
    if (input.value.trim()) ctx[input.dataset.var] = input.value.trim();
  });
  return ctx;
}

function renderTemplateVariables() {
  const t = state.templates.find(x => x.id === $('templateSelect').value);
  const vars = t && t.variables ? t.variables.split(',').map(v => v.trim()).filter(Boolean) : [];
  $('templateVarsFields').innerHTML = vars.map(v =>
    '<div class="form-field"><label>' + esc(v) + '</label><input class="form-control var-input" data-var="' + esc(v) + '" placeholder="Value for ' + esc(v) + '"></div>'
  ).join('');
  $('templateVarsField').hidden = !vars.length;
  applyTemplate();
}

function applyTemplate() {
  const t = state.templates.find(x => x.id === $('templateSelect').value);
  if (!t || state.manualMessage) return;
  const ctx = templateContext();
  const rendered = t.body.replace(/{{\s*([\w.]+)\s*}}/g, (match, key) => (ctx[key] != null ? ctx[key] : match));
  $('messageInput').value = rendered;
  updateMessageCount();
}

function updateMessageCount() {
  const text = $('messageInput').value;
  $('messageCount').textContent = text.length + ' chars';
  $('messagePreviewField').hidden = !$('templateSelect').value || !text;
  $('messagePreview').textContent = text;
  $('messageHint').textContent = text.length > 160
    ? 'Long messages can be harder to read on mobile — consider trimming.'
    : 'Tip: keep it short and personal for better reply rates.';
}

function clearComposer() {
  $('sendForm').reset();
  $('templateVarsFields').innerHTML = '';
  $('templateVarsField').hidden = true;
  $('messagePreviewField').hidden = true;
  $('scheduleGroup').style.display = 'none';
  state.mode = 'now';
  state.manualMessage = false;
  document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('active', b.dataset.mode === 'now'));
  $('sendSubmit').innerHTML = '<svg class="icon icon-sm"><use href="#i-send"></use></svg> Send now';
  updateMessageCount();
}

async function loadMessages() {
  setTableLoading('jobsBody', 5);
  state.jobs = await api('/messages/jobs');
  renderJobs();
  renderNotifications();
}

function renderJobs() {
  const search = ($('messagesSearch')?.value || '').toLowerCase();
  const filtered = state.jobs.filter(j => {
    const statusOk = state.messageFilter === 'all' || j.status === state.messageFilter;
    const searchOk = !search || (j.phone || '').toLowerCase().includes(search) || (j.id || '').includes(search) || (j.message || '').toLowerCase().includes(search);
    return statusOk && searchOk;
  });
  $('jobsBody').innerHTML = jobRows(filtered);
}

async function loadCampaigns() {
  setTableLoading('campaignsBody', 6);
  const items = await api('/campaigns');
  const body = $('campaignsBody');
  if (!items.length) { body.innerHTML = emptyRow(6, 'No campaigns yet', 'Create a campaign to broadcast to your contacts.', { label: 'New campaign', goto: 'campaigns' }); return; }
  body.innerHTML = items.map(c => {
    const canLaunch = c.status === 'draft' || c.status === 'failed';
    return '<tr><td><div class="cell-main">' + esc(c.name) + '</div><div class="cell-sub">' + esc(shortId(c.id)) + '</div></td>' +
      '<td>' + badge(c.status) + '</td><td>' + (c.total || 0) + '</td><td>' + (c.sent || 0) + '</td><td>' + (c.failed || 0) + '</td>' +
      '<td><div class="cell-actions">' +
      (canLaunch ? '<button class="icon-action" title="Launch to a group" data-action="launch-campaign" data-id="' + esc(c.id) + '" data-name="' + esc(c.name) + '"><svg class="icon icon-sm"><use href="#i-play"></use></svg></button>' : '') +
      (c.status === 'running' || c.status === 'scheduled' ? '<button class="icon-action" title="Pause" data-action="pause-campaign" data-id="' + esc(c.id) + '"><svg class="icon icon-sm"><use href="#i-pause"></use></svg></button>' : '') +
      (c.status === 'paused' ? '<button class="icon-action" title="Resume" data-action="resume-campaign" data-id="' + esc(c.id) + '"><svg class="icon icon-sm"><use href="#i-play"></use></svg></button>' : '') +
      '<button class="icon-action danger" title="Delete" data-action="delete-campaign" data-id="' + esc(c.id) + '"><svg class="icon icon-sm"><use href="#i-trash"></use></svg></button>' +
      '</div></td></tr>';
  }).join('');
}

async function loadContacts() {
  setTableLoading('contactsBody', 5);
  const [items, groups] = await Promise.all([api('/contacts'), api('/contacts/groups')]);
  state.contacts = items;
  state.groups = groups;
  const filter = $('contactsGroupFilter');
  filter.innerHTML = '<option value="">All groups</option>' + groups.map(g =>
    '<option value="' + esc(g.id) + '">' + esc(g.name) + '</option>'
  ).join('');
  renderContacts();
}

function renderContacts() {
  const search = ($('contactsSearch')?.value || '').toLowerCase();
  const group = $('contactsGroupFilter')?.value || '';
  const items = state.contacts.filter(c =>
    (!group || c.group_id === group) && (!search ||
      (c.name || '').toLowerCase().includes(search) ||
      (c.phone || '').toLowerCase().includes(search) ||
      (c.email || '').toLowerCase().includes(search))
  );
  const body = $('contactsBody');
  if (!items.length) { body.innerHTML = emptyRow(5, 'No contacts found', 'Add a contact, import a CSV or adjust your search.', { label: 'Add contact', goto: 'contacts' }); return; }
  const groupName = id => (state.groups.find(g => g.id === id) || {}).name || '';
  body.innerHTML = items.map(c =>
    '<tr><td><div class="cell-main">' + esc(c.name || 'Unnamed') + '</div>' +
    (c.tags || groupName(c.group_id) ? '<div class="cell-sub">' + esc([groupName(c.group_id), c.tags].filter(Boolean).join(' · ')) + '</div>' : '') + '</td>' +
    '<td>' + esc(c.phone) + '</td><td>' + esc(c.email || '—') + '</td>' +
    '<td>' + (c.opted_out ? '<span class="badge badge-danger">Opted out</span>' : '<span class="badge badge-success">Active</span>') + '</td>' +
    '<td><div class="cell-actions"><button class="icon-action" title="Edit" data-action="edit-contact" data-id="' + esc(c.id) + '"><svg class="icon icon-sm"><use href="#i-template"></use></svg></button>' +
    '<button class="icon-action danger" title="Delete" data-action="delete-contact" data-id="' + esc(c.id) + '"><svg class="icon icon-sm"><use href="#i-trash"></use></svg></button></div></td></tr>'
  ).join('');
}

async function loadTemplates() {
  setTableLoading('templatesBody', 4);
  const items = await api('/templates');
  const body = $('templatesBody');
  if (!items.length) { body.innerHTML = emptyRow(4, 'No templates yet', 'Create a reusable message with variables.', { label: 'New template', goto: 'templates' }); return; }
  body.innerHTML = items.map(t =>
    '<tr><td><div class="cell-main">' + esc(t.name) + '</div></td>' +
    '<td style="max-width:320px"><div class="cell-sub" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis">' + esc(t.body) + '</div></td>' +
    '<td>' + (t.variables ? t.variables.split(',').filter(Boolean).map(v => '<span class="badge badge-accent">' + esc(v.trim()) + '</span>').join(' ') : '<span style="color:var(--muted)">—</span>') + '</td>' +
    '<td><div class="cell-actions"><button class="icon-action" title="Edit" data-action="edit-template" data-id="' + esc(t.id) + '"><svg class="icon icon-sm"><use href="#i-template"></use></svg></button>' +
    '<button class="icon-action danger" title="Delete" data-action="delete-template" data-id="' + esc(t.id) + '"><svg class="icon icon-sm"><use href="#i-trash"></use></svg></button></div></td></tr>'
  ).join('');
}

async function loadSchedules() {
  setTableLoading('schedulesBody', 5);
  const status = $('schedulesStatusFilter')?.value || '';
  const items = await api('/schedules' + (status ? '?status=' + encodeURIComponent(status) : ''));
  const body = $('schedulesBody');
  if (!items.length) { body.innerHTML = emptyRow(5, 'Nothing scheduled', 'Use Compose → Schedule to queue a message.', { label: 'Schedule a message', goto: 'composer' }); return; }
  body.innerHTML = items.map(j =>
    '<tr><td><div class="cell-main">' + esc(j.phone) + '</div><div class="cell-sub">' + esc(shortId(j.id)) + '</div></td>' +
    '<td>' + badge(j.status) + '</td><td>' + fmt(j.run_at) + '</td><td>' + (j.attempts || 0) + ' / ' + (j.max_attempts || 3) + '</td>' +
    '<td><div class="cell-actions"><button class="icon-action" title="Details" data-action="detail" data-kind="schedules" data-id="' + esc(j.id) + '"><svg class="icon icon-sm"><use href="#i-eye"></use></svg></button>' +
    '<button class="icon-action danger" title="Delete" data-action="delete-schedule" data-id="' + esc(j.id) + '"><svg class="icon icon-sm"><use href="#i-trash"></use></svg></button></div></td></tr>' +
    '<tr class="detail-row" id="detail-schedules-' + esc(j.id) + '" hidden><td colspan="5"><div class="detail-grid"><div><span>Message</span><p>' + esc(j.message || '—') + '</p></div></div></td></tr>'
  ).join('');
}

async function loadAnalytics() {
  const [summary, timeline, providers] = await Promise.all([
    api('/analytics/summary'), api('/analytics/timeline?days=' + state.days), api('/analytics/providers'),
  ]);
  const d = summary.delivery || {};
  const rate = d.total ? Math.round(d.success / d.total * 100) : 0;
  $('aTotal').textContent = d.total ?? 0;
  $('aSuccess').textContent = d.success ?? 0;
  $('aFailed').textContent = d.failed ?? 0;
  $('aRate').textContent = rate + '%';
  $('timelineRange').textContent = 'Last ' + state.days + ' days';
  renderChart('analyticsChart', timeline, state.days);
  renderProviders('analyticsProviders', providers);
}

async function loadApiKeys() {
  $('apiKeysBody').innerHTML = '<div class="provider-list"><div class="loading-line"></div></div>';
  const keys = await api('/auth/api-keys');
  state.apiKeys = keys;
  const body = $('apiKeysBody');
  if (!keys.length) { body.innerHTML = emptyBox('No API keys yet', 'Create a key to connect your own scripts to the API.'); return; }
  body.innerHTML = '<div class="api-key-list">' + keys.map(k =>
    '<div class="api-key-row"><span class="provider-icon"><svg class="icon icon-sm"><use href="#i-lock"></use></svg></span>' +
    '<span><strong>' + esc(k.name) + '</strong><small>' + esc(k.prefix) + '••••••••</small></span>' +
    '<button class="icon-action danger" title="Revoke key" data-action="revoke-key" data-id="' + esc(k.id) + '"><svg class="icon icon-sm"><use href="#i-trash"></use></svg></button></div>'
  ).join('') + '</div>';
}

const loaders = {
  overview: loadOverview, composer: loadComposer, messages: loadMessages, campaigns: loadCampaigns,
  contacts: loadContacts, templates: loadTemplates, schedules: loadSchedules, analytics: loadAnalytics,
  settings: loadApiKeys,
};

function refresh(view) {
  if (!loaders[view]) return;
  Promise.resolve(loaders[view]()).catch(err => toast(err.message || 'Could not load data', 'error'));
}

function currentView() {
  const el = document.querySelector('.view.active');
  return el ? el.id.replace('view-', '') : 'overview';
}

function showView(name) {
  document.querySelectorAll('.view').forEach(v => v.classList.toggle('active', v.id === 'view-' + name));
  document.querySelectorAll('.nav-item[data-view]').forEach(n => n.classList.toggle('active', n.dataset.view === name));
  closeDropdowns();
  closeDrawer();
  window.scrollTo(0, 0);
  refresh(name);
}

/* ---------- Dropdowns ---------- */
function closeDropdowns() {
  document.querySelectorAll('.dropdown.open').forEach(d => {
    d.classList.remove('open');
    d.querySelector('[aria-expanded]')?.setAttribute('aria-expanded', 'false');
  });
}

function toggleDropdown(id) {
  const el = $(id);
  if (!el) return;
  const open = el.classList.contains('open');
  closeDropdowns();
  if (!open) {
    el.classList.add('open');
    el.querySelector('[aria-expanded]')?.setAttribute('aria-expanded', 'true');
  }
}

$('notifBtn')?.addEventListener('click', () => toggleDropdown('notifDropdown'));
$('userBtn')?.addEventListener('click', () => toggleDropdown('userDropdown'));
document.addEventListener('click', e => { if (!e.target.closest('.dropdown')) closeDropdowns(); });
$('notifMarkRead')?.addEventListener('click', () => {
  state.jobs.filter(j => j.status === 'failed').forEach(j => state.seenFailures.add(j.id));
  saveSeen();
  renderNotifications();
  toast('Notifications marked as read');
});
$('userApiKeys')?.addEventListener('click', () => showView('settings'));

/* ---------- Confirmation ---------- */
let pendingConfirm = null;
function confirmAction(message, onConfirm, label) {
  $('confirmMessage').textContent = message;
  $('confirmOk').textContent = label || 'Confirm';
  pendingConfirm = onConfirm;
  $('confirmBackdrop').classList.add('open');
  document.body.classList.add('modal-open');
  $('confirmOk').focus();
}
function closeConfirm() {
  $('confirmBackdrop').classList.remove('open');
  document.body.classList.remove('modal-open');
  pendingConfirm = null;
}
$('confirmCancel')?.addEventListener('click', closeConfirm);
$('confirmBackdrop')?.addEventListener('click', e => { if (e.target === $('confirmBackdrop')) closeConfirm(); });
$('confirmOk')?.addEventListener('click', async () => {
  const fn = pendingConfirm;
  closeConfirm();
  if (fn) await fn();
});

/* ---------- Actions ---------- */
async function act(fn, success) {
  try { await fn(); toast(success); refresh(currentView()); refresh('overview'); }
  catch (err) { toast(err.message || 'Something went wrong', 'error'); }
}

async function retryJob(id) { await act(() => api('/messages/jobs/' + encodeURIComponent(id) + '/retry', { method: 'POST', body: '{}' }), 'Job queued for retry'); }
async function cancelJob(id) { confirmAction('Cancel this scheduled message?', () => act(() => api('/messages/jobs/' + encodeURIComponent(id) + '/cancel', { method: 'POST', body: '{}' }), 'Job cancelled'), 'Cancel job'); }
async function launchCampaign(id) { await act(() => api('/campaigns/' + encodeURIComponent(id) + '/launch', { method: 'POST', body: '{}' }), 'Campaign launched'); }
async function pauseCampaign(id) { await act(() => api('/campaigns/' + encodeURIComponent(id) + '/pause', { method: 'POST', body: '{}' }), 'Campaign paused'); }
async function resumeCampaign(id) { await act(() => api('/campaigns/' + encodeURIComponent(id) + '/resume', { method: 'POST', body: '{}' }), 'Campaign resumed'); }
async function deleteCampaign(id) { confirmAction('Delete this campaign and its queued jobs?', () => act(() => api('/campaigns/' + encodeURIComponent(id), { method: 'DELETE' }), 'Campaign deleted'), 'Delete'); }
async function deleteContact(id) { confirmAction('Delete this contact?', () => act(() => api('/contacts/' + encodeURIComponent(id), { method: 'DELETE' }), 'Contact deleted'), 'Delete'); }
async function deleteTemplate(id) { confirmAction('Delete this template?', () => act(() => api('/templates/' + encodeURIComponent(id), { method: 'DELETE' }), 'Template deleted'), 'Delete'); }
async function deleteSchedule(id) { confirmAction('Delete this scheduled message?', () => act(() => api('/schedules/' + encodeURIComponent(id), { method: 'DELETE' }), 'Schedule deleted'), 'Delete'); }
async function revokeApiKey(id) { confirmAction('Revoke this API key? Scripts using it will stop working.', () => act(() => api('/auth/api-keys/' + encodeURIComponent(id), { method: 'DELETE' }), 'API key revoked'), 'Revoke'); }

const actionHandlers = {
  detail: (id, btn) => toggleDetail(btn.dataset.kind, id),
  retry: id => retryJob(id),
  cancel: id => cancelJob(id),
  copy: id => copyText(id),
  'launch-campaign': (id, btn) => openLaunchCampaign(id, btn.dataset.name || id),
  'pause-campaign': id => pauseCampaign(id),
  'resume-campaign': id => resumeCampaign(id),
  'delete-campaign': id => deleteCampaign(id),
  'edit-contact': id => editContact(id),
  'delete-contact': id => deleteContact(id),
  'edit-template': id => editTemplate(id),
  'delete-template': id => deleteTemplate(id),
  'delete-schedule': id => deleteSchedule(id),
  'revoke-key': id => revokeApiKey(id),
};

document.addEventListener('click', e => {
  const btn = e.target.closest('[data-action]');
  if (!btn) return;
  const handler = actionHandlers[btn.dataset.action];
  if (!handler) return;
  e.preventDefault();
  handler(btn.dataset.id, btn);
});

function copyText(text) {
  if (navigator.clipboard) navigator.clipboard.writeText(text).then(() => toast('Copied to clipboard')).catch(() => toast('Could not copy', 'error'));
  else toast('Clipboard unavailable', 'error');
}

/* ---------- Composer ---------- */
document.querySelectorAll('[data-mode]').forEach(btn => {
  btn.addEventListener('click', () => {
    state.mode = btn.dataset.mode;
    document.querySelectorAll('[data-mode]').forEach(b => b.classList.toggle('active', b === btn));
    $('scheduleGroup').style.display = state.mode === 'schedule' ? 'block' : 'none';
    $('sendSubmit').innerHTML = state.mode === 'schedule'
      ? '<svg class="icon icon-sm"><use href="#i-calendar"></use></svg> Schedule message'
      : '<svg class="icon icon-sm"><use href="#i-send"></use></svg> Send now';
  });
});

$('templateSelect')?.addEventListener('change', () => {
  state.manualMessage = false;
  renderTemplateVariables();
});
$('templateVarsFields')?.addEventListener('input', applyTemplate);
$('messageInput')?.addEventListener('input', () => {
  state.manualMessage = true;
  updateMessageCount();
});

$('sendForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const phone = $('phoneInput').value.trim();
  const message = $('messageInput').value.trim();
  if (!phone || !message) { toast('Phone and message are required', 'error'); return; }
  if (!/^\+?[\d\s().-]{7,}$/.test(phone)) { toast('Enter a valid phone number with country code', 'error'); return; }
  const payload = { phone, message, provider: $('providerSelect').value };
  const templateId = $('templateSelect').value;
  if (templateId) { payload.template_id = templateId; payload.context = templateContext(); }
  let endpoint = '/messages/send';
  if (state.mode === 'schedule') {
    const runAt = $('runAtInput').value;
    if (!runAt) { toast('Choose a date and time', 'error'); return; }
    payload.run_at = new Date(runAt).toISOString();
    endpoint = '/messages/schedule';
  }
  const submit = $('sendSubmit');
  submit.disabled = true;
  submit.innerHTML = '<span class="spinner"></span> Working…';
  try {
    await api(endpoint, { method: 'POST', body: JSON.stringify(payload) });
    toast(state.mode === 'schedule' ? 'Message scheduled' : 'Message queued');
    clearComposer();
    refresh('overview');
    refresh('messages');
  } catch (err) { toast(err.message || 'Could not send message', 'error'); }
  finally {
    submit.disabled = false;
    submit.innerHTML = state.mode === 'schedule'
      ? '<svg class="icon icon-sm"><use href="#i-calendar"></use></svg> Schedule message'
      : '<svg class="icon icon-sm"><use href="#i-send"></use></svg> Send now';
  }
});

/* ---------- Modal forms ---------- */
const modal = $('modalBackdrop');
function modalConfig(type, item) {
  const field = (label, input) => '<div class="field"><label>' + label + '</label>' + input + '</div>';
  const input = (name, value, placeholder, extra = '') =>
    '<input name="' + name + '" class="form-control" value="' + esc(value || '') + '" placeholder="' + esc(placeholder) + '" ' + extra + '>';
  const textarea = (name, value, placeholder, hint = '') =>
    '<textarea name="' + name + '" class="form-control" rows="4" placeholder="' + esc(placeholder) + '">' + esc(value || '') + '</textarea>' +
    (hint ? '<div class="form-hint">' + esc(hint) + '</div>' : '');

  const configs = {
    campaign: {
      title: 'New campaign', submit: 'Create campaign',
      fields: field('Name', input('name', '', 'Welcome campaign', 'required')) +
        field('Message', textarea('message', '', 'Hi {{ name }}…', 'Use {{ variable }} to personalize.')) +
        field('Schedule <span style="color:var(--muted);font-weight:500">(optional)</span>', '<input name="scheduled_at" type="datetime-local" class="form-control">'),
    },
    contact: {
      title: item ? 'Edit contact' : 'Add contact', submit: item ? 'Save changes' : 'Add contact',
      fields: field('Name', input('name', item?.name, 'Full name')) +
        field('Phone', input('phone', item?.phone, '+233…', 'required')) +
        field('Email', input('email', item?.email, 'name@example.com', 'type="email"')) +
        field('Group', '<select name="group_id" class="form-control"><option value="">No group</option>' +
          state.groups.map(g => '<option value="' + esc(g.id) + '"' + (item?.group_id === g.id ? ' selected' : '') + '>' + esc(g.name) + '</option>').join('') + '</select>'),
    },
    template: {
      title: item ? 'Edit template' : 'New template', submit: item ? 'Save changes' : 'Create template',
      fields: field('Name', input('name', item?.name, 'Order update', 'required')) +
        field('Message body', textarea('body', item?.body, 'Hi {{ name }}, your order is on its way!', 'Use {{ variable }} to personalize messages.')),
    },
    launch: {
      title: 'Launch campaign', submit: 'Launch',
      fields: '<div class="launch-note">' + esc(item?.name || '') + '</div>' +
        field('Audience', '<select name="group_id" class="form-control"><option value="">All active contacts</option>' +
          state.groups.map(g => '<option value="' + esc(g.id) + '">' + esc(g.name) + '</option>').join('') + '</select>') +
        field('Or paste phone numbers <span style="color:var(--muted);font-weight:500">(optional)</span>',
          textarea('phones', '', '+233…, one per line', 'Overrides the audience selection when filled.')) +
        '<div class="form-hint">Only contacts who have not opted out will receive messages.</div>',
    },
    apikey: {
      title: 'Create API key', submit: 'Create key',
      fields: field('Name', input('name', '', 'e.g. Production script', 'required')) +
        '<div class="form-hint">The secret is shown once after creation. Store it somewhere safe.</div>',
    },
  }[type];
  return configs;
}

async function openModal(type, item) {
  if (type === 'contact' && !state.groups.length) {
    try { state.groups = await api('/contacts/groups'); } catch (e) { /* groups optional */ }
  }
  state.modalType = type;
  state.editingId = item?.id || null;
  const conf = modalConfig(type, item);
  if (!conf) return;
  $('modalTitle').textContent = conf.title;
  $('modalSubmit').textContent = conf.submit;
  $('modalFields').innerHTML = conf.fields;
  modal.classList.add('open');
  document.body.classList.add('modal-open');
  $('modalFields')?.focus();
}

function closeModal() { modal.classList.remove('open'); document.body.classList.remove('modal-open'); state.modalType = null; state.editingId = null; }

function editContact(id) {
  const item = state.contacts.find(c => c.id === id);
  if (item) openModal('contact', item);
}
function editTemplate(id) { api('/templates/' + encodeURIComponent(id)).then(t => openModal('template', t)).catch(err => toast(err.message, 'error')); }
async function openLaunchCampaign(id, name) {
  try {
    const groups = await api('/contacts/groups');
    state.groups = groups;
    openModal('launch', { id, name });
  } catch (err) { toast(err.message, 'error'); }
}

$('modalClose')?.addEventListener('click', closeModal);
$('modalCancel')?.addEventListener('click', closeModal);
modal?.addEventListener('click', e => { if (e.target === modal) closeModal(); });
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') { closeModal(); closeConfirm(); closeDropdowns(); closeDrawer(); }
});

$('modalForm')?.addEventListener('submit', async e => {
  e.preventDefault();
  const type = state.modalType;
  const data = Object.fromEntries(new FormData(e.target).entries());
  const submit = $('modalSubmit');
  submit.disabled = true;
  try {
    if (type === 'campaign') {
      if (data.scheduled_at) data.scheduled_at = new Date(data.scheduled_at).toISOString();
      else delete data.scheduled_at;
      await api('/campaigns', { method: 'POST', body: JSON.stringify(data) });
      toast('Campaign created');
    } else if (type === 'contact') {
      const editing = !!state.editingId;
      if (!data.group_id) data.group_id = null;
      await api('/contacts' + (editing ? '/' + encodeURIComponent(state.editingId) : ''), {
        method: editing ? 'PUT' : 'POST', body: JSON.stringify(data),
      });
      toast(editing ? 'Contact updated' : 'Contact added');
    } else if (type === 'template') {
      const editing = !!state.editingId;
      await api('/templates' + (editing ? '/' + encodeURIComponent(state.editingId) : ''), {
        method: editing ? 'PUT' : 'POST', body: JSON.stringify(data),
      });
      toast(editing ? 'Template updated' : 'Template created');
    } else if (type === 'launch') {
      if (data.phones) data.phones = data.phones.split(/[\s,;]+/).map(s => s.trim()).filter(Boolean);
      else delete data.phones;
      if (!data.group_id) delete data.group_id;
      const res = await api('/campaigns/' + encodeURIComponent(state.editingId) + '/launch', { method: 'POST', body: JSON.stringify(data) });
      toast(res.enqueued + ' messages queued');
    } else if (type === 'apikey') {
      const key = await api('/auth/api-keys', { method: 'POST', body: JSON.stringify(data) });
      $('keyRevealValue').value = key.key;
      $('keyReveal').hidden = false;
      toast('API key created');
    }
    closeModal();
    e.target.reset();
    refresh(currentView());
    refresh('overview');
    if (type === 'apikey') refresh('settings');
  } catch (err) { toast(err.message || 'Could not save', 'error'); }
  finally { submit.disabled = false; }
});

$('newCampaignBtn')?.addEventListener('click', () => openModal('campaign'));
$('newContactBtn')?.addEventListener('click', () => openModal('contact'));
$('newTemplateBtn')?.addEventListener('click', () => openModal('template'));
$('newApiKeyBtn')?.addEventListener('click', () => openModal('apikey'));
$('keyRevealCopy')?.addEventListener('click', () => copyText($('keyRevealValue').value));
$('keyRevealClose')?.addEventListener('click', () => { $('keyReveal').hidden = true; });
$('userApiKeys')?.addEventListener('click', () => refresh('settings'));

/* ---------- CSV import ---------- */
function parseCSV(text) {
  text = String(text).replace(/^\uFEFF/, '');
  const rows = [];
  let row = [], current = '', quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { current += '"'; i++; }
      else if (ch === '"') quoted = false;
      else current += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ',') { row.push(current); current = ''; }
    else if (ch === '\n') { row.push(current); rows.push(row); row = []; current = ''; }
    else if (ch !== '\r') current += ch;
  }
  if (current || row.length) { row.push(current); rows.push(row); }
  const headers = (rows.shift() || []).map(h => h.trim().toLowerCase());
  const seen = new Set();
  return rows.filter(r => r.some(c => c && c.trim())).map(r => {
    const obj = {};
    headers.forEach((h, i) => { obj[h] = (r[i] || '').trim(); });
    return { name: obj.name || '', phone: obj.phone || obj.mobile || '', email: obj.email || '', tags: obj.tags || '' };
  }).filter(c => {
    if (!c.phone || seen.has(c.phone)) return false;
    seen.add(c.phone);
    return true;
  });
}

$('importContactsBtn')?.addEventListener('click', () => $('contactsCsv').click());
$('contactsCsv')?.addEventListener('change', async e => {
  const file = e.target.files?.[0];
  if (!file) return;
  try {
    const contacts = parseCSV(await file.text());
    if (!contacts.length) { toast('No contacts with a phone column found', 'error'); return; }
    confirmAction('Import ' + contacts.length + ' contacts from ' + file.name + '?', async () => {
      await act(() => api('/contacts/import', { method: 'POST', body: JSON.stringify({ contacts }) }), contacts.length + ' contacts imported');
      refresh('contacts');
    }, 'Import');
  } catch (err) { toast('Could not read CSV file', 'error'); }
  e.target.value = '';
});

/* ---------- Navigation & filters ---------- */
document.querySelectorAll('.nav-item[data-view]').forEach(el =>
  el.addEventListener('click', () => showView(el.dataset.view))
);
document.addEventListener('click', e => {
  const el = e.target.closest('[data-goto]');
  if (el) showView(el.dataset.goto);
});

function openDrawer() {
  $('sidebar').classList.add('open');
  $('sidebarBackdrop').classList.add('open');
  document.body.classList.add('drawer-open');
}
function closeDrawer() {
  $('sidebar').classList.remove('open');
  $('sidebarBackdrop').classList.remove('open');
  document.body.classList.remove('drawer-open');
}
$('menuBtn')?.addEventListener('click', openDrawer);
$('sidebarBackdrop')?.addEventListener('click', closeDrawer);

$('messageFilters')?.addEventListener('click', e => {
  const btn = e.target.closest('[data-filter]');
  if (!btn) return;
  state.messageFilter = btn.dataset.filter;
  document.querySelectorAll('#messageFilters button').forEach(b => b.classList.toggle('active', b === btn));
  renderJobs();
});
$('daysFilters')?.addEventListener('click', e => {
  const btn = e.target.closest('[data-days]');
  if (!btn) return;
  state.days = Number(btn.dataset.days);
  document.querySelectorAll('#daysFilters button').forEach(b => b.classList.toggle('active', b === btn));
  refresh('analytics');
});

$('messagesSearch')?.addEventListener('input', renderJobs);
$('contactsSearch')?.addEventListener('input', renderContacts);
$('contactsGroupFilter')?.addEventListener('change', renderContacts);
$('schedulesStatusFilter')?.addEventListener('change', loadSchedules);
$('globalSearch')?.addEventListener('input', e => {
  const view = currentView();
  if (view === 'messages') { $('messagesSearch').value = e.target.value; renderJobs(); }
  if (view === 'contacts') { $('contactsSearch').value = e.target.value; renderContacts(); }
});
$('globalSearch')?.addEventListener('keydown', e => {
  if (e.key !== 'Enter') return;
  const q = e.target.value.trim();
  if (!q) return;
  const looksLikePhone = /^\+?[\d\s().-]+$/.test(q);
  showView(looksLikePhone ? 'messages' : 'contacts');
  const target = looksLikePhone ? 'messagesSearch' : 'contactsSearch';
  $(target).value = q;
  (looksLikePhone ? renderJobs : renderContacts)();
});

/* ---------- Real-time updates ---------- */
function silentRefresh() {
  const now = Date.now();
  if (now - state.lastSilent < 2000) return;
  state.lastSilent = now;
  refresh('overview');
  if (currentView() !== 'overview') refresh(currentView());
}

function startPolling() {
  if (state.polling) return;
  state.polling = true;
  setInterval(() => {
    if (['overview', 'messages', 'schedules'].includes(currentView())) silentRefresh();
  }, 20000);
}

function initRealtime() {
  if (state.socket || state.polling) return;
  if (typeof io !== 'function') { startPolling(); return; }
  try {
    const socket = io({ path: '/socket.io', transports: ['websocket', 'polling'] });
    state.socket = socket;
    socket.on('job_update', job => {
      if (job.status === 'success' && job.id) {
        state.seenFailures.delete(job.id);
        saveSeen();
      }
      const text = job.status === 'success' ? 'Delivered to ' + job.phone
        : job.status === 'failed' ? 'Delivery failed to ' + job.phone
          : 'Job ' + job.status + ' — ' + job.phone;
      toast(text, job.status === 'failed' ? 'error' : 'success');
      silentRefresh();
    });
    socket.on('connect_error', startPolling);
  } catch (e) { startPolling(); }
}

/* ---------- Init ---------- */
const hour = new Date().getHours();
$('greeting').textContent = (hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening') + ' 👋';
$('todayLabel').textContent = new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' }) + ' · Here is your workspace at a glance.';
refresh('overview');
if (typeof io === 'function') initRealtime(); else startPolling();
setTimeout(() => { if (!state.socket && !state.polling) initRealtime(); }, 2500);
