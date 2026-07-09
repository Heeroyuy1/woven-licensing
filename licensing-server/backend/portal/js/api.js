/**
 * Licensing Portal API Client
 * Matches the Woven Model Licensing Server REST API exactly.
 * ES module. No external dependencies.
 */
export class LicensingApi {
    constructor(baseUrl = '') {
        this.baseUrl = baseUrl.replace(/\/+$/, '');
        this.token = localStorage.getItem('woven_jwt') || null;
        this.user = null;
    }

    setToken(token) {
        this.token = token;
        if (token) {
            localStorage.setItem('woven_jwt', token);
        } else {
            localStorage.removeItem('woven_jwt');
        }
    }

    _headers(extra = {}) {
        const h = { 'Content-Type': 'application/json', 'Accept': 'application/json', ...extra };
        if (this.token) h['Authorization'] = `Bearer ${this.token}`;
        return h;
    }

    async _handleResponse(resp) {
        const text = await resp.text();
        let data = {};
        if (text) {
            try { data = JSON.parse(text); } catch (e) { data = { detail: text }; }
        }
        if (resp.status === 401) {
            this.setToken(null);
            const path = window.location.pathname;
            if (!path.includes('login.html')) {
                window.location.href = '/login.html?reason=session_expired';
                return null;
            }
            throw new Error(data.detail || 'Unauthorized');
        }
        if (!resp.ok) {
            throw new Error(data.detail || `HTTP ${resp.status}`);
        }
        return data;
    }

    async _get(path, params = {}) {
        const qs = Object.keys(params).length ? '?' + new URLSearchParams(params).toString() : '';
        const resp = await fetch(`${this.baseUrl}${path}${qs}`, {
            method: 'GET', headers: this._headers(),
        });
        return this._handleResponse(resp);
    }

    async _post(path, body = null) {
        const resp = await fetch(`${this.baseUrl}${path}`, {
            method: 'POST', headers: this._headers(),
            body: body ? JSON.stringify(body) : undefined,
        });
        return this._handleResponse(resp);
    }

    async _put(path, body = null) {
        const resp = await fetch(`${this.baseUrl}${path}`, {
            method: 'PUT', headers: this._headers(),
            body: body ? JSON.stringify(body) : undefined,
        });
        return this._handleResponse(resp);
    }

    async _delete(path) {
        const resp = await fetch(`${this.baseUrl}${path}`, {
            method: 'DELETE', headers: this._headers(),
        });
        return this._handleResponse(resp);
    }

    // ── Auth ──────────────────────────────────────────────────
    async login(email, password) {
        const data = await this._post('/api/v1/auth/login', { email, password });
        if (data.access_token) {
            this.setToken(data.access_token);
            this.user = { id: data.user_id, email: data.email, name: data.name, role: data.role };
        }
        return data;
    }

    async register(email, password, name, company) {
        const data = await this._post('/api/v1/auth/register', { email, password, name, company });
        if (data.access_token) {
            this.setToken(data.access_token);
            this.user = { id: data.user_id, email: data.email, name: data.name, role: data.role };
        }
        return data;
    }

    async refreshToken(refresh_token) {
        const data = await this._post('/api/v1/auth/refresh', { refresh_token });
        if (data.access_token) this.setToken(data.access_token);
        return data;
    }

    async logout() {
        try { await this._post('/api/v1/auth/logout'); } catch (e) { /* ignore */ }
        this.setToken(null);
        this.user = null;
    }

    // ── Public Licensing ───────────────────────────────────────
    async activateLicense(licenseKey, fingerprint, fingerprintData) {
        return this._post('/api/v1/activate', {
            license_key: licenseKey,
            fingerprint: fingerprint,
            fingerprint_data: fingerprintData,
        });
    }

    async validateLicense(licenseKey, fingerprint) {
        return this._post('/api/v1/validate', { license_key: licenseKey, fingerprint });
    }

    async deactivateLicense(licenseKey, fingerprint) {
        return this._post('/api/v1/deactivate', { license_key: licenseKey, fingerprint });
    }

    async transferLicense(licenseKey, oldFingerprint, newFingerprintData) {
        return this._post('/api/v1/transfer', {
            license_key: licenseKey,
            old_fingerprint: oldFingerprint,
            new_fingerprint_data: newFingerprintData,
        });
    }

    async renewLicense(licenseId, extraDays = 365) {
        return this._post(`/api/v1/renew?license_id=${licenseId}&extra_days=${extraDays}`);
    }

    async checkUpdates(currentVersion, productCode) {
        return this._get('/api/v1/check-updates', {
            current_version: currentVersion,
            product_code: productCode,
        });
    }

    async getLicenseInfo(licenseKey) {
        return this._get(`/api/v1/license/${licenseKey}`);
    }

    // ── Products ──────────────────────────────────────────────
    async getProducts() {
        return this._get('/api/v1/products/');
    }

    // ── Admin: Stats ──────────────────────────────────────────
    async getAdminStats() {
        return this._get('/api/v1/admin/stats');
    }

    // ── Admin: Users ──────────────────────────────────────────
    async getAdminUsers(skip = 0, limit = 200) {
        return this._get('/api/v1/admin/users', { skip, limit });
    }

    async createAdminUser(email, password, name, role = 'customer', company = '') {
        return this._post('/api/v1/admin/users', { email, password, name, role, company });
    }

    async getAdminUser(userId) {
        return this._get(`/api/v1/admin/users/${userId}`);
    }

    async updateAdminUser(userId, data) {
        return this._put(`/api/v1/admin/users/${userId}`, data);
    }

    // ── Admin: Licenses ───────────────────────────────────────
    async generateLicense(productCode, userId, licenseType = 'perpetual', options = {}) {
        return this._post('/api/v1/admin/licenses/generate', {
            product_code: productCode,
            user_id: userId,
            license_type: licenseType,
            max_activations: options.maxActivations || 1,
            max_devices: options.maxDevices || 1,
            expiration_days: options.expirationDays || null,
            perpetual: options.perpetual !== undefined ? options.perpetual : true,
            offline_days: options.offlineDays || 7,
            feature_flags: options.featureFlags || null,
            notes: options.notes || null,
        });
    }

    async revokeLicense(licenseId, reason = 'Revoked by admin') {
        return this._post(`/api/v1/admin/licenses/${licenseId}/revoke`, { reason });
    }

    async resetActivations(licenseId) {
        return this._post(`/api/v1/admin/licenses/${licenseId}/reset-activations`);
    }

    // ── Admin: Machines ───────────────────────────────────────
    async getAdminMachines(skip = 0, limit = 200) {
        return this._get('/api/v1/admin/machines', { skip, limit });
    }

    async toggleBlacklist(machineId) {
        return this._post(`/api/v1/admin/machines/${machineId}/blacklist`);
    }

    // ── Admin: Logs ─────────────────────────────────────────────
    async getAdminLogs(skip = 0, limit = 50, action = '') {
        const params = { skip, limit };
        if (action) params.action = action;
        return this._get('/api/v1/admin/logs', params);
    }

    // ── Admin: Products ───────────────────────────────────────
    async createProduct(code, name, version = '1.0.0', description = null) {
        return this._post('/api/v1/admin/products', {
            code, name, version,
            description: description || null,
            active: true,
        });
    }

    // ── Admin: Export ──────────────────────────────────────────
    async exportData(exportType) {
        return this._get('/api/v1/admin/export', { export_type: exportType });
    }
}
