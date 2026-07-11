/**
 * Mail Agent API Client
 * Centralised wrappers for all backend REST endpoints.
 */

async function apiFetch(url, options = {}) {
  const host = window.location.hostname;
  const isLocal = host === 'localhost' || host === '127.0.0.1';
  const base = isLocal ? '' : (localStorage.getItem('backend_url') || 'http://127.0.0.1:5000');
  const fullUrl = base && url.startsWith('/') ? `${base}${url}` : url;
  return fetch(fullUrl, options);
}

const API = {
  // ─── Accounts ────────────────────────────────────────────
  async getAccounts() {
    const r = await apiFetch('/api/accounts');
    return r.json();
  },
  async addAccount() {
    const r = await apiFetch('/api/accounts/add', { method: 'POST' });
    return r.json();
  },
  async removeAccount(email) {
    const r = await apiFetch(`/api/accounts/${encodeURIComponent(email)}`, { method: 'DELETE' });
    return r.json();
  },
  async searchContacts(query) {
    const r = await apiFetch(`/api/contacts/search?q=${encodeURIComponent(query)}`);
    return r.json();
  },

  // ─── Emails ──────────────────────────────────────────────
  async getEmails(params = {}) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, v); });
    const r = await apiFetch(`/api/emails?${qs}`);
    return r.json();
  },
  async getEmailDetail(id) {
    const r = await apiFetch(`/api/emails/${id}`);
    return r.json();
  },
  async toggleImportant(id, isImportant) {
    const r = await apiFetch(`/api/emails/${id}/important`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_important: isImportant }),
    });
    return r.json();
  },
  async sendEmail(from, to, subject, body) {
    const r = await apiFetch('/api/emails/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, subject, body }),
    });
    return r.json();
  },
  async composeEmail(instruction) {
    const r = await apiFetch('/api/emails/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
    });
    return r.json();
  },
  async rewriteEmail(text) {
    const r = await apiFetch('/api/emails/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    return r.json();
  },
  async scheduleEmail(from, to, subject, body, send_at, schedule_hint) {
    const r = await apiFetch('/api/emails/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, subject, body, send_at, schedule_hint }),
    });
    return r.json();
  },
  async getScheduledEmails(status) {
    const qs = status ? `?status=${status}` : '';
    const r = await apiFetch(`/api/emails/scheduled${qs}`);
    return r.json();
  },
  async deleteScheduledEmail(id) {
    const r = await apiFetch(`/api/emails/scheduled/${id}`, { method: 'DELETE' });
    return r.json();
  },

  // ─── Sync ─────────────────────────────────────────────────
  async syncEmails(account) {
    const r = await apiFetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(account ? { account } : {}),
    });
    return r.json();
  },
  async getSyncStatus() {
    const r = await apiFetch('/api/sync/status');
    return r.json();
  },
  async controlAutoSync(enabled, interval = 300) {
    const r = await apiFetch('/api/sync/auto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, interval }),
    });
    return r.json();
  },
  async getAutoSyncStatus() {
    const r = await apiFetch('/api/sync/auto/status');
    return r.json();
  },

  // ─── Stats ───────────────────────────────────────────────
  async getStats(account) {
    const qs = account ? `?account=${encodeURIComponent(account)}` : '';
    const r = await apiFetch(`/api/stats${qs}`);
    return r.json();
  },

  // ─── Settings ────────────────────────────────────────────
  async getSettings() {
    const r = await apiFetch('/api/settings');
    return r.json();
  },
  async saveSettings(data) {
    const r = await apiFetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  },

  // ─── Model Tests ─────────────────────────────────────────
  async testModel(settings = {}) {
    const r = await apiFetch('/api/models/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    return r.json();
  },
  async testLocalModel(url, model) {
    const r = await apiFetch('/api/models/test-local', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ local_base_url: url, local_model: model }),
    });
    return r.json();
  },
  async testCloudModel(model) {
    const r = await apiFetch('/api/models/test-cloud', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cloud_model: model }),
    });
    return r.json();
  },
  async getModelStatus() {
    const r = await apiFetch('/api/models/status');
    return r.json();
  },

  async chat(message, scope, account, session_id) {
    const r = await apiFetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, scope, account, session_id, limit: 16 }),
    });
    return r.json();
  },
  async getChatHistory(session_id, limit = 50) {
    const r = await apiFetch(`/api/chat/history?session_id=${encodeURIComponent(session_id)}&limit=${limit}`);
    return r.json();
  },
  async getChatSessions() {
    const r = await apiFetch('/api/chat/sessions');
    return r.json();
  },


  // ─── Agent ────────────────────────────────────────────────
  async generateDraftReply(emailId, scope = 'professional') {
    const r = await apiFetch(`/api/agent/draft-reply/${emailId}?scope=${scope}`);
    return r.json();
  },
  async analyzeEmail(emailId) {
    const r = await apiFetch(`/api/agent/analyze/${emailId}`);
    return r.json();
  },

  // ─── Rules ────────────────────────────────────────────────
  async getRules() {
    const r = await apiFetch('/api/agent/rules');
    return r.json();
  },
  async createRule(data) {
    const r = await apiFetch('/api/agent/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  },
  async updateRule(id, data) {
    const r = await apiFetch(`/api/agent/rules/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  },
  async deleteRule(id) {
    const r = await apiFetch(`/api/agent/rules/${id}`, { method: 'DELETE' });
    return r.json();
  },
  async sendChatMessage(message, email_id, scope, session_id) {
    const r = await apiFetch('/api/chat/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, email_id, scope, session_id }),
    });
    return r.json();
  },

  // ─── Logs ─────────────────────────────────────────────────
  async getLogs(limit = 100) {
    const r = await apiFetch(`/api/logs?limit=${limit}`);
    return r.json();
  },
};
