/**
 * Stratum Licensing Portal — Main Application
 * Vanilla JS, ES module. Connects to Woven Model Licensing Server API.
 * Features: Dashboard, License management, User management, Machine management, Settings
 */
import { LicensingApi } from './api.js';

const api = new LicensingApi('http://localhost:8000');
let state = {
    user: null,
    stats: null,
    licenses: [],
    users: [],
    machines: [],
    products: [],
    logs: [],
    activeTab: 'dashboard',
};

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function escapeHtml(text) {
    if (!text) return '';
    const d = document.createElement('div');
    d.textContent = String(text);
    return d.innerHTML;
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transition = 'opacity 0.3s';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

function formatDate(dateStr) {
    if (!dateStr) return '—';
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    const opts = { year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' };
    return d.toLocaleDateString('en-US', opts);
}

function timeAgo(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    if (isNaN(d)) return dateStr;
    const now = new Date();
    const sec = Math.floor((now - d) / 1000);
    if (sec < 60) return `${sec}s ago`;
    const min = Math.floor(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.floor(min / 60);
    if (hr < 24) return `${hr}h ago`;
    return `${Math.floor(hr / 24)}d ago`;
}

function capFirst(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : ''; }

function badgeClass(status) {
    const s = (status || '').toLowerCase();
    if (['active', 'perpetual', 'yes', 'true'].includes(s)) return 'badge-active';
    if (['inactive', 'revoked', 'blocked', 'disabled', 'false'].includes(s)) return 'badge-inactive';
    if (['pending', 'trial'].includes(s)) return 'badge-pending';
    if (['expired', 'subscription'].includes(s)) return 'badge-expired';
    return '';
}

function showIn(el, content) {
    if (el) el.innerHTML = content;
}

async function loadApp() {
    if (!api.token) {
        window.location.href = '/login.html';
        return;
    }
    // Decode JWT to get user info
    try {
        const payload = JSON.parse(atob(api.token.split('.')[1]));
        state.user = {
            id: payload.sub || 0,
            email: payload.email || 'admin@wovenmodel.com',
            name: payload.name || 'Administrator',
            role: payload.role || 'admin',
        };
    } catch (e) {
        state.user = { id: 0, email: 'admin@wovenmodel.com', name: 'Administrator', role: 'admin' };
    }

    if (window.location.pathname.includes('login.html')) {
        window.location.href = '/';
        return;
    }

    const loginEl = document.getElementById('app-login');
    const mainEl = document.getElementById('app-main');
    if (loginEl) loginEl.style.display = 'none';
    if (mainEl) mainEl.style.display = 'grid';

    const avatar = document.getElementById('sidebar-avatar');
    const userName = document.getElementById('sidebar-username');
    const userEmail = document.getElementById('sidebar-useremail');
    if (avatar) avatar.textContent = (state.user.name || 'A')[0].toUpperCase();
    if (userName) userName.textContent = state.user.name;
    if (userEmail) userEmail.textContent = state.user.email;

    const params = new URLSearchParams(window.location.search);
    switchTab(params.get('tab') || 'dashboard');
}

function switchTab(tabName) {
    state.activeTab = tabName;
    $$('.sidebar-nav-item').forEach(item => item.classList.toggle('active', item.dataset.tab === tabName));
    $$('.page').forEach(page => page.classList.toggle('active', page.id === `page-${tabName}`));
    switch (tabName) {
        case 'dashboard': loadDashboard(); break;
        case 'licenses': loadLicenses(); break;
        case 'users': loadUsers(); break;
        case 'machines': loadMachines(); break;
        case 'settings': loadSettings(); break;
        case 'logs': loadLogs(); break;
    }
}

// ── Dashboard ────────────────────────────────────────────────────
async function loadDashboard() {
    const statsEl = document.getElementById('dash-stats');
    const activityEl = document.getElementById('dash-activity');
    const logsEl = document.getElementById('dash-logs');

    showIn(statsEl, '<div class="loading"><div class="spinner"></div></div>');
    if (activityEl) showIn(activityEl, '');
    if (logsEl) showIn(logsEl, '');

    try {
        const stats = await api.getAdminStats();
        state.stats = stats;
        renderStats(stats);
    } catch (err) {
        showIn(statsEl, `<div class="empty-state"><p>Failed to load stats: ${escapeHtml(err.message)}</p><button class="btn btn-outline btn-sm" onclick="loadDashboard()">Retry</button></div>`);
    }

    try {
        const logs = await api.getAdminLogs(0, 10);
        if (logsEl) renderRecentActivity(logs);
    } catch (_) {}

    try {
        const logs = await api.getAdminLogs(0, 5);
        if (logsEl) renderRecentActivity(logs);
    } catch (_) {}
}

function renderStats(stats) {
    const cards = [
        { label: 'Total Users', value: stats.total_users || 0, icon: 'people' },
        { label: 'Total Licenses', value: stats.total_licenses || 0, icon: 'key' },
        { label: 'Active Licenses', value: stats.active_licenses || 0, icon: 'check' },
        { label: 'Machines', value: stats.total_machines || 0, icon: 'monitor' },
        { label: 'Activations', value: stats.total_activations || 0, icon: 'zap' },
        { label: 'Products', value: stats.total_products || 0, icon: 'package' },
    ];
    const el = document.getElementById('dash-stats');
    showIn(el, cards.map(c => `
        <div class="stat-card">
            <div class="stat-icon">${svgIcon(c.icon)}</div>
            <div class="stat-value">${c.value}</div>
            <div class="stat-label">${c.label}</div>
        </div>
    `).join(''));
}

function renderRecentActivity(logs) {
    const el = document.getElementById('dash-logs');
    if (!el) return;
    if (!logs || logs.length === 0) {
        showIn(el, '<div class="empty-state"><p>No recent activity</p></div>');
        return;
    }
    showIn(el, logs.map(l => `
        <div class="activity-item">
            <div class="activity-icon">${svgIcon('activity')}</div>
            <div class="activity-body">
                <div class="activity-text">${escapeHtml(l.action || 'Activity')} ${l.details ? '— ' + escapeHtml(l.details) : ''}</div>
                <div class="activity-time">${timeAgo(l.timestamp)}</div>
            </div>
        </div>
    `).join('') + `<div style="margin-top:12px;text-align:right;"><a class="btn btn-outline btn-sm" href="#" onclick="switchTab('logs');return false;">View All Logs →</a></div>`);
}

// ── Licenses ─────────────────────────────────────────────────────
async function loadLicenses() {
    const el = document.getElementById('licenses-table-body');
    showIn(el, '<tr><td colspan="8"><div class="loading"><div class="spinner"></div></div></td></tr>');
    try {
        const data = await api.getAdminStats();
        // Fetch license info from export
        const exportData = await api.exportData('licenses');
        state.licenses = exportData.data || [];
        renderLicenses();
        // Load products
        try {
            state.products = await api.getProducts();
            populateProductSelect();
        } catch (_) {}
    } catch (err) {
        showIn(el, `<tr><td colspan="8" class="empty-state"><p>${escapeHtml(err.message)}</p><button class="btn btn-outline btn-sm" onclick="loadLicenses()">Retry</button></td></tr>`);
    }
}

function renderLicenses() {
    const el = document.getElementById('licenses-table-body');
    if (!state.licenses.length) {
        showIn(el, '<tr><td colspan="8"><div class="empty-state"><p>No licenses found. Generate one to get started.</p></div></td></tr>');
        return;
    }
    showIn(el, state.licenses.map(lic => {
        const status = (lic.status || 'active').toLowerCase();
        return `<tr>
            <td style="font-family:monospace;font-size:12px;max-width:180px;overflow:hidden;text-overflow:ellipsis" title="${escapeHtml(lic.license_key || '')}">${escapeHtml(lic.license_key || '—')}</td>
            <td><span class="badge ${badgeClass(lic.type || lic.license_type)}">${escapeHtml(capFirst(lic.type || lic.license_type || 'standard'))}</span></td>
            <td><span class="badge ${badgeClass(status)}">${escapeHtml(capFirst(status))}</span></td>
            <td>${escapeHtml(lic.user_email || lic.email || '—')}</td>
            <td>${escapeHtml(lic.product_code || lic.product || '—')}</td>
            <td>${formatDate(lic.expiration_date || lic.expires_at || lic.expiration)}</td>
            <td style="text-align:center">${lic.current_activations || 0}/${lic.max_activations || '—'}</td>
            <td><div class="table-actions">
                <button class="btn btn-outline btn-sm" onclick="showLicenseDetail('${escapeHtml(lic.license_key)}')" title="View details">View</button>
                <button class="btn btn-danger btn-sm" onclick="revokeLicense(${lic.id})" ${status === 'revoked' ? 'disabled' : ''}>Revoke</button>
            </div></td>
        </tr>`;
    }).join(''));
}

window.showLicenseDetail = async function(key) {
    try {
        const info = await api.getLicenseInfo(key);
        const el = document.getElementById('license-detail-content');
        const activations = (info.activations || []).map(a => `
            <tr><td>${escapeHtml(a.machine_fingerprint || '')}</td><td>${escapeHtml(a.machine_hostname || '—')}</td><td><span class="badge ${badgeClass(a.status)}">${escapeHtml(a.status)}</span></td><td>${formatDate(a.activation_date)}</td><td>${formatDate(a.last_validation)}</td></tr>
        `).join('');
        showIn(el, `
            <div class="settings-section">
                <h3>${escapeHtml(info.license_key)}</h3>
                <div class="form-row" style="grid-template-columns:1fr 1fr 1fr;margin-bottom:16px">
                    <div><label>Type</label><div>${escapeHtml(capFirst(info.license_type))}</div></div>
                    <div><label>Status</label><div><span class="badge ${badgeClass(info.status)}">${escapeHtml(capFirst(info.status))}</span></div></div>
                    <div><label>Product ID</label><div>${info.product_id}</div></div>
                    <div><label>User ID</label><div>${info.user_id}</div></div>
                    <div><label>Expires</label><div>${formatDate(info.expiration_date)}</div></div>
                    <div><label>Activations</label><div>${info.current_activations}/${info.max_activations}</div></div>
                    <div><label>Perpetual</label><div>${info.perpetual ? '✅ Yes' : '❌ No'}</div></div>
                    <div><label>Offline Days</label><div>${info.offline_days}</div></div>
                    <div><label>Created</label><div>${formatDate(info.created_at)}</div></div>
                </div>
                ${info.feature_flags ? `<div><label>Features</label><div style="margin-bottom:12px">${escapeHtml(info.feature_flags)}</div></div>` : ''}
                ${info.activations && info.activations.length ? `
                <h4 style="margin:16px 0 8px">Activations (${info.activations.length})</h4>
                <div class="table-container"><table><thead><tr><th>Fingerprint</th><th>Hostname</th><th>Status</th><th>Activated</th><th>Last Validation</th></tr></thead><tbody>${activations}</tbody></table></div>
                ` : '<div class="empty-state"><p>No activations</p></div>'}
                <div style="margin-top:16px;display:flex;gap:8px">
                    <button class="btn btn-outline" onclick="hideModal('modal-license-detail')">Close</button>
                    <button class="btn btn-danger" onclick="revokeLicense(${info.id});hideModal('modal-license-detail')">Revoke License</button>
                    <button class="btn btn-success" onclick="resetActivations(${info.id});hideModal('modal-license-detail')">Reset Activations</button>
                </div>
            </div>
        `);
        showModal('modal-license-detail');
    } catch (err) {
        showToast(err.message || 'Failed to load license details', 'error');
    }
};

document.addEventListener('click', function(e) {
    const exportMenu = document.getElementById('export-menu');
    const exportBtn = document.getElementById('export-btn');
    if (exportMenu && exportBtn && !exportBtn.contains(e.target) && !exportMenu.contains(e.target)) {
        exportMenu.classList.remove('visible');
    }
});

window.revokeLicense = async function(id) {
    if (!confirm('Revoke this license permanently? This action cannot be undone.')) return;
    try {
        await api.revokeLicense(id);
        showToast('License revoked', 'success');
        loadLicenses();
    } catch (err) {
        showToast(err.message || 'Failed to revoke', 'error');
    }
};

window.resetActivations = async function(id) {
    if (!confirm('Reset all activations for this license?')) return;
    try {
        await api.resetActivations(id);
        showToast('Activations reset', 'success');
        loadLicenses();
    } catch (err) {
        showToast(err.message || 'Failed to reset', 'error');
    }
};

function populateProductSelect() {
    const select = document.getElementById('gen-product');
    if (!select) return;
    select.innerHTML = '<option value="">Select product…</option>' +
        state.products.map(p => `<option value="${escapeHtml(p.code || p.id)}">${escapeHtml(p.name || p.code)} (${escapeHtml(p.code)})</option>`).join('');
}

// ── Users ────────────────────────────────────────────────────────
async function loadUsers() {
    const el = document.getElementById('users-table-body');
    showIn(el, '<tr><td colspan="5"><div class="loading"><div class="spinner"></div></div></td></tr>');
    try {
        state.users = await api.getAdminUsers();
        renderUsers();
    } catch (err) {
        showIn(el, `<tr><td colspan="5" class="empty-state"><p>${escapeHtml(err.message)}</p><button class="btn btn-outline btn-sm" onclick="loadUsers()">Retry</button></td></tr>`);
    }
}

function renderUsers() {
    const el = document.getElementById('users-table-body');
    if (!state.users.length) {
        showIn(el, '<tr><td colspan="5"><div class="empty-state"><p>No users found</p></div></td></tr>');
        return;
    }
    showIn(el, state.users.map(u =>
        `<tr>
            <td>${escapeHtml(u.email || '—')}</td>
            <td>${escapeHtml(u.name || '—')}</td>
            <td><span class="badge ${badgeClass(u.role)}">${escapeHtml(capFirst(u.role))}</span></td>
            <td><span class="badge ${badgeClass(u.is_active ? 'active' : 'inactive')}">${u.is_active ? 'Active' : 'Inactive'}</span></td>
            <td>${u.license_count || 0}</td>
        </tr>`
    ).join(''));
}

window.handleCreateUser = async function(e) {
    e.preventDefault();
    const email = document.getElementById('new-user-email').value.trim();
    const password = document.getElementById('new-user-password').value;
    const name = document.getElementById('new-user-name').value.trim();
    const role = document.getElementById('new-user-role').value;

    if (!email || !password) {
        showToast('Email and password are required', 'error');
        return;
    }

    const btn = document.getElementById('create-user-submit');
    btn.disabled = true;
    btn.textContent = 'Creating…';
    try {
        await api.createAdminUser(email, password, name, role);
        showToast('User created successfully!', 'success');
        hideModal('modal-create-user');
        document.getElementById('create-user-form').reset();
        loadUsers();
    } catch (err) {
        showToast(err.message || 'Failed to create user', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create User';
    }
};

// ── Machines ─────────────────────────────────────────────────────
async function loadMachines() {
    const el = document.getElementById('machines-table-body');
    showIn(el, '<tr><td colspan="5"><div class="loading"><div class="spinner"></div></div></td></tr>');
    try {
        state.machines = await api.getAdminMachines();
        renderMachines();
    } catch (err) {
        showIn(el, `<tr><td colspan="5" class="empty-state"><p>${escapeHtml(err.message)}</p><button class="btn btn-outline btn-sm" onclick="loadMachines()">Retry</button></td></tr>`);
    }
}

function renderMachines() {
    const el = document.getElementById('machines-table-body');
    if (!state.machines.length) {
        showIn(el, '<tr><td colspan="5"><div class="empty-state"><p>No machines registered yet. Machines appear when licenses are activated.</p></div></td></tr>');
        return;
    }
    showIn(el, state.machines.map(m =>
        `<tr>
            <td style="font-family:monospace;font-size:11px;" title="${escapeHtml(m.fingerprint_hash)}">${escapeHtml((m.fingerprint_hash || '').substring(0, 24))}…</td>
            <td>${escapeHtml(m.hostname || '—')}</td>
            <td>${escapeHtml(m.operating_system || '—')}</td>
            <td>${formatDate(m.last_seen)}</td>
            <td>
                <label class="toggle">
                    <input type="checkbox" ${m.is_blacklisted ? 'checked' : ''} onchange="toggleBlacklist(${m.id}, this.checked)">
                    <span class="slider"></span>
                </label>
            </td>
        </tr>`
    ).join(''));
}

window.toggleBlacklist = async function(id, checked) {
    try {
        await api.toggleBlacklist(id);
        showToast(checked ? 'Machine blacklisted' : 'Machine unblacklisted', 'success');
        loadMachines();
    } catch (err) {
        showToast(err.message || 'Failed to toggle blacklist', 'error');
        loadMachines();
    }
};

// ── Logs ─────────────────────────────────────────────────────────
async function loadLogs() {
    const el = document.getElementById('logs-table-body');
    if (!el) return;
    showIn(el, '<tr><td colspan="5"><div class="loading"><div class="spinner"></div></div></td></tr>');
    try {
        state.logs = await api.getAdminLogs(0, 100);
        renderLogs();
    } catch (err) {
        showIn(el, `<tr><td colspan="5" class="empty-state"><p>${escapeHtml(err.message)}</p></td></tr>`);
    }
}

function renderLogs() {
    const el = document.getElementById('logs-table-body');
    if (!el) return;
    if (!state.logs.length) {
        showIn(el, '<tr><td colspan="5"><div class="empty-state"><p>No log entries</p></div></td></tr>');
        return;
    }
    showIn(el, state.logs.map(l =>
        `<tr>
            <td style="white-space:nowrap">${formatDate(l.timestamp)}</td>
            <td><span class="badge ${badgeClass(l.success ? 'active' : 'inactive')}">${l.success ? '✅' : '❌'}</span></td>
            <td>${escapeHtml(l.action)}</td>
            <td>${escapeHtml(l.user_email || '—')}</td>
            <td>${escapeHtml(l.details || '—')}</td>
        </tr>`
    ).join(''));
}

// ── Settings ──────────────────────────────────────────────────────
function loadSettings() {
    // Signing key info is not exposed via API, so show info text
    const keyEl = document.getElementById('settings-signing-key');
    if (keyEl) showIn(keyEl, 'The server Ed25519 public key is not exposed through the API for security. It is stored in the .env.production file as SIGNING_PUBLIC_KEY.');
}

// ── License Generator ────────────────────────────────────────────
window.handleGenerateLicense = async function(e) {
    e.preventDefault();
    const productCode = document.getElementById('gen-product').value;
    const userId = parseInt(document.getElementById('gen-user').value, 10);
    const licType = document.getElementById('gen-type').value;
    const maxAct = parseInt(document.getElementById('gen-max-activations').value, 10) || 1;
    const perpetual = licType === 'perpetual';
    const expirationDays = document.getElementById('gen-expiration-days').value ? parseInt(document.getElementById('gen-expiration-days').value, 10) : null;

    if (!productCode || !userId) {
        showToast('Please select a product and enter a user ID', 'error');
        return;
    }

    const btn = document.getElementById('gen-submit');
    btn.disabled = true;
    btn.textContent = 'Generating…';
    try {
        const result = await api.generateLicense(productCode, userId, licType, {
            maxActivations: maxAct,
            perpetual: perpetual,
            expirationDays: expirationDays,
            featureFlags: ['all'],
        });
        showToast(`License generated: ${result.license_key}`, 'success');
        hideModal('modal-generate');
        document.getElementById('gen-form').reset();
        loadLicenses();
    } catch (err) {
        showToast(err.message || 'Failed to generate license', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Generate License';
    }
};

// ── Exports ──────────────────────────────────────────────────────
window.handleExport = async function(type) {
    const btn = document.getElementById('export-btn');
    if (btn) { btn.disabled = true; btn.textContent = 'Exporting…'; }
    try {
        const data = await api.exportData(type);
        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = data.filename || `woven-${type}-${Date.now()}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showToast(`Exported ${data.record_count} ${type} records`, 'success');
    } catch (err) {
        showToast(err.message || 'Export failed', 'error');
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = 'Export Data'; }
    }
};

// ── Modal Helpers ────────────────────────────────────────────────
function showModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.add('visible');
}

function hideModal(id) {
    const el = document.getElementById(id);
    if (el) el.classList.remove('visible');
}

window.showGenerateModal = function() {
    if (state.products.length === 0) {
        // Try loading products
        api.getProducts().then(p => { state.products = p; populateProductSelect(); }).catch(() => {});
    }
    populateProductSelect();
    showModal('modal-generate');
};

window.hideGenerateModal = () => hideModal('modal-generate');

window.showCreateUserModal = () => showModal('modal-create-user');
window.hideCreateUserModal = () => hideModal('modal-create-user');

window.showCreateProductModal = () => showModal('modal-create-product');
window.hideCreateProductModal = () => hideModal('modal-create-product');

window.handleCreateProduct = async function(e) {
    e.preventDefault();
    const code = document.getElementById('new-product-code').value.trim().toUpperCase().replace(/\s+/g, '_');
    const name = document.getElementById('new-product-name').value.trim();
    const version = document.getElementById('new-product-version').value.trim() || '1.0.0';
    const description = document.getElementById('new-product-description').value.trim() || null;

    if (!code || !name) {
        showToast('Product code and name are required', 'error');
        return;
    }

    const btn = document.getElementById('create-product-submit');
    btn.disabled = true;
    btn.textContent = 'Creating…';
    try {
        const result = await api.createProduct(code, name, version, description);
        showToast(`Product "${result.name}" created!`, 'success');
        hideModal('modal-create-product');
        document.getElementById('create-product-form').reset();
        state.products = await api.getProducts();
        populateProductSelect();
    } catch (err) {
        showToast(err.message || 'Failed to create product', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Create Product';
    }
};

// ── SVG Icons ────────────────────────────────────────────────────
function svgIcon(name) {
    const icons = {
        dashboard: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>',
        licenses: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 7l-4 4-2-2"/><rect x="3" y="3" width="18" height="18" rx="2"/></svg>',
        users: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="8" r="4"/><path d="M4 21v-2a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2"/></svg>',
        machines: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="12" rx="2"/><path d="M8 20h8"/><path d="M12 16v4"/></svg>',
        settings: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>',
        logs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        people: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>',
        key: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="15" r="4"/><path d="M10.85 12.15L19 4"/><path d="M18 5l2 2"/><path d="M15 8l2 2"/></svg>',
        check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>',
        monitor: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8"/><path d="M12 17v4"/></svg>',
        zap: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>',
        activity: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
        package: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16.5 9.4 7.55 4.24"/><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"/><polyline points="3.29 7 12 12 20.71 7"/><line x1="12" y1="22" x2="12" y2="12"/></svg>',
        plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>',
    };
    return icons[name] || '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/></svg>';
}

// ── Init ──────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    // Login form
    const loginForm = document.getElementById('login-form');
    if (loginForm) {
        loginForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const errorEl = document.getElementById('login-error');
            const btn = document.getElementById('login-btn');
            const email = document.getElementById('login-email').value.trim();
            const password = document.getElementById('login-password').value;
            if (errorEl) errorEl.classList.remove('visible');
            if (!email || !password) {
                if (errorEl) { errorEl.textContent = 'Please enter email and password.'; errorEl.classList.add('visible'); }
                return;
            }
            btn.disabled = true;
            btn.textContent = 'Signing in…';
            try {
                await api.login(email, password);
                window.location.href = '/';
            } catch (err) {
                if (errorEl) { errorEl.textContent = err.message || 'Login failed.'; errorEl.classList.add('visible'); }
                btn.disabled = false;
                btn.textContent = 'Sign In';
            }
        });
    }

    // Sidebar navigation
    $$('.sidebar-nav-item').forEach(item => {
        item.addEventListener('click', () => switchTab(item.dataset.tab));
    });

    // Logout
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async () => {
            await api.logout();
            window.location.href = '/login.html';
        });
    }

    // Modal close handlers
    $$('.modal-overlay').forEach(overlay => {
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) overlay.classList.remove('visible');
        });
    });
    $$('.modal-close').forEach(btn => {
        btn.addEventListener('click', () => btn.closest('.modal-overlay').classList.remove('visible'));
    });

    // Generate license form
    const genForm = document.getElementById('gen-form');
    if (genForm) genForm.addEventListener('submit', window.handleGenerateLicense);

    // Create user form
    const createForm = document.getElementById('create-user-form');
    if (createForm) createForm.addEventListener('submit', window.handleCreateUser);

    // Create product form
    const createProductForm = document.getElementById('create-product-form');
    if (createProductForm) createProductForm.addEventListener('submit', window.handleCreateProduct);

    // Export dropdown
    const exportBtn = document.getElementById('export-btn');
    const exportMenu = document.getElementById('export-menu');
    if (exportBtn && exportMenu) {
        exportBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            exportMenu.classList.toggle('visible');
        });
        exportMenu.querySelectorAll('.dropdown-item').forEach(item => {
            item.addEventListener('click', () => {
                window.handleExport(item.dataset.type);
                exportMenu.classList.remove('visible');
            });
        });
    }

    // Check auth and load app
    if (api.token) {
        loadApp();
    } else if (!window.location.pathname.includes('login.html')) {
        window.location.href = '/login.html';
    }
});
