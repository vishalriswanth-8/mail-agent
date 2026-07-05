/**
 * Mail Agent API Client
 * Centralised wrappers for all backend REST endpoints.
 */

const API = {
  // ─── Accounts ────────────────────────────────────────────
  async getAccounts() {
    const r = await fetch('/api/accounts');
    return r.json();
  },
  async addAccount() {
    const r = await fetch('/api/accounts/add', { method: 'POST' });
    return r.json();
  },
  async removeAccount(email) {
    const r = await fetch(`/api/accounts/${encodeURIComponent(email)}`, { method: 'DELETE' });
    return r.json();
  },
  async searchContacts(query) {
    const r = await fetch(`/api/contacts/search?q=${encodeURIComponent(query)}`);
    return r.json();
  },

  // ─── Emails ──────────────────────────────────────────────
  async getEmails(params = {}) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.set(k, v); });
    const r = await fetch(`/api/emails?${qs}`);
    return r.json();
  },
  async getEmailDetail(id) {
    const r = await fetch(`/api/emails/${id}`);
    return r.json();
  },
  async toggleImportant(id, isImportant) {
    const r = await fetch(`/api/emails/${id}/important`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ is_important: isImportant }),
    });
    return r.json();
  },
  async sendEmail(from, to, subject, body) {
    const r = await fetch('/api/emails/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, subject, body }),
    });
    return r.json();
  },
  async composeEmail(instruction) {
    const r = await fetch('/api/emails/compose', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ instruction }),
    });
    return r.json();
  },
  async rewriteEmail(text) {
    const r = await fetch('/api/emails/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text }),
    });
    return r.json();
  },
  async scheduleEmail(from, to, subject, body, send_at, schedule_hint) {
    const r = await fetch('/api/emails/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ from, to, subject, body, send_at, schedule_hint }),
    });
    return r.json();
  },
  async getScheduledEmails(status) {
    const qs = status ? `?status=${status}` : '';
    const r = await fetch(`/api/emails/scheduled${qs}`);
    return r.json();
  },
  async deleteScheduledEmail(id) {
    const r = await fetch(`/api/emails/scheduled/${id}`, { method: 'DELETE' });
    return r.json();
  },

  // ─── Sync ─────────────────────────────────────────────────
  async syncEmails(account) {
    const r = await fetch('/api/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(account ? { account } : {}),
    });
    return r.json();
  },
  async getSyncStatus() {
    const r = await fetch('/api/sync/status');
    return r.json();
  },
  async controlAutoSync(enabled, interval = 300) {
    const r = await fetch('/api/sync/auto', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled, interval }),
    });
    return r.json();
  },
  async getAutoSyncStatus() {
    const r = await fetch('/api/sync/auto/status');
    return r.json();
  },

  // ─── Stats ───────────────────────────────────────────────
  async getStats(account) {
    const qs = account ? `?account=${encodeURIComponent(account)}` : '';
    const r = await fetch(`/api/stats${qs}`);
    return r.json();
  },

  // ─── Settings ────────────────────────────────────────────
  async getSettings() {
    const r = await fetch('/api/settings');
    return r.json();
  },
  async saveSettings(data) {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  },

  // ─── Model Tests ─────────────────────────────────────────
  async testModel(settings = {}) {
    const r = await fetch('/api/models/test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(settings),
    });
    return r.json();
  },
  async testLocalModel(url, model) {
    const r = await fetch('/api/models/test-local', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ local_base_url: url, local_model: model }),
    });
    return r.json();
  },
  async testCloudModel(model) {
    const r = await fetch('/api/models/test-cloud', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cloud_model: model }),
    });
    return r.json();
  },
  async getModelStatus() {
    const r = await fetch('/api/models/status');
    return r.json();
  },

  // ─── Chat ─────────────────────────────────────────────────
  async chat(message, scope, account, session_id) {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, scope, account, session_id, limit: 16 }),
    });
    return r.json();
  },
  async getChatHistory(session_id, limit = 50) {
    const r = await fetch(`/api/chat/history?session_id=${encodeURIComponent(session_id)}&limit=${limit}`);
    return r.json();
  },

  // ─── Agent ────────────────────────────────────────────────
  async generateDraftReply(emailId, scope = 'professional') {
    const r = await fetch(`/api/agent/draft-reply/${emailId}?scope=${scope}`);
    return r.json();
  },
  async analyzeEmail(emailId) {
    const r = await fetch(`/api/agent/analyze/${emailId}`);
    return r.json();
  },

  // ─── Rules ────────────────────────────────────────────────
  async getRules() {
    const r = await fetch('/api/agent/rules');
    return r.json();
  },
  async createRule(data) {
    const r = await fetch('/api/agent/rules', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  },
  async updateRule(id, data) {
    const r = await fetch(`/api/agent/rules/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    return r.json();
  },
  async deleteRule(id) {
    const r = await fetch(`/api/agent/rules/${id}`, { method: 'DELETE' });
    return r.json();
  },

  // ─── Logs ─────────────────────────────────────────────────
  async getLogs(limit = 100) {
    const r = await fetch(`/api/logs?limit=${limit}`);
    return r.json();
  },
};
