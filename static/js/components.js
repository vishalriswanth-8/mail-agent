/**
 * Mail Agent Components
 * Pure functions that return HTML strings or DOM elements.
 */

const CATEGORY_ICONS = {
  work: '💼', personal: '👤', finance: '💰', newsletter: '📰',
  social: '🌐', promotion: '🏷️', security: '🔒', 'auto-reply': '🤖', other: '📧',
};

const PRIORITY_LABELS = {
  5: { label: 'Critical', cls: 'critical' },
  4: { label: 'Important', cls: 'important' },
  3: { label: 'Normal', cls: 'normal' },
  2: { label: 'Low', cls: 'low' },
  1: { label: 'Low', cls: 'low' },
};

const LOG_ICONS = {
  sync_complete: { icon: '🔄', cls: 'log-icon-sync' },
  sync_error: { icon: '❌', cls: 'log-icon-error' },
  email_sent: { icon: '📤', cls: 'log-icon-sent' },
  email_scheduled: { icon: '🕒', cls: 'log-icon-sent' },
  email_error: { icon: '❌', cls: 'log-icon-error' },
  auto_reply_sent: { icon: '🤖', cls: 'log-icon-rule' },
  importance_detected: { icon: '⭐', cls: 'log-icon-important' },
  manual_important: { icon: '⭐', cls: 'log-icon-important' },
  model_switch: { icon: '🔀', cls: 'log-icon-sync' },
  rule_created: { icon: '📋', cls: 'log-icon-rule' },
  rule_deleted: { icon: '🗑️', cls: 'log-icon-rule' },
  account_added: { icon: '👤', cls: 'log-icon-sync' },
  account_removed: { icon: '👤', cls: 'log-icon-error' },
};

function getAvatarColor(name) {
  const colors = [
    'linear-gradient(135deg,#6366f1,#8b5cf6)',
    'linear-gradient(135deg,#ec4899,#f43f5e)',
    'linear-gradient(135deg,#10b981,#06b6d4)',
    'linear-gradient(135deg,#f59e0b,#ef4444)',
    'linear-gradient(135deg,#3b82f6,#6366f1)',
    'linear-gradient(135deg,#8b5cf6,#ec4899)',
  ];
  let hash = 0;
  for (let i = 0; i < (name || '').length; i++) hash += name.charCodeAt(i);
  return colors[hash % colors.length];
}

function getInitials(name) {
  if (!name) return '?';
  const parts = name.replace(/<.*>/, '').trim().split(/\s+/);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (parts[0] || '?')[0].toUpperCase();
}

function formatDate(dateStr) {
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
  } catch {
    return dateStr;
  }
}

function formatDateTime(dateStr) {
  if (!dateStr) return '';
  try {
    const d = new Date(dateStr);
    return d.toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}

/**
 * Render a single email card.
 */
function renderEmailCard(email) {
  const priorityScore = email.priority_score || 3;
  const priorityInfo = PRIORITY_LABELS[priorityScore] || PRIORITY_LABELS[3];
  const category = email.category || 'other';
  const sender = email.sender || 'Unknown';
  const initials = getInitials(sender);
  const avatarBg = getAvatarColor(sender);
  const isUnread = !email.is_read;
  const isImportant = email.is_important;
  const shortSummary = email.short_summary || email.summary || email.snippet || '';

  const card = document.createElement('div');
  card.className = `email-card priority-${priorityInfo.cls}${isUnread ? ' unread' : ''}${isImportant ? ' important-email' : ''}`;
  card.dataset.id = email.id;
  card.dataset.account = email.account || '';

  card.innerHTML = `
    <div class="sender-avatar" style="background:${avatarBg};">${initials}</div>
    <div class="email-card-body">
      <div class="email-card-top">
        <span class="email-sender">${escHtml(extractSenderName(sender))}</span>
        <span class="email-time">${formatDate(email.internal_date ? new Date(parseInt(email.internal_date)).toISOString() : email.date)}</span>
      </div>
      <div class="email-subject">${escHtml(email.subject || '(No Subject)')}</div>
      ${shortSummary ? `<div class="email-summary">${escHtml(shortSummary)}</div>` : ''}
      <div class="email-card-footer">
        <span class="tag tag-priority-${priorityInfo.cls}">${priorityInfo.label}</span>
        <span class="tag tag-cat-${category}">${CATEGORY_ICONS[category] || '📧'} ${capitalize(category)}</span>
        <span class="account-badge">${escHtml(email.account || '')}</span>
      </div>
    </div>
  `;

  card.addEventListener('click', () => openEmailDetail(email.id));
  return card;
}

/**
 * Render full email detail panel content.
 */
function renderDetailContent(email) {
  const priorityScore = email.priority_score || 3;
  const priorityInfo = PRIORITY_LABELS[priorityScore] || PRIORITY_LABELS[3];
  const category = email.category || 'other';

  let keyPointsHTML = '';
  try {
    const kp = typeof email.key_points === 'string' ? JSON.parse(email.key_points) : (email.key_points || []);
    if (kp.length) {
      keyPointsHTML = `
        <div>
          <div class="detail-section-title">Key Points</div>
          <div class="key-point-list">${kp.map(p => `
            <div class="key-point-item"><div class="key-point-dot"></div><span>${escHtml(p)}</span></div>
          `).join('')}</div>
        </div>`;
    }
  } catch {}

  let actionItemsHTML = '';
  try {
    const ai = typeof email.action_items === 'string' ? JSON.parse(email.action_items) : (email.action_items || []);
    if (ai.length) {
      actionItemsHTML = `
        <div>
          <div class="detail-section-title">Action Items</div>
          <div class="action-list">${ai.map(a => `
            <div class="action-item">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--accent-primary)" stroke-width="2.5">
                <polyline points="9 11 12 14 22 4"/>
                <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
              </svg>
              <span>${escHtml(a)}</span>
            </div>
          `).join('')}</div>
        </div>`;
    }
  } catch {}

  const body = email.body || email.snippet || '(No content)';

  return `
    <div>
      <div class="detail-header-actions" id="detail-header-actions-inner">
        <span class="tag tag-priority-${priorityInfo.cls}">${priorityInfo.label}</span>
        <span class="tag tag-cat-${category}">${CATEGORY_ICONS[category] || '📧'} ${capitalize(category)}</span>
        ${email.is_important ? '<span class="tag" style="background:rgba(245,158,11,0.15);color:#f59e0b;">⭐ Important</span>' : ''}
      </div>
    </div>
    <div class="detail-subject">${escHtml(email.subject || '(No Subject)')}</div>
    <div class="detail-meta">
      <div class="detail-meta-row"><span class="detail-meta-label">From</span><span class="detail-meta-value">${escHtml(email.sender || '')}</span></div>
      <div class="detail-meta-row"><span class="detail-meta-label">To</span><span class="detail-meta-value">${escHtml(email.recipient || email.account || '')}</span></div>
      <div class="detail-meta-row"><span class="detail-meta-label">Date</span><span class="detail-meta-value">${escHtml(email.date || '')}</span></div>
      <div class="detail-meta-row"><span class="detail-meta-label">Account</span><span class="detail-meta-value">${escHtml(email.account || '')}</span></div>
    </div>
    <div class="detail-divider"></div>
    ${email.summary ? `
      <div>
        <div class="detail-section-title">AI Summary</div>
        <div class="detail-summary-box">${escHtml(email.summary)}</div>
      </div>` : ''}
    ${keyPointsHTML}
    ${actionItemsHTML}
    <div class="detail-divider"></div>
    <div>
      <div class="detail-section-title">Full Message</div>
      <div class="detail-body">${escHtml(body)}</div>
    </div>
    <div class="detail-divider"></div>
    <div>
      <div class="detail-section-title">Quick Reply</div>
      <div class="detail-reply-box">
        <textarea id="quick-reply-body" rows="4" placeholder="Type your reply..."></textarea>
        <div style="display:flex;gap:8px;flex-wrap:wrap;">
          <button class="btn btn-secondary btn-sm" onclick="generateDraftReply(${email.id})">✨ AI Draft</button>
          <button class="btn btn-primary btn-sm" onclick="sendQuickReply(${email.id}, '${escAttr(email.sender_email || email.sender || '')}', '${escAttr(email.subject || '')}', '${escAttr(email.account || '')}')">Send Reply</button>
          <button class="btn btn-ghost btn-sm" onclick="toggleEmailImportant(${email.id}, ${!email.is_important})">${email.is_important ? '★ Unmark Important' : '☆ Mark Important'}</button>
        </div>
      </div>
    </div>
  `;
}

/**
 * Render a category card.
 */
function renderCategoryCard(category, count) {
  return `
    <div class="category-card" onclick="filterByCategory('${category}')">
      <div class="category-card-icon">${CATEGORY_ICONS[category] || '📧'}</div>
      <div class="category-card-name">${capitalize(category)}</div>
      <div class="category-card-count">${count} email${count !== 1 ? 's' : ''}</div>
    </div>
  `;
}

/**
 * Render a rule item.
 */
function renderRuleItem(rule) {
  const keywords = Array.isArray(rule.trigger_keywords) ? rule.trigger_keywords.join(', ') : rule.trigger_keywords;
  return `
    <div class="rule-item" id="rule-item-${rule.id}">
      <div style="font-size:20px;flex-shrink:0;">📋</div>
      <div class="rule-info">
        <div class="rule-name">${escHtml(rule.name || 'Unnamed Rule')}</div>
        <div class="rule-keywords">Keywords: ${escHtml(keywords || '')}</div>
        ${rule.time_condition ? `<div class="rule-keywords">Time: ${escHtml(rule.time_condition)}</div>` : ''}
        <div class="rule-template">"${escHtml((rule.reply_template || '').substring(0, 80))}${rule.reply_template && rule.reply_template.length > 80 ? '...' : ''}"</div>
        <div class="rule-keywords" style="margin-top:4px;">Triggered ${rule.trigger_count || 0} time(s)${rule.last_triggered ? ' · Last: ' + formatDate(rule.last_triggered) : ''}</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:4px;flex-shrink:0;">
        <button class="btn btn-xs btn-secondary" onclick="editRule(${rule.id})">Edit</button>
        <button class="btn btn-xs btn-danger" onclick="deleteRuleById(${rule.id})">Delete</button>
        <button class="btn btn-xs ${rule.is_active ? 'btn-ghost' : 'btn-primary'}" onclick="toggleRule(${rule.id}, ${rule.is_active ? 0 : 1})">${rule.is_active ? 'Disable' : 'Enable'}</button>
      </div>
    </div>
  `;
}

/**
 * Render a log entry.
 */
function renderLogEntry(log) {
  const info = LOG_ICONS[log.event_type] || { icon: '📌', cls: 'log-icon-default' };
  return `
    <div class="log-entry">
      <div class="log-icon ${info.cls}">${info.icon}</div>
      <div class="log-info">
        <div class="log-desc">${escHtml(log.description || '')}</div>
        <div class="log-time">${formatDateTime(log.created_at)}</div>
      </div>
    </div>
  `;
}

/**
 * Render a scheduled email item.
 */
function renderScheduledItem(s) {
  return `
    <div class="scheduled-item" id="scheduled-${s.id}">
      <div style="font-size:20px;">🕒</div>
      <div class="scheduled-info">
        <div class="scheduled-subject">${escHtml(s.subject || '(No Subject)')}</div>
        <div class="scheduled-meta">To: ${escHtml(s.to_email)} · From: ${escHtml(s.from_email)}</div>
        <div class="scheduled-meta" style="margin-top:2px;">Status: <strong style="color:${s.status === 'sent' ? 'var(--success)' : s.status === 'failed' ? 'var(--danger)' : 'var(--accent-primary)'}">${s.status}</strong></div>
      </div>
      <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px;">
        <span class="scheduled-time">${formatDateTime(s.send_at)}</span>
        ${s.status === 'pending' ? `<button class="btn btn-xs btn-danger" onclick="cancelScheduled(${s.id})">Cancel</button>` : ''}
      </div>
    </div>
  `;
}

/**
 * Render an account item in sidebar.
 */
function renderAccountItem(acc, isActive) {
  const initials = getInitials(acc.display_name || acc.email);
  const bg = getAvatarColor(acc.email);
  return `
    <div class="account-item${isActive ? ' active' : ''}" data-email="${escAttr(acc.email)}" onclick="selectAccount('${escAttr(acc.email)}')">
      <div class="account-avatar" style="background:${bg};">${initials}</div>
      <div class="account-info">
        <span class="account-name">${escHtml(acc.display_name || acc.email)}</span>
        <div class="account-status">
          <div class="status-dot" style="background:${acc.is_valid ? 'var(--success)' : 'var(--danger)'};"></div>
          <span>${acc.is_valid ? 'Connected' : 'Invalid'}</span>
        </div>
      </div>
      <button class="btn-icon" style="opacity:0.4;" onclick="event.stopPropagation();removeAccount('${escAttr(acc.email)}')" title="Remove account">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
        </svg>
      </button>
    </div>
  `;
}

// ─── Utilities ────────────────────────────────────────────────

function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function escAttr(s) {
  if (!s) return '';
  return String(s).replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function capitalize(s) {
  if (!s) return '';
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function extractSenderName(sender) {
  if (!sender) return 'Unknown';
  const match = sender.match(/^([^<]+)</);
  if (match) return match[1].trim();
  return sender;
}

function showToast(message, type = 'info', duration = 3500) {
  const container = document.getElementById('toast-container');
  if (!container) return;
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  const icons = { success: '✓', error: '✕', info: 'ℹ', warning: '⚠' };
  toast.innerHTML = `<span>${icons[type] || 'ℹ'}</span> ${escHtml(message)}`;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transition = 'opacity 0.3s';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}

function openModal(overlayId, modalId) {
  const overlay = document.getElementById(overlayId);
  const modal = document.getElementById(modalId);
  if (overlay) { overlay.style.display = 'flex'; requestAnimationFrame(() => overlay.classList.add('visible')); }
  if (modal) { requestAnimationFrame(() => modal.classList.add('open')); }
}

function closeModal(overlayId, modalId) {
  const overlay = document.getElementById(overlayId);
  const modal = document.getElementById(modalId);
  if (overlay) { overlay.classList.remove('visible'); setTimeout(() => { overlay.style.display = 'none'; }, 250); }
  if (modal) { modal.classList.remove('open'); }
}
