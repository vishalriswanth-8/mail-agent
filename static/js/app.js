/**
 * Mail Agent — Main Application Controller
 */

// ─── State ─────────────────────────────────────────────────
const state = {
  accounts: [],
  emails: [],
  selectedAccount: null,
  currentView: 'inbox',
  currentFilter: {},
  currentEmailId: null,
  chatSessionId: getOrCreateChatSession(),
  chatOpen: false,
  isCloudMode: false,
  syncPollInterval: null,
};

function getOrCreateChatSession() {
  const stored = localStorage.getItem('mailAgentChatSession');
  const timestamp = localStorage.getItem('mailAgentChatTimestamp');
  const now = Date.now();

  // Keep session for 24 hours
  if (stored && timestamp && (now - parseInt(timestamp)) < 86400000) {
    return stored;
  }

  const newSession = generateUUID();
  localStorage.setItem('mailAgentChatSession', newSession);
  localStorage.setItem('mailAgentChatTimestamp', now.toString());
  return newSession;
}

// ─── Init ───────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  bindEvents();
  await loadAccounts();
  await loadStats();
  await loadEmails();
  await loadSettings();
  await refreshModelStatus();
  await loadChatHistory();
  await loadChatSessions();
  startSyncPoller();
});

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, c => {
    const r = Math.random() * 16 | 0;
    return (c === 'x' ? r : (r & 0x3 | 0x8)).toString(16);
  });
}

// ─── Event Bindings ────────────────────────────────────────
function bindEvents() {
  // Accounts
  document.getElementById('btn-add-account')?.addEventListener('click', addAccount);
  document.getElementById('btn-add-first')?.addEventListener('click', addAccount);

  // Navigation
  document.querySelectorAll('.nav-item[data-view]').forEach(btn => {
    btn.addEventListener('click', () => switchView(btn.dataset.view));
  });
  document.getElementById('nav-settings')?.addEventListener('click', openSettings);

  // Sync
  document.getElementById('btn-sync')?.addEventListener('click', triggerSync);

  // Search & Filters
  let searchDebounce;
  document.getElementById('search-input')?.addEventListener('input', e => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => {
      state.currentFilter.search = e.target.value || undefined;
      loadEmails();
    }, 350);
  });
  document.getElementById('filter-account')?.addEventListener('change', e => {
    state.selectedAccount = e.target.value || null;
    state.currentFilter.account = state.selectedAccount;
    loadEmails();
    loadStats();
  });
  document.getElementById('filter-category')?.addEventListener('change', e => {
    state.currentFilter.category = e.target.value || undefined;
    loadEmails();
  });

  // Focus Chips
  document.querySelectorAll('.focus-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      document.querySelectorAll('.focus-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      if (chip.dataset.filter === 'unread') {
        state.currentFilter.is_read = false;
        state.currentFilter.category = undefined;
      } else if (chip.dataset.filterCat) {
        state.currentFilter.category = chip.dataset.filterCat;
        state.currentFilter.is_read = undefined;
      } else {
        state.currentFilter.is_read = undefined;
        state.currentFilter.category = undefined;
      }
      loadEmails();
    });
  });

  // Detail Panel
  document.getElementById('btn-close-detail')?.addEventListener('click', closeDetailPanel);
  document.getElementById('detail-overlay')?.addEventListener('click', closeDetailPanel);

  // Chat
  document.getElementById('chat-fab-btn')?.addEventListener('click', toggleChat);
  document.getElementById('btn-close-chat-panel')?.addEventListener('click', toggleChat);
  document.getElementById('btn-chat-send')?.addEventListener('click', sendChatMessage);
  document.getElementById('chat-input')?.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChatMessage(); }
  });
  document.getElementById('chat-input')?.addEventListener('input', autoResizeTextarea);
  document.getElementById('btn-new-chat')?.addEventListener('click', startNewChat);

  // Compose Modal
  document.getElementById('btn-compose')?.addEventListener('click', openCompose);
  document.getElementById('btn-close-compose')?.addEventListener('click', () => closeModal('compose-overlay', 'compose-modal'));
  document.getElementById('btn-cancel-compose')?.addEventListener('click', () => closeModal('compose-overlay', 'compose-modal'));
  document.getElementById('compose-overlay')?.addEventListener('click', () => closeModal('compose-overlay', 'compose-modal'));
  document.getElementById('compose-form')?.addEventListener('submit', handleSendEmail);
  document.getElementById('btn-ai-compose')?.addEventListener('click', aiCompose);
  document.getElementById('btn-ai-rewrite')?.addEventListener('click', aiRewrite);
  document.getElementById('btn-toggle-schedule')?.addEventListener('click', () => {
    const row = document.getElementById('schedule-row');
    row.style.display = row.style.display === 'none' ? 'flex' : 'none';
  });
  document.getElementById('btn-clear-schedule')?.addEventListener('click', () => {
    document.getElementById('compose-schedule-at').value = '';
    document.getElementById('schedule-row').style.display = 'none';
  });

  // Settings Modal
  document.getElementById('btn-close-settings')?.addEventListener('click', () => closeModal('settings-overlay', 'settings-modal'));
  document.getElementById('btn-cancel-settings')?.addEventListener('click', () => closeModal('settings-overlay', 'settings-modal'));
  document.getElementById('settings-overlay')?.addEventListener('click', () => closeModal('settings-overlay', 'settings-modal'));
  document.getElementById('btn-save-settings')?.addEventListener('click', saveSettings);

  // Rule Modal
  document.getElementById('btn-close-rule')?.addEventListener('click', () => closeModal('rule-overlay', 'rule-modal'));
  document.getElementById('btn-cancel-rule')?.addEventListener('click', () => closeModal('rule-overlay', 'rule-modal'));
  document.getElementById('rule-overlay')?.addEventListener('click', () => closeModal('rule-overlay', 'rule-modal'));
  document.getElementById('btn-add-rule')?.addEventListener('click', openAddRule);
  document.getElementById('btn-save-rule')?.addEventListener('click', saveRule);

  // Search Contact Modal
  document.getElementById('btn-search-contact-chat')?.addEventListener('click', () => openModal('search-contact-overlay', 'search-contact-modal'));
  document.getElementById('btn-close-search-contact')?.addEventListener('click', () => closeModal('search-contact-overlay', 'search-contact-modal'));
  document.getElementById('search-contact-overlay')?.addEventListener('click', () => closeModal('search-contact-overlay', 'search-contact-modal'));
  let contactSearchDebounce;
  document.getElementById('contact-search-input')?.addEventListener('input', e => {
    clearTimeout(contactSearchDebounce);
    contactSearchDebounce = setTimeout(() => searchContacts(e.target.value), 300);
  });

  // Refresh buttons
  document.getElementById('btn-refresh-scheduled')?.addEventListener('click', loadScheduled);
  document.getElementById('btn-refresh-logs')?.addEventListener('click', loadLogs);
}

// ─── Accounts ──────────────────────────────────────────────
async function loadAccounts() {
  try {
    const data = await API.getAccounts();
    state.accounts = data.accounts || [];
    renderAccountList();
    updateAccountDropdowns();
    document.getElementById('stat-accounts-val').textContent = state.accounts.length;
    document.getElementById('no-accounts').style.display = state.accounts.length ? 'none' : 'block';

    if (state.accounts.length === 0) {
      openModal('dev-access-overlay', 'dev-access-modal');
    } else {
      closeModal('dev-access-overlay', 'dev-access-modal');
    }
  } catch (e) {
    console.error('loadAccounts error:', e);
  }
}

function renderAccountList() {
  const list = document.getElementById('account-list');
  if (!list) return;
  const noAccounts = document.getElementById('no-accounts');

  if (!state.accounts.length) {
    if (noAccounts) noAccounts.style.display = 'block';
    // Clear existing items
    list.querySelectorAll('.account-item').forEach(el => el.remove());
    return;
  }
  if (noAccounts) noAccounts.style.display = 'none';

  // Remove old items
  list.querySelectorAll('.account-item').forEach(el => el.remove());

  state.accounts.forEach(acc => {
    list.insertAdjacentHTML('beforeend', renderAccountItem(acc, acc.email === state.selectedAccount));
  });
}

function updateAccountDropdowns() {
  const filterSel = document.getElementById('filter-account');
  const composeSel = document.getElementById('compose-from');
  const ruleSel = document.getElementById('rule-account');

  [filterSel, composeSel, ruleSel].forEach(sel => {
    if (!sel) return;
    // Remove old account options
    [...sel.options].forEach(o => { if (o.value && o.value !== '') o.remove(); });
    state.accounts.forEach(acc => {
      const opt = new Option(acc.display_name || acc.email, acc.email);
      sel.appendChild(opt);
    });
  });
}

async function addAccount() {
  showToast('Opening Google sign-in…', 'info');
  try {
    const result = await API.addAccount();
    if (result.success) {
      showToast(`Account added: ${result.email}`, 'success');
      await loadAccounts();
    } else {
      showToast(result.error || 'Failed to add account', 'error');
    }
  } catch (e) {
    showToast('Error adding account', 'error');
  }
}

async function removeAccount(email) {
  if (!confirm(`Remove ${email} from Mail Agent?`)) return;
  try {
    await API.removeAccount(email);
    showToast('Account removed', 'success');
    if (state.selectedAccount === email) { state.selectedAccount = null; state.currentFilter.account = undefined; }
    await loadAccounts();
    await loadEmails();
    await loadStats();
  } catch {
    showToast('Error removing account', 'error');
  }
}

function selectAccount(email) {
  state.selectedAccount = email === state.selectedAccount ? null : email;
  state.currentFilter.account = state.selectedAccount || undefined;
  renderAccountList();
  loadEmails();
  loadStats();
}

// ─── Stats ─────────────────────────────────────────────────
async function loadStats() {
  try {
    const stats = await API.getStats(state.selectedAccount);
    document.getElementById('stat-total-val').textContent = stats.total || 0;
    document.getElementById('stat-unread-val').textContent = stats.unread || 0;
    document.getElementById('stat-important-val').textContent = stats.important || 0;
    document.getElementById('stat-critical-val').textContent = stats.priorities?.critical || 0;
    document.getElementById('badge-inbox').textContent = stats.unread || 0;
    document.getElementById('badge-important').textContent = stats.important || 0;
    document.getElementById('badge-critical').textContent = stats.priorities?.critical || 0;
  } catch { }
}

// ─── Email List ────────────────────────────────────────────
async function loadEmails() {
  const listEl = document.getElementById('email-list');
  const emptyEl = document.getElementById('empty-state');
  const skeleton = document.getElementById('loading-skeleton');

  if (!listEl) return;
  listEl.innerHTML = '';
  if (skeleton) skeleton.style.display = 'block';
  if (emptyEl) emptyEl.style.display = 'none';

  try {
    const params = {
      account: state.selectedAccount || undefined,
      limit: 100,
      ...state.currentFilter,
    };

    // For important view, filter by is_important
    if (state.currentView === 'important') params.is_important = true;
    if (state.currentView === 'critical') params.priority_score = 5;

    const data = await API.getEmails(params);
    state.emails = data.emails || [];

    if (skeleton) skeleton.style.display = 'none';

    if (!state.emails.length) {
      if (emptyEl) emptyEl.style.display = 'flex';
      return;
    }

    state.emails.forEach(email => listEl.appendChild(renderEmailCard(email)));
    document.getElementById('email-count').textContent = `${state.emails.length} email${state.emails.length !== 1 ? 's' : ''}`;
  } catch (e) {
    if (skeleton) skeleton.style.display = 'none';
    console.error('loadEmails error:', e);
  }
}

// ─── Views ─────────────────────────────────────────────────
function switchView(view) {
  state.currentView = view;

  // Update nav active state
  document.querySelectorAll('.nav-item').forEach(btn => btn.classList.remove('active'));
  document.getElementById(`nav-${view}`)?.classList.add('active');

  // Update title
  const titles = {
    inbox: 'Inbox', important: 'Important', critical: 'Critical',
    categories: 'Categories', scheduled: 'Scheduled', rules: 'Auto-Rules', logs: 'Activity Log',
  };
  document.getElementById('view-title').textContent = titles[view] || view;

  // Show/hide views
  const views = ['emails', 'categories', 'scheduled', 'rules', 'logs'];
  views.forEach(v => {
    const el = document.getElementById(`view-${v}`);
    if (el) el.style.display = 'none';
  });

  if (view === 'categories') {
    document.getElementById('view-categories').style.display = 'block';
    loadCategories();
  } else if (view === 'scheduled') {
    document.getElementById('view-scheduled').style.display = 'block';
    loadScheduled();
  } else if (view === 'rules') {
    document.getElementById('view-rules').style.display = 'block';
    loadRules();
  } else if (view === 'logs') {
    document.getElementById('view-logs').style.display = 'block';
    loadLogs();
  } else {
    document.getElementById('view-emails').style.display = 'flex';
    // Reset filters for special views
    state.currentFilter.is_important = undefined;
    state.currentFilter.priority_score = undefined;
    loadEmails();
  }
}

async function loadCategories() {
  try {
    const stats = await API.getStats(state.selectedAccount);
    const grid = document.getElementById('category-grid');
    if (!grid) return;
    const cats = stats.categories || {};
    grid.innerHTML = Object.entries(cats)
      .filter(([, count]) => count > 0)
      .sort((a, b) => b[1] - a[1])
      .map(([cat, count]) => renderCategoryCard(cat, count))
      .join('');
    if (!grid.innerHTML) grid.innerHTML = '<p style="color:var(--text-muted);font-size:13px;">No categories yet.</p>';
  } catch { }
}

async function loadScheduled() {
  try {
    const data = await API.getScheduledEmails();
    const list = document.getElementById('scheduled-list');
    const items = data.scheduled || [];
    const badge = document.getElementById('badge-scheduled');
    const pending = items.filter(s => s.status === 'pending').length;
    if (badge) badge.textContent = pending || '';
    if (!list) return;
    list.innerHTML = items.length
      ? items.map(renderScheduledItem).join('')
      : '<p style="color:var(--text-muted);font-size:13px;">No scheduled emails.</p>';
  } catch { }
}

async function loadRules() {
  try {
    const data = await API.getRules();
    const list = document.getElementById('rules-list');
    const rules = data.rules || [];
    if (!list) return;
    list.innerHTML = rules.length
      ? rules.map(renderRuleItem).join('')
      : '<p style="color:var(--text-muted);font-size:13px;">No rules defined. Click "+ Add Rule" to create one.</p>';
  } catch { }
}

async function loadLogs() {
  try {
    const data = await API.getLogs(100);
    const list = document.getElementById('log-list');
    const logs = data.logs || [];
    if (!list) return;
    list.innerHTML = logs.length
      ? logs.map(renderLogEntry).join('')
      : '<p style="color:var(--text-muted);font-size:13px;">No activity logged yet.</p>';
  } catch { }
}

function filterByCategory(category) {
  state.currentFilter.category = category;
  switchView('inbox');
}

// ─── Email Detail ──────────────────────────────────────────
async function openEmailDetail(id) {
  state.currentEmailId = id;
  try {
    const data = await API.getEmailDetail(id);
    const email = data.email;
    if (!email) return;

    const panel = document.getElementById('detail-panel');
    const content = document.getElementById('detail-content');
    const overlay = document.getElementById('detail-overlay');

    content.innerHTML = renderDetailContent(email);

    // Sync the header actions from content
    const innerActions = content.querySelector('#detail-header-actions-inner');
    const headerActions = document.getElementById('detail-header-actions');
    if (innerActions && headerActions) {
      headerActions.innerHTML = innerActions.innerHTML;
      innerActions.remove();
    }

    overlay.classList.add('visible');
    overlay.style.display = 'block';
    panel.classList.add('open');

    // Mark as read in list
    const card = document.querySelector(`.email-card[data-id="${id}"]`);
    if (card) card.classList.remove('unread');

    await loadStats();
  } catch (e) {
    showToast('Failed to load email', 'error');
  }
}

function closeDetailPanel() {
  const panel = document.getElementById('detail-panel');
  const overlay = document.getElementById('detail-overlay');
  panel.classList.remove('open');
  overlay.classList.remove('visible');
  setTimeout(() => { overlay.style.display = 'none'; }, 300);
  state.currentEmailId = null;
}

// ─── Sync ──────────────────────────────────────────────────
async function triggerSync() {
  const btn = document.getElementById('btn-sync');
  if (btn) { btn.classList.add('syncing'); document.getElementById('sync-btn-text').textContent = 'Syncing…'; }
  try {
    const result = await API.syncEmails(state.selectedAccount);
    if (!result.success) showToast(result.message || 'Sync failed', 'error');
  } catch {
    showToast('Sync request failed', 'error');
  }
}

function startSyncPoller() {
  state.syncPollInterval = setInterval(async () => {
    try {
      const status = await API.getSyncStatus();
      const progressWrap = document.getElementById('sync-progress-bar-wrap');
      const progressBar = document.getElementById('sync-bar');
      const msgEl = document.getElementById('sync-message');
      const btn = document.getElementById('btn-sync');
      const btnText = document.getElementById('sync-btn-text');

      if (status.is_syncing) {
        if (progressWrap) progressWrap.style.display = 'flex';
        const pct = status.total ? Math.round((status.current / status.total) * 100) : 50;
        if (progressBar) progressBar.style.width = `${pct}%`;
        if (msgEl) msgEl.textContent = status.message || 'Syncing…';
        if (btn) btn.classList.add('syncing');
        if (btnText) btnText.textContent = 'Syncing…';
      } else {
        if (progressWrap) progressWrap.style.display = 'none';
        if (btn) btn.classList.remove('syncing');
        if (btnText) btnText.textContent = 'Sync';
        // Reload data if just finished
        if (progressBar && progressBar.style.width === '100%') {
          progressBar.style.width = '0%';
          await loadEmails();
          await loadStats();
          showToast('Sync complete!', 'success');
        }
      }
    } catch { }
  }, 2000);
}

// ─── Chat Bot ──────────────────────────────────────────────
function toggleChat() {
  state.chatOpen = !state.chatOpen;
  const panel = document.getElementById('chat-panel');
  if (panel) panel.classList.toggle('open', state.chatOpen);
  if (state.chatOpen) {
    loadChatSessions();
  }
}

// ─── Markdown renderer for chat messages ─────────────────
function renderMarkdown(text) {
  if (!text) return '';
  // Escape HTML first (but preserve emojis)
  let html = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Bold: **text**
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');

  // Process line by line for bullets and numbering
  const lines = html.split('\n');
  const result = [];
  let inList = false;
  let listType = null;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const bulletMatch = line.match(/^\s*[-*•]\s+(.+)/);
    const numberedMatch = line.match(/^\s*(\d+)\.\s+(.+)/);

    if (bulletMatch) {
      if (!inList || listType !== 'ul') {
        if (inList) result.push(listType === 'ul' ? '</ul>' : '</ol>');
        result.push('<ul class="chat-list">');
        inList = true; listType = 'ul';
      }
      result.push(`<li>${bulletMatch[1]}</li>`);
    } else if (numberedMatch) {
      if (!inList || listType !== 'ol') {
        if (inList) result.push(listType === 'ul' ? '</ul>' : '</ol>');
        result.push('<ol class="chat-list">');
        inList = true; listType = 'ol';
      }
      result.push(`<li>${numberedMatch[2]}</li>`);
    } else {
      if (inList) {
        result.push(listType === 'ul' ? '</ul>' : '</ol>');
        inList = false; listType = null;
      }
      if (line.trim() === '') {
        result.push('<br>');
      } else {
        result.push(line + '<br>');
      }
    }
  }
  if (inList) result.push(listType === 'ul' ? '</ul>' : '</ol>');

  // Clean up duplicate <br> at end
  return result.join('').replace(/(<br>){3,}/g, '<br><br>').replace(/<br>$/, '');
}

// ─── Load session list in sidebar ─────────────────────────
async function loadChatSessions() {
  try {
    const data = await API.getChatSessions();
    const sessions = data.sessions || [];
    const listEl = document.getElementById('chat-session-list');
    if (!listEl) return;

    if (sessions.length === 0) {
      listEl.innerHTML = '<p class="chat-sessions-empty">💬 No past chats yet</p>';
      return;
    }

    listEl.innerHTML = sessions.map(s => {
      const isActive = s.session_id === state.chatSessionId;
      const timeAgo = formatChatTime(s.last_message_at);
      return `
        <div class="chat-session-item${isActive ? ' active' : ''}" onclick="selectChatSession('${escAttr(s.session_id)}')" title="${escAttr(s.title)}">
          <div class="session-icon">💬</div>
          <div class="session-info">
            <div class="session-title">${escHtml(s.title)}</div>
            <div class="session-time">${timeAgo}</div>
          </div>
        </div>
      `;
    }).join('');
  } catch (e) {
    console.error('Failed to load chat sessions', e);
  }
}

function formatChatTime(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    const now = new Date();
    const diff = now - d;
    if (diff < 60000) return 'just now';
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
    if (diff < 604800000) return d.toLocaleDateString('en', { weekday: 'short' });
    return d.toLocaleDateString('en', { month: 'short', day: 'numeric' });
  } catch { return ''; }
}

// ─── Start a new chat session ─────────────────────────────
function startNewChat() {
  const newId = generateUUID();
  state.chatSessionId = newId;
  localStorage.setItem('mailAgentChatSession', newId);
  localStorage.setItem('mailAgentChatTimestamp', Date.now().toString());

  const container = document.getElementById('chat-messages');
  if (container) {
    container.innerHTML = '';
    appendChatMessage('bot', '✨ New chat started! How can I help you with your emails today?\n\n- 📬 Ask me to summarize emails\n- 🔍 Search for emails by topic\n- ✍️ Help you compose or reply');
  }

  // Deselect active session in sidebar
  document.querySelectorAll('.chat-session-item').forEach(el => el.classList.remove('active'));
}

// ─── Select a past chat session ───────────────────────────
async function selectChatSession(sessionId) {
  state.chatSessionId = sessionId;
  localStorage.setItem('mailAgentChatSession', sessionId);
  localStorage.setItem('mailAgentChatTimestamp', Date.now().toString());

  // Update sidebar active state
  document.querySelectorAll('.chat-session-item').forEach(el => {
    el.classList.toggle('active', el.getAttribute('onclick')?.includes(sessionId));
  });

  await loadChatHistory();
}

async function loadChatHistory() {
  try {
    const data = await API.getChatHistory(state.chatSessionId, 50);
    const history = data.history || [];
    const container = document.getElementById('chat-messages');
    if (!container) return;

    // Clear existing
    container.innerHTML = '';

    if (history.length === 0) {
      // Show welcome message
      appendChatMessage('bot', '👋 Hi! I\'m your **Mail Assistant**. Ask me anything about your emails!\n\n💡 Try asking:\n- "Summarize my unread emails"\n- "What emails need replies?"\n- "Show me work emails"');
      return;
    }

    // Render from oldest to newest
    [...history].forEach(msg => {
      appendChatMessage('user', msg.user_message, false);
      appendChatMessage('bot', msg.agent_response, false);
    });
    container.scrollTop = container.scrollHeight;
  } catch (e) {
    console.error('Failed to load chat history', e);
  }
}

async function sendChatMessage(action = null) {
  const input = document.getElementById('chat-input');
  const message = action || (input ? (input.value || '').trim() : '');
  if (!message) return;

  if (!action && input) {
    input.value = '';
    input.style.height = 'auto';
  }

  // Always update timestamp on activity
  localStorage.setItem('mailAgentChatTimestamp', Date.now().toString());

  // Do not show the hidden slash commands in the UI
  if (!message.startsWith('/')) {
    appendChatMessage('user', message);
  } else if (message.startsWith('/summarize_contact ')) {
    appendChatMessage('user', `📋 Summarize emails from ${message.replace('/summarize_contact ', '')}`);
  } else if (message.startsWith('/info_email ')) {
    const parts = message.replace('/info_email ', '').split('|');
    const emailTitle = parts[1] || `Email #${parts[0]}`;
    appendChatMessage('user', `📧 Get details about: "${emailTitle}"`);
  }

  showChatTyping();

  const scope = document.getElementById('chat-scope')?.value || 'all';
  const account = scope === 'account' ? (state.selectedAccount || undefined) : undefined;

  try {
    const result = await API.chat(message, scope, account, state.chatSessionId);
    hideChatTyping();
    if (result && result.success) {
      appendChatMessage('bot', result.reply, true, result.options, result.email_links);
      // Refresh session list after each message
      await loadChatSessions();
    } else {
      const errMsg = result?.error || 'unknown error';
      console.error('[Chat] API error:', errMsg);
      appendChatMessage('bot', `❌ Sorry, I couldn't process that: ${errMsg}`);
    }
  } catch (err) {
    hideChatTyping();
    console.error('[Chat] Network error:', err);
    appendChatMessage('bot', '⚠️ Connection error. Please check the server is running and try again.');
  }
}


function handleChatOptionClick(action) {
  // Remove options from the UI once clicked to prevent double clicks
  document.querySelectorAll('.chat-options-container').forEach(el => el.remove());
  sendChatMessage(action);
}

function appendChatMessage(role, text, animate = true, options = null, emailLinks = null) {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const msgEl = document.createElement('div');
  msgEl.className = `chat-msg ${role}`;

  // Avatar
  const avatarEmoji = role === 'bot' ? '🤖' : '👤';

  // Render message content
  const renderedText = renderMarkdown(text);

  // Build options HTML
  let optionsHtml = '';
  if (options && options.length > 0) {
    optionsHtml = `
      <div class="chat-options-container">
        ${options.map(opt => `<button class="chat-option-btn" onclick="handleChatOptionClick('${escAttr(opt.action)}')">📧 ${escHtml(opt.label)}</button>`).join('')}
      </div>
    `;
  }

  // Build email link buttons
  let emailLinksHtml = '';
  if (emailLinks && emailLinks.length > 0) {
    emailLinksHtml = emailLinks.map(link => `
      <button class="chat-open-email-btn" onclick="openEmailDetail(${link.id}); return false;">
        📬 Open Email: <em>${escHtml(link.subject || 'View Email')}</em>
      </button>
    `).join('');
  }

  // Format time
  const now = new Date();
  const timeStr = now.toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' });

  msgEl.innerHTML = `
    <div class="chat-avatar ${role}-avatar">${avatarEmoji}</div>
    <div class="chat-bubble-wrap">
      <div class="chat-bubble">${renderedText}${optionsHtml}${emailLinksHtml}</div>
      <span class="chat-time">${timeStr}</span>
    </div>
  `;

  if (animate) msgEl.classList.add('msg-animate');
  container.appendChild(msgEl);
  container.scrollTop = container.scrollHeight;
}

function showChatTyping() {
  const container = document.getElementById('chat-messages');
  if (!container) return;
  const typing = document.createElement('div');
  typing.className = 'chat-msg bot';
  typing.id = 'chat-typing-indicator';
  typing.innerHTML = `
    <div class="chat-avatar bot-avatar">🤖</div>
    <div class="chat-bubble-wrap">
      <div class="chat-bubble typing-bubble">
        <div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div>
      </div>
    </div>
  `;
  container.appendChild(typing);
  container.scrollTop = container.scrollHeight;
}

function hideChatTyping() {
  document.getElementById('chat-typing-indicator')?.remove();
}

function autoResizeTextarea(e) {
  e.target.style.height = 'auto';
  e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px';
}


// ─── Compose ───────────────────────────────────────────────
function openCompose() {
  openModal('compose-overlay', 'compose-modal');
  // Pre-select first account
  if (state.accounts.length) {
    document.getElementById('compose-from').value = state.accounts[0].email;
  }
}

async function aiCompose() {
  const instruction = document.getElementById('ai-instruction')?.value?.trim();
  if (!instruction) { showToast('Please describe what you want to send', 'warning'); return; }

  const btn = document.getElementById('btn-ai-compose');
  btn.textContent = '⏳ Generating…';
  btn.disabled = true;

  try {
    const result = await API.composeEmail(instruction);
    if (result.success) {
      document.getElementById('compose-to').value = result.to_hint || '';
      document.getElementById('compose-subject').value = result.subject || '';
      document.getElementById('compose-body').value = result.body || '';

      if (result.schedule_hint) {
        document.getElementById('schedule-row').style.display = 'flex';
        showToast(`Schedule hint detected: "${result.schedule_hint}". Select date/time or let AI set it.`, 'info', 5000);
      }
      showToast('Email composed by AI!', 'success');
    } else {
      showToast(result.error || 'AI compose failed', 'error');
    }
  } catch {
    showToast('Error composing email', 'error');
  } finally {
    btn.textContent = '✨ Generate Email';
    btn.disabled = false;
  }
}

async function aiRewrite() {
  const body = document.getElementById('compose-body')?.value?.trim();
  if (!body) { showToast('Nothing to rewrite', 'warning'); return; }
  const btn = document.getElementById('btn-ai-rewrite');
  btn.textContent = '⏳ Rewriting…';
  btn.disabled = true;
  try {
    const result = await API.rewriteEmail(body);
    if (result.success) {
      document.getElementById('compose-body').value = result.text;
      showToast('Email rewritten!', 'success');
    } else {
      showToast(result.error || 'Rewrite failed', 'error');
    }
  } catch {
    showToast('Error rewriting email', 'error');
  } finally {
    btn.textContent = '✨ Make Professional';
    btn.disabled = false;
  }
}

async function handleSendEmail(e) {
  e.preventDefault();
  const from = document.getElementById('compose-from')?.value;
  const to = document.getElementById('compose-to')?.value;
  const subject = document.getElementById('compose-subject')?.value;
  const body = document.getElementById('compose-body')?.value;
  const scheduleAt = document.getElementById('compose-schedule-at')?.value;

  if (!from || !to) { showToast('Please fill From and To fields', 'warning'); return; }

  const btn = document.getElementById('btn-send');
  btn.textContent = '⏳ Sending…';
  btn.disabled = true;

  try {
    if (scheduleAt) {
      const isoDate = new Date(scheduleAt).toISOString();
      const result = await API.scheduleEmail(from, to, subject, body, isoDate, '');
      if (result.success) {
        showToast(`Email scheduled for ${new Date(isoDate).toLocaleString()}`, 'success');
        closeModal('compose-overlay', 'compose-modal');
        document.getElementById('compose-form').reset();
        document.getElementById('schedule-row').style.display = 'none';
        document.getElementById('ai-instruction').value = '';
        loadScheduled();
      } else {
        showToast(result.error || 'Schedule failed', 'error');
      }
    } else {
      const result = await API.sendEmail(from, to, subject, body);
      if (result.success) {
        showToast('Email sent!', 'success');
        closeModal('compose-overlay', 'compose-modal');
        document.getElementById('compose-form').reset();
        document.getElementById('ai-instruction').value = '';
      } else {
        showToast(result.error || 'Send failed', 'error');
      }
    }
  } catch {
    showToast('Error sending email', 'error');
  } finally {
    btn.textContent = 'Send';
    btn.disabled = false;
  }
}

// ─── Quick Reply ────────────────────────────────────────────
async function generateDraftReply(emailId) {
  const btn = event.target;
  btn.textContent = '⏳ Drafting…';
  btn.disabled = true;
  try {
    const result = await API.generateDraftReply(emailId);
    if (result.success) {
      document.getElementById('quick-reply-body').value = result.draft_body;
      showToast('Draft generated!', 'success');
    } else {
      showToast(result.error || 'Draft failed', 'error');
    }
  } catch {
    showToast('Error generating draft', 'error');
  } finally {
    btn.textContent = '✨ AI Draft';
    btn.disabled = false;
  }
}

async function sendQuickReply(emailId, senderEmail, subject, fromAccount) {
  const body = document.getElementById('quick-reply-body')?.value?.trim();
  if (!body) { showToast('Write a reply first', 'warning'); return; }
  if (!fromAccount) { showToast('Could not determine sender account', 'error'); return; }
  try {
    const result = await API.sendEmail(fromAccount, senderEmail, `Re: ${subject}`, body);
    if (result.success) {
      showToast('Reply sent!', 'success');
      document.getElementById('quick-reply-body').value = '';
    } else {
      showToast(result.error || 'Send failed', 'error');
    }
  } catch {
    showToast('Error sending reply', 'error');
  }
}

async function toggleEmailImportant(emailId, makeImportant) {
  try {
    const result = await API.toggleImportant(emailId, makeImportant);
    if (result.success) {
      showToast(makeImportant ? 'Marked as important ⭐' : 'Removed from important', 'success');
      // Re-open detail to reflect change
      await openEmailDetail(emailId);
      await loadStats();
    }
  } catch {
    showToast('Error updating importance', 'error');
  }
}

// ─── Scheduled ──────────────────────────────────────────────
async function cancelScheduled(id) {
  if (!confirm('Cancel this scheduled email?')) return;
  try {
    await API.deleteScheduledEmail(id);
    showToast('Scheduled email cancelled', 'success');
    loadScheduled();
  } catch {
    showToast('Error cancelling scheduled email', 'error');
  }
}

// ─── Rules ─────────────────────────────────────────────────
function openAddRule() {
  document.getElementById('rule-modal-title').textContent = 'New Auto-Reply Rule';
  document.getElementById('rule-edit-id').value = '';
  document.getElementById('rule-name').value = '';
  document.getElementById('rule-keywords').value = '';
  document.getElementById('rule-template').value = '';
  document.getElementById('rule-time').value = '';
  document.getElementById('rule-account').value = '';
  openModal('rule-overlay', 'rule-modal');
}

async function editRule(id) {
  try {
    const data = await API.getRules();
    const rule = (data.rules || []).find(r => r.id === id);
    if (!rule) return;
    document.getElementById('rule-modal-title').textContent = 'Edit Auto-Reply Rule';
    document.getElementById('rule-edit-id').value = id;
    document.getElementById('rule-name').value = rule.name || '';
    document.getElementById('rule-keywords').value = Array.isArray(rule.trigger_keywords)
      ? rule.trigger_keywords.join(', ')
      : (rule.trigger_keywords || '');
    document.getElementById('rule-template').value = rule.reply_template || '';
    document.getElementById('rule-time').value = rule.time_condition || '';
    document.getElementById('rule-account').value = rule.account || '';
    openModal('rule-overlay', 'rule-modal');
  } catch {
    showToast('Error loading rule', 'error');
  }
}

async function saveRule() {
  const editId = document.getElementById('rule-edit-id').value;
  const name = document.getElementById('rule-name').value.trim();
  const keywordsRaw = document.getElementById('rule-keywords').value.trim();
  const template = document.getElementById('rule-template').value.trim();
  const timeCondition = document.getElementById('rule-time').value.trim();
  const account = document.getElementById('rule-account').value;

  if (!name || !keywordsRaw || !template) {
    showToast('Name, keywords, and reply template are required', 'warning');
    return;
  }

  const keywords = keywordsRaw.split(',').map(k => k.trim()).filter(Boolean);
  const payload = { name, trigger_keywords: keywords, reply_template: template, time_condition: timeCondition, account };

  try {
    if (editId) {
      await API.updateRule(parseInt(editId), payload);
      showToast('Rule updated!', 'success');
    } else {
      await API.createRule(payload);
      showToast('Rule created!', 'success');
    }
    closeModal('rule-overlay', 'rule-modal');
    loadRules();
  } catch {
    showToast('Error saving rule', 'error');
  }
}

async function deleteRuleById(id) {
  if (!confirm('Delete this auto-reply rule?')) return;
  try {
    await API.deleteRule(id);
    showToast('Rule deleted', 'success');
    loadRules();
  } catch {
    showToast('Error deleting rule', 'error');
  }
}

async function toggleRule(id, isActive) {
  try {
    await API.updateRule(id, { is_active: isActive });
    showToast(isActive ? 'Rule enabled' : 'Rule disabled', 'success');
    loadRules();
  } catch {
    showToast('Error updating rule', 'error');
  }
}

// ─── Settings ──────────────────────────────────────────────
function openSettings() {
  openModal('settings-overlay', 'settings-modal');
  loadSettings();
  refreshModelStatus();
}

async function loadSettings() {
  try {
    const data = await API.getSettings();
    const s = data.settings || {};
    state.isCloudMode = s.ai_provider === 'cloud';

    // Update model toggle
    updateModelToggleUI();

    // Settings modal fields
    const localUrl = document.getElementById('local-base-url');
    const localModel = document.getElementById('local-model');
    const cloudModel = document.getElementById('cloud-model');
    const persona = document.getElementById('persona-body');
    const forceProvider = document.getElementById('force-provider');

    if (localUrl) localUrl.value = s.local_base_url || '';
    if (localModel) localModel.value = s.local_model || '';
    if (cloudModel) cloudModel.value = s.cloud_model || '';
    if (persona) persona.value = s.agent_persona || '';
    if (forceProvider) forceProvider.checked = !!s.force_provider;

    // Show/hide local/cloud fields
    const localFields = document.getElementById('local-fields');
    const cloudFields = document.getElementById('cloud-fields');
    if (localFields) localFields.style.display = state.isCloudMode ? 'none' : 'block';
    if (cloudFields) cloudFields.style.display = state.isCloudMode ? 'block' : 'none';

    // Auto sync
    const autoSyncStatus = await API.getAutoSyncStatus();
    const autoToggle = document.getElementById('auto-sync-toggle');
    const autoInterval = document.getElementById('auto-sync-interval');
    if (autoToggle) autoToggle.checked = autoSyncStatus.auto_sync_enabled || false;
    if (autoInterval) autoInterval.value = autoSyncStatus.interval || 300;
  } catch (e) {
    console.error('loadSettings error:', e);
  }
}

async function saveSettings() {
  try {
    const provider = state.isCloudMode ? 'cloud' : 'local';
    const payload = {
      ai_provider: provider,
      local_base_url: document.getElementById('local-base-url')?.value || '',
      local_model: document.getElementById('local-model')?.value || '',
      cloud_model: document.getElementById('cloud-model')?.value || '',
      agent_persona: document.getElementById('persona-body')?.value || '',
      force_provider: document.getElementById('force-provider')?.checked || false,
    };
    await API.saveSettings(payload);

    // Auto sync
    const enabled = document.getElementById('auto-sync-toggle')?.checked || false;
    const interval = parseInt(document.getElementById('auto-sync-interval')?.value || '300');
    await API.controlAutoSync(enabled, interval);

    showToast('Settings saved!', 'success');
    closeModal('settings-overlay', 'settings-modal');
    await refreshModelStatus();
  } catch {
    showToast('Error saving settings', 'error');
  }
}

// ─── Model Toggle ──────────────────────────────────────────
async function toggleModelProvider() {
  state.isCloudMode = !state.isCloudMode;
  updateModelToggleUI();

  try {
    await API.saveSettings({ ai_provider: state.isCloudMode ? 'cloud' : 'local' });
    showToast(`Switched to ${state.isCloudMode ? '☁️ Cloud (Nvidia NIM)' : '🖥️ Local (LM Studio)'}`, 'info');
    await refreshModelStatus();
  } catch {
    showToast('Error switching provider', 'error');
  }
}

function updateModelToggleUI() {
  const track = document.getElementById('model-toggle-track');
  const settingsTrack = document.getElementById('settings-toggle-track');
  const localLabel = document.getElementById('toggle-local-label');
  const cloudLabel = document.getElementById('toggle-cloud-label');
  const providerLabelText = document.getElementById('provider-label-text');
  const providerSublabel = document.getElementById('provider-sublabel');
  const localFields = document.getElementById('local-fields');
  const cloudFields = document.getElementById('cloud-fields');

  if (track) track.classList.toggle('cloud-mode', state.isCloudMode);
  if (settingsTrack) settingsTrack.classList.toggle('cloud-mode', state.isCloudMode);
  if (localLabel) localLabel.classList.toggle('active', !state.isCloudMode);
  if (cloudLabel) cloudLabel.classList.toggle('active', state.isCloudMode);

  if (providerLabelText) providerLabelText.textContent = state.isCloudMode ? '☁️ Cloud (Nvidia NIM)' : '🖥️ Local (LM Studio)';
  if (providerSublabel) providerSublabel.textContent = state.isCloudMode ? 'Using Nvidia NIM API' : 'Running on your computer';
  if (localFields) localFields.style.display = state.isCloudMode ? 'none' : 'block';
  if (cloudFields) cloudFields.style.display = state.isCloudMode ? 'block' : 'none';
}

function settingsToggleProvider() {
  state.isCloudMode = !state.isCloudMode;
  updateModelToggleUI();
}

async function refreshModelStatus() {
  const statusDot = document.getElementById('model-status-dot');
  if (statusDot) { statusDot.className = 'toggle-status-dot checking'; }

  try {
    const status = await API.getModelStatus();
    const isHealthy = status.is_healthy;

    if (statusDot) statusDot.className = `toggle-status-dot ${isHealthy ? 'online' : 'offline'}`;

    const indicator = document.getElementById('model-status-indicator');
    const name = document.getElementById('model-status-name');
    const msg = document.getElementById('model-status-msg');

    if (indicator) indicator.className = `model-status-indicator ${isHealthy ? 'online' : 'offline'}`;
    if (name) name.textContent = `${status.current_provider?.toUpperCase() || '?'} — ${status.model_name || 'Unknown'}`;
    if (msg) msg.textContent = status.health_message || '';
  } catch {
    if (statusDot) statusDot.className = 'toggle-status-dot offline';
  }
}

// ─── Test Connection ───────────────────────────────────────
async function testLocal() {
  const btn = document.getElementById('btn-test-local');
  const result = document.getElementById('test-local-result');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Testing…'; }
  if (result) { result.className = 'test-result'; result.style.display = 'none'; }

  try {
    const url = document.getElementById('local-base-url')?.value || '';
    const model = document.getElementById('local-model')?.value || '';
    const data = await API.testLocalModel(url, model);
    if (result) {
      result.style.display = 'block';
      result.className = `test-result ${data.success ? 'success' : 'error'}`;
      if (data.success) {
        result.innerHTML = `
          <div style="font-weight: 700; margin-bottom: 6px; font-size: 14px;">📋 Test Report: Success</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Status | <strong>Value:</strong> ✅ Connected</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Model | <strong>Value:</strong> <code>${data.model || 'auto-detect'}</code></div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Endpoint | <strong>Value:</strong> <code style="font-size: 11px; word-break: break-all;">${data.endpoint}</code></div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Latency | <strong>Value:</strong> ${data.latency_sec} seconds</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Preview | <strong>Value:</strong> <em style="background: rgba(255,255,255,0.06); padding: 2px 4px; border-radius: 4px;">"${data.response_preview}"</em></div>
        `;
      } else {
        result.innerHTML = `
          <div style="font-weight: 700; margin-bottom: 6px; font-size: 14px;">📋 Test Report: Failed</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Model | <strong>Value:</strong> <code>${data.model || 'Unknown'}</code></div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Endpoint | <strong>Value:</strong> <code style="font-size: 11px; word-break: break-all;">${data.endpoint || 'Unknown'}</code></div>
          <div style="color: #ff4a4a; margin-top: 6px;"><strong>Error:</strong> ${data.error || 'Connection failed'}</div>
        `;
      }
    }
  } catch (e) {
    if (result) {
      result.style.display = 'block';
      result.className = 'test-result error';
      result.textContent = `✕ Error: ${e.message}`;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '🖥️ Test Local'; }
  }
}

async function testCloud() {
  const btn = document.getElementById('btn-test-cloud');
  const result = document.getElementById('test-cloud-result');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ Testing…'; }
  if (result) { result.className = 'test-result'; result.style.display = 'none'; }

  try {
    const model = document.getElementById('cloud-model')?.value || '';
    const data = await API.testCloudModel(model);
    if (result) {
      result.style.display = 'block';
      result.className = `test-result ${data.success ? 'success' : 'error'}`;
      if (data.success) {
        result.innerHTML = `
          <div style="font-weight: 700; margin-bottom: 6px; font-size: 14px;">📋 Test Report: Success</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Status | <strong>Value:</strong> ✅ Connected</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Model | <strong>Value:</strong> <code>${data.model}</code></div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Endpoint | <strong>Value:</strong> <code style="font-size: 11px; word-break: break-all;">${data.endpoint}</code></div>
          ${data.api_key_obscured ? `<div style="margin-bottom: 4px;"><strong>Metric:</strong> API Key | <strong>Value:</strong> <code>${data.api_key_obscured}</code></div>` : ''}
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Latency | <strong>Value:</strong> ${data.latency_sec} seconds</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Preview | <strong>Value:</strong> <em style="background: rgba(255,255,255,0.06); padding: 2px 4px; border-radius: 4px;">"${data.response_preview}"</em></div>
        `;
      } else {
        result.innerHTML = `
          <div style="font-weight: 700; margin-bottom: 6px; font-size: 14px;">📋 Test Report: Failed</div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Model | <strong>Value:</strong> <code>${data.model || 'Unknown'}</code></div>
          <div style="margin-bottom: 4px;"><strong>Metric:</strong> Endpoint | <strong>Value:</strong> <code style="font-size: 11px; word-break: break-all;">${data.endpoint || 'Unknown'}</code></div>
          ${data.api_key_obscured ? `<div style="margin-bottom: 4px;"><strong>Metric:</strong> API Key | <strong>Value:</strong> <code>${data.api_key_obscured}</code></div>` : ''}
          <div style="color: #ff4a4a; margin-top: 6px;"><strong>Error:</strong> ${data.error || 'Connection failed'}</div>
        `;
      }
    }
  } catch (e) {
    if (result) {
      result.style.display = 'block';
      result.className = 'test-result error';
      result.textContent = `✕ Error: ${e.message}`;
    }
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '☁️ Test Cloud'; }
  }
}

// ─── Contact Search ───────────────────────────────────────
async function searchContacts(query) {
  const resultsDiv = document.getElementById('contact-search-results');
  if (!resultsDiv) return;

  if (!query || query.trim() === '') {
    resultsDiv.innerHTML = '<p class="text-muted" style="font-size:12px;">Start typing to search contacts.</p>';
    return;
  }

  try {
    const data = await API.searchContacts(query);
    const contacts = data.contacts || [];

    if (contacts.length === 0) {
      resultsDiv.innerHTML = '<p class="text-muted" style="font-size:12px;">No contacts found.</p>';
      return;
    }

    resultsDiv.innerHTML = contacts.map(c => `
      <div class="account-item" style="cursor:pointer;" onclick="selectContactForChat('${escAttr(c.sender_email)}')">
        <div class="account-avatar" style="background:${getAvatarColor(c.sender_email)}">${getInitials(c.sender || c.sender_email)}</div>
        <div class="account-info">
          <span class="account-name">${escHtml(c.sender || c.sender_email)}</span>
          <span class="text-muted" style="font-size:11px;">${escHtml(c.sender_email)}</span>
        </div>
      </div>
    `).join('');
  } catch (e) {
    resultsDiv.innerHTML = '<p class="text-muted" style="font-size:12px;color:var(--danger)">Error searching contacts.</p>';
  }
}

function selectContactForChat(email) {
  closeModal('search-contact-overlay', 'search-contact-modal');
  const chatInput = document.getElementById('chat-input');
  if (chatInput) {
    chatInput.value = `Summarize emails from ${email}`;
    chatInput.focus();
  }
}
