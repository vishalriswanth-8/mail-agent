/* ============================================================
   Mail Agent Pro - Frontend Application Logic
   Handles UI interactions, API calls, and state management
   ============================================================ */

class MailAgentDashboard {
    constructor() {
        this.currentScope = localStorage.getItem('scope') || 'Professional';
        this.currentAccount = localStorage.getItem('account') || '';
        this.selectedEmail = null;
        this.chatSessionId = this.generateSessionId();
        this.emailCache = {};
        window.proDashboardInstance = this;
        this.init();
    }

    init() {
        this.cacheElements();
        this.attachEventListeners();
        this.loadDashboard();
    }

    cacheElements() {
        // Navigation
        this.scopeToggle = document.getElementById('scope-toggle');
        this.accountSelector = document.getElementById('account-selector');

        // Sidebar views
        this.navDashboard = document.getElementById('nav-dashboard');
        this.navAgent = document.getElementById('nav-agent');
        this.navChat = document.getElementById('nav-chat');
        this.btnSync = document.getElementById('btn-sync');
        this.btnAddAccount = document.getElementById('btn-add-account');

        // Stats
        this.statCritical = document.getElementById('stat-critical');
        this.statImportant = document.getElementById('stat-important');

        // Views
        this.viewDashboard = document.getElementById('view-dashboard');
        this.viewAgent = document.getElementById('view-agent');
        this.viewChat = document.getElementById('view-chat');

        // Dashboard priority sections
        this.listCritical = document.getElementById('list-critical');
        this.listImportant = document.getElementById('list-important');
        this.listNormal = document.getElementById('list-normal');
        this.listLow = document.getElementById('list-low');

        // Agent panel
        this.taskList = document.getElementById('task-list');
        this.suggestionList = document.getElementById('suggestion-list');
        this.emailDetailPane = document.getElementById('agent-email-detail');

        // Chat
        this.chatMessages = document.getElementById('chat-messages');
        this.chatInput = document.getElementById('chat-input');
        this.btnSendMessage = document.getElementById('btn-send-message');

        // Modals
        this.emailDetailModal = document.getElementById('email-modal');
        this.draftReplyModal = document.getElementById('draft-modal');
        this.draftTo = document.getElementById('draft-to');
        this.draftSubject = document.getElementById('draft-subject');
        this.draftBody = document.getElementById('draft-body');
        this.btnSendDraft = document.getElementById('btn-send-draft');

        // Quick search
        this.quickSearchInput = document.getElementById('quick-search');
        this.btnQuickSearch = document.getElementById('btn-quick-search');
        this.searchModal = document.getElementById('search-modal');
    }

    attachEventListeners() {
        // Navigation
        this.scopeToggle?.addEventListener('change', (e) => this.handleScopeChange(e));
        this.accountSelector?.addEventListener('change', (e) => this.handleAccountChange(e));

        // View navigation
        this.navDashboard?.addEventListener('click', () => this.switchView('dashboard'));
        this.navAgent?.addEventListener('click', () => this.switchView('agent'));
        this.navChat?.addEventListener('click', () => this.switchView('chat'));

        // Actions
        this.btnSync?.addEventListener('click', () => this.syncEmails());
        this.btnAddAccount?.addEventListener('click', () => this.addAccount());

        // Chat
        this.btnSendMessage?.addEventListener('click', () => this.sendChatMessage());
        this.chatInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendChatMessage();
            }
        });

        // Draft send
        this.btnSendDraft?.addEventListener('click', () => this.sendDraft());

        // Quick search handlers
        this.btnQuickSearch?.addEventListener('click', () => this.handleQuickSearch());
        this.quickSearchInput?.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this.handleQuickSearch();
            }
        });

        // Modal buttons - use event delegation for dynamic content
        document.addEventListener('click', (e) => {
            if (e.target.id === 'btn-close-modal') {
                this.closeModal(this.emailDetailModal);
            }
            if (e.target.id === 'btn-close-draft') {
                this.closeModal(this.draftReplyModal);
            }
            if (e.target.id === 'btn-cancel-draft') {
                this.closeModal(this.draftReplyModal);
            }
            if (e.target.id === 'btn-analyze-modal') {
                if (this.selectedEmail) {
                    this.analyzeEmail(this.selectedEmail.id);
                    this.switchView('agent');
                    this.closeModal(this.emailDetailModal);
                }
            }
            if (e.target.id === 'btn-draft-reply-modal') {
                if (this.selectedEmail) {
                    this.openDraftModal(this.selectedEmail);
                }
            }
        });

        // Click outside modal
        window.addEventListener('click', (e) => {
            if (e.target === this.emailDetailModal) {
                this.closeModal(this.emailDetailModal);
            }
            if (e.target === this.draftReplyModal) {
                this.closeModal(this.draftReplyModal);
            }
        });
    }

    // ========== Quick Search & Interactive Summary ==========

    async handleQuickSearch() {
        const query = (this.quickSearchInput?.value || '').trim();
        if (!query) return this.showNotification('Please enter a search term');

        // If user asked generic chat, fall back to chat assistant
        const lower = query.toLowerCase();
        if (!/email|mail|@|\w+/.test(lower)) {
            // fallback to chat
            this.chatInput.value = query;
            this.switchView('chat');
            return;
        }

        const results = this.searchEmailsByKeyword(query);
        this.renderSearchResultsModal(results, query);
    }

    searchEmailsByKeyword(query) {
        const q = query.toLowerCase();
        const results = [];
        const emails = Object.values(this.emailCache || {});
        for (const e of emails) {
            const subject = (e.subject || '').toLowerCase();
            const from = (e.from || '').toLowerCase();
            const body = (e.body || '').toLowerCase();
            const summary = (e.summary || '').toLowerCase();
            if (subject.includes(q) || from.includes(q) || body.includes(q) || summary.includes(q)) {
                results.push(e);
            }
        }
        // Sort by date desc if present
        results.sort((a, b) => (new Date(b.date || 0)) - (new Date(a.date || 0)));
        return results;
    }

    renderSearchResultsModal(results, query) {
        // Ensure modal exists; create if missing
        let modal = document.getElementById('search-modal');
        if (!modal) {
            modal = document.createElement('div');
            modal.id = 'search-modal';
            modal.className = 'modal';
            modal.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Search results for "${this.escapeHtml(query)}"</h2>
                        <button class="btn-close-modal" id="btn-close-search">✕</button>
                    </div>
                    <div class="modal-body" id="search-modal-body"></div>
                </div>`;
            document.body.appendChild(modal);
            // close handler
            document.getElementById('btn-close-search')?.addEventListener('click', () => { modal.style.display = 'none'; });
            modal.addEventListener('click', (e) => { if (e.target === modal) modal.style.display = 'none'; });
        }

        const body = modal.querySelector('#search-modal-body');
        if (!body) return;
        body.innerHTML = '';

        const count = results.length;
        const uniqueSenders = [...new Set(results.map(r => r.from || r.to || 'unknown'))];

        const summaryText = `Found ${count} matching email${count !== 1 ? 's' : ''} from ${uniqueSenders.length} sender${uniqueSenders.length !== 1 ? 's' : ''}.`;
        const p = document.createElement('p');
        p.style.marginBottom = '12px';
        p.textContent = summaryText;
        body.appendChild(p);

        if (count === 0) {
            const empty = document.createElement('div');
            empty.className = 'empty-state';
            empty.innerHTML = `<p>No emails matched "${this.escapeHtml(query)}"</p>`;
            body.appendChild(empty);
        } else {
            // If multiple messages share same sender, show clarification note
            const senderCounts = {};
            results.forEach(r => { const s = r.from || 'unknown'; senderCounts[s] = (senderCounts[s] || 0) + 1; });
            const clarif = document.createElement('div');
            clarif.style.marginBottom = '8px';
            clarif.style.color = 'var(--text-light)';
            clarif.textContent = 'Click any message to view details. Use the quick actions for a short summary, draft reply, or agent analysis.';
            body.appendChild(clarif);

            // List results as buttons
            const list = document.createElement('div');
            list.style.display = 'flex';
            list.style.flexDirection = 'column';
            list.style.gap = '8px';

            results.forEach(email => {
                const item = document.createElement('div');
                item.style.display = 'flex';
                item.style.justifyContent = 'space-between';
                item.style.alignItems = 'center';
                item.style.padding = '8px';
                item.style.borderRadius = '6px';
                item.style.background = 'var(--bg-tertiary)';

                const left = document.createElement('div');
                left.style.flex = '1';
                const when = email.date ? new Date(email.date).toLocaleString() : '';
                const subj = email.subject ? email.subject : '(No subject)';
                const sender = email.from || 'Unknown';
                left.innerHTML = `<div style="font-weight:600">${this.escapeHtml(subj)}</div><div style="font-size:12px;color:var(--text-light);">${this.escapeHtml(sender)} · ${this.escapeHtml(when)}</div>`;

                const actions = document.createElement('div');
                actions.style.display = 'flex';
                actions.style.gap = '6px';

                const btnSummary = document.createElement('button');
                btnSummary.className = 'btn-small secondary';
                btnSummary.textContent = 'Summary';
                btnSummary.addEventListener('click', () => this.showInlineSummary(email));

                const btnOpen = document.createElement('button');
                btnOpen.className = 'btn-small primary';
                btnOpen.textContent = 'Open';
                btnOpen.addEventListener('click', () => { this.showEmailDetail(email); modal.style.display = 'none'; this.switchView('dashboard'); });

                const btnDraft = document.createElement('button');
                btnDraft.className = 'btn-small secondary';
                btnDraft.textContent = 'Draft';
                btnDraft.addEventListener('click', async () => {
                    await this.previewDraftForEmail(email);
                });

                const btnAgent = document.createElement('button');
                btnAgent.className = 'btn-small secondary';
                btnAgent.textContent = 'Agent';
                btnAgent.addEventListener('click', async () => {
                    modal.style.display = 'none';
                    this.selectedEmail = email;
                    await this.analyzeEmail(email.id);
                    this.switchView('agent');
                });

                actions.appendChild(btnSummary);
                actions.appendChild(btnDraft);
                actions.appendChild(btnAgent);
                actions.appendChild(btnOpen);

                item.appendChild(left);
                item.appendChild(actions);
                list.appendChild(item);
            });

            body.appendChild(list);
        }

        modal.style.display = 'flex';
    }

    showInlineSummary(email) {
        const subj = email.subject || '(No subject)';
        const from = email.from || 'Unknown';
        const date = email.date ? new Date(email.date).toLocaleString() : '';
        const snippet = (email.summary || email.body || '').substring(0, 200);

        // quick small modal for inline summary
        let sm = document.getElementById('summary-modal');
        if (!sm) {
            sm = document.createElement('div');
            sm.id = 'summary-modal';
            sm.className = 'modal';
            sm.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Quick summary</h2>
                        <button class="btn-close-modal" id="btn-close-summary">✕</button>
                    </div>
                    <div class="modal-body" id="summary-modal-body"></div>
                </div>`;
            document.body.appendChild(sm);
            document.getElementById('btn-close-summary')?.addEventListener('click', () => { sm.style.display = 'none'; });
            sm.addEventListener('click', (e) => { if (e.target === sm) sm.style.display = 'none'; });
        }

        const body = sm.querySelector('#summary-modal-body');
        body.innerHTML = `<div style="font-weight:600">${this.escapeHtml(subj)}</div>
                          <div style="font-size:13px;color:var(--text-light);">${this.escapeHtml(from)} · ${this.escapeHtml(date)}</div>
                          <div style="margin-top:10px;">${this.escapeHtml(snippet)}${snippet.length >= 200 ? '...' : ''}</div>
                          <div style="margin-top:12px; display:flex; gap:8px; justify-content:flex-end;">
                              <button class="btn-small primary" id="btn-summary-open">Open</button>
                              <button class="btn-small secondary" id="btn-summary-draft">Draft</button>
                          </div>`;

        document.getElementById('btn-summary-open')?.addEventListener('click', () => { this.showEmailDetail(email); sm.style.display = 'none'; });
        document.getElementById('btn-summary-draft')?.addEventListener('click', async () => { await this.previewDraftForEmail(email); sm.style.display = 'none'; });
        sm.style.display = 'flex';
    }

    async previewDraftForEmail(email) {
        try {
            this.showLoading();
            const scope = this.currentScope;
            const resp = await API.generateDraftReply(email.id, scope);
            if (resp && resp.success && resp.data) {
                this.showDraftPreview(resp.data);
            } else {
                this.showError('Could not generate draft');
            }
        } catch (err) {
            console.error('Draft preview error', err);
            this.showError('Draft generation failed');
        } finally {
            this.hideLoading();
        }
    }

    showDraftPreview(draft) {
        let dm = document.getElementById('draft-preview-modal');
        if (!dm) {
            dm = document.createElement('div');
            dm.id = 'draft-preview-modal';
            dm.className = 'modal';
            dm.innerHTML = `
                <div class="modal-content">
                    <div class="modal-header">
                        <h2>Draft Preview</h2>
                        <button class="btn-close-modal" id="btn-close-draft-preview">✕</button>
                    </div>
                    <div class="modal-body" id="draft-preview-body"></div>
                </div>`;
            document.body.appendChild(dm);
            document.getElementById('btn-close-draft-preview')?.addEventListener('click', () => { dm.style.display = 'none'; });
            dm.addEventListener('click', (e) => { if (e.target === dm) dm.style.display = 'none'; });
        }

        const body = dm.querySelector('#draft-preview-body');
        body.innerHTML = `<div><strong>To:</strong> ${this.escapeHtml(draft.to || '')}</div>
                          <div><strong>Subject:</strong> ${this.escapeHtml(draft.subject || '')}</div>
                          <div style="margin-top:12px; white-space:pre-wrap;">${this.escapeHtml(draft.body || '')}</div>
                          <div style="margin-top:12px; display:flex; gap:8px; justify-content:flex-end;">
                              <button class="btn-small primary" id="btn-load-draft">Use Draft</button>
                              <button class="btn-small secondary" id="btn-close-draft-preview-2">Close</button>
                          </div>`;

        document.getElementById('btn-load-draft')?.addEventListener('click', () => {
            // load into draft modal for editing
            if (this.draftTo) this.draftTo.value = draft.to || '';
            if (this.draftSubject) this.draftSubject.value = draft.subject || '';
            if (this.draftBody) this.draftBody.value = draft.body || '';
            dm.style.display = 'none';
            this.openModal(this.draftReplyModal);
        });
        document.getElementById('btn-close-draft-preview-2')?.addEventListener('click', () => { dm.style.display = 'none'; });
        dm.style.display = 'flex';
    }

    // ========== Navigation & View Management ==========

    switchView(view) {
        // Hide all views
        this.viewDashboard?.classList.remove('active');
        this.viewAgent?.classList.remove('active');
        this.viewChat?.classList.remove('active');

        // Deactivate all nav buttons
        this.navDashboard?.classList.remove('active');
        this.navAgent?.classList.remove('active');
        this.navChat?.classList.remove('active');

        // Show selected view
        switch (view) {
            case 'dashboard':
                this.viewDashboard?.classList.add('active');
                this.navDashboard?.classList.add('active');
                break;
            case 'agent':
                this.viewAgent?.classList.add('active');
                this.navAgent?.classList.add('active');
                this.loadAgentPanel();
                break;
            case 'chat':
                this.viewChat?.classList.add('active');
                this.navChat?.classList.add('active');
                this.scrollChatToBottom();
                break;
        }
    }

    handleScopeChange(e) {
        this.currentScope = e.target.value;
        localStorage.setItem('scope', this.currentScope);
        this.showNotification(`Scope changed to: ${this.currentScope}`);
    }

    handleAccountChange(e) {
        this.currentAccount = e.target.value;
        localStorage.setItem('account', this.currentAccount);
        this.loadDashboard();
    }

    // ========== Dashboard Loading ==========

    async loadDashboard() {
        try {
            this.showLoading();
            const limit = 50;
            const response = await API.getDashboard(this.currentAccount, limit);

            if (response.success) {
                this.renderDashboard(response.data);
                this.updateStats(response.data);

                const accountsData = await API.getAccounts();
                const accounts = accountsData.accounts || [];
                if (accounts.length === 0) {
                    this.openModal(document.getElementById('dev-access-modal'));
                } else {
                    this.closeModal(document.getElementById('dev-access-modal'));
                }
            } else {
                this.showError(response.message || 'Failed to load dashboard');
            }
        } catch (error) {
            console.error('Dashboard load error:', error);
            this.showError('Error loading dashboard');
        } finally {
            this.hideLoading();
        }
    }

    renderDashboard(data) {
        const { critical = [], important = [], normal = [], low = [] } = data;

        // Clear all lists
        [this.listCritical, this.listImportant, this.listNormal, this.listLow].forEach(list => {
            if (list) list.innerHTML = '';
        });

        // Render emails by priority
        this.renderPriorityList(critical, this.listCritical, 'critical');
        this.renderPriorityList(important, this.listImportant, 'important');
        this.renderPriorityList(normal, this.listNormal, 'normal');
        this.renderPriorityList(low, this.listLow, 'low');
    }

    renderPriorityList(emails, container, priority) {
        if (!container) return;

        if (emails.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>No emails</p></div>';
            return;
        }

        emails.forEach(email => {
            const card = this.createEmailCard(email);
            card.addEventListener('click', () => this.showEmailDetail(email));
            container.appendChild(card);

            // Cache email for later access
            this.emailCache[email.id] = email;
        });
    }

    createEmailCard(email) {
        const div = document.createElement('div');
        div.className = 'email-card';
        div.dataset.emailId = email.id;

        const subject = email.subject || '(No subject)';
        const summary = email.summary || email.body || '';
        const from = email.from || 'Unknown';
        const date = new Date(email.date).toLocaleDateString();

        div.innerHTML = `
            <div class="email-subject">${this.escapeHtml(subject)}</div>
            <div class="email-sender">${this.escapeHtml(from)}</div>
            <div class="email-summary">${this.escapeHtml(summary.substring(0, 100))}</div>
            <div class="email-footer">
                <span>${date}</span>
                <span>${email.category || 'Uncategorized'}</span>
            </div>
        `;

        return div;
    }

    updateStats(data) {
        const critical = data.critical?.length || 0;
        const important = data.important?.length || 0;

        if (this.statCritical) this.statCritical.textContent = critical;
        if (this.statImportant) this.statImportant.textContent = important;
    }

    // ========== Email Detail Modal ==========

    async showEmailDetail(email) {
        this.selectedEmail = email;

        // Populate modal
        const from = email.from || 'Unknown';
        const to = email.to || '';
        const date = new Date(email.date).toLocaleDateString();
        const category = email.category || 'Uncategorized';
        const priority = email.priority || 'Normal';
        const summary = email.summary || email.body || '';
        const body = email.body || '';

        // Fill in modal fields
        document.getElementById('modal-subject').textContent = this.escapeHtml(email.subject || '(No subject)');
        document.getElementById('modal-from').textContent = this.escapeHtml(from);
        document.getElementById('modal-to').textContent = this.escapeHtml(to);
        document.getElementById('modal-date').textContent = date;
        document.getElementById('modal-category').textContent = category;
        document.getElementById('modal-priority').textContent = priority;
        document.getElementById('modal-summary').textContent = this.escapeHtml(summary);
        document.getElementById('modal-body').textContent = this.escapeHtml(body);

        // Show modal
        this.openModal(this.emailDetailModal);
    }

    // ========== Agent Panel ==========

    async loadAgentPanel() {
        if (!this.selectedEmail) {
            this.emailDetailPane.innerHTML = '<div class="empty-state"><p>Select an email to analyze</p></div>';
            return;
        }

        await this.analyzeEmail(this.selectedEmail.id);
    }

    async analyzeEmail(emailId) {
        try {
            this.showLoading();
            const response = await API.analyzeEmail(emailId);

            if (response.success) {
                this.renderAgentAnalysis(response.data);
            } else {
                this.showError('Failed to analyze email');
            }
        } catch (error) {
            console.error('Analysis error:', error);
            this.showError('Error analyzing email');
        } finally {
            this.hideLoading();
        }
    }

    renderAgentAnalysis(data) {
        const { tasks = [], suggestions = [], email = {} } = data;

        // Render tasks
        if (this.taskList) {
            this.taskList.innerHTML = '';
            if (tasks.length === 0) {
                this.taskList.innerHTML = '<div class="empty-state"><p>No tasks suggested</p></div>';
            } else {
                tasks.forEach(task => {
                    const item = this.createTaskItem(task);
                    this.taskList.appendChild(item);
                });
            }
        }

        // Render suggestions
        if (this.suggestionList) {
            this.suggestionList.innerHTML = '';
            if (suggestions.length === 0) {
                this.suggestionList.innerHTML = '<div class="empty-state"><p>No suggestions</p></div>';
            } else {
                suggestions.forEach(suggestion => {
                    const item = this.createSuggestionItem(suggestion);
                    this.suggestionList.appendChild(item);
                });
            }
        }

        // Render email detail
        this.renderEmailDetailPane(email);
    }

    createTaskItem(task) {
        const div = document.createElement('div');
        div.className = 'task-item';

        const priorityClass = task.priority ? ` priority-${task.priority}` : '';

        div.innerHTML = `
            <div class="task-title">${this.escapeHtml(task.task_title || task.title || 'Task')}</div>
            <div class="task-description">${this.escapeHtml(task.description || '')}</div>
            <div class="task-actions">
                <span class="badge">${task.status || 'pending'}</span>
                ${task.status !== 'completed' ? `<button class="btn-small primary" data-task-id="${task.id}">✓ Done</button>` : ''}
            </div>
        `;

        const completeBtn = div.querySelector('[data-task-id]');
        if (completeBtn) {
            completeBtn.addEventListener('click', () => this.completeTask(task.id));
        }

        return div;
    }

    createSuggestionItem(suggestion) {
        const div = document.createElement('div');
        div.className = 'suggestion-item';

        div.innerHTML = `
            <div class="task-title">${this.escapeHtml(suggestion.suggestion_type || 'Suggestion')}</div>
            <div class="task-description">${this.escapeHtml(suggestion.text || '')}</div>
            ${suggestion.draft_response ? `<div class="task-actions"><small>${this.escapeHtml(suggestion.draft_response.substring(0, 50))}...</small></div>` : ''}
            <div class="task-actions">
                <button class="btn-small secondary" data-suggestion-id="${suggestion.id}">💾 Save Draft</button>
            </div>
        `;

        const saveBtn = div.querySelector('[data-suggestion-id]');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.acceptSuggestion(suggestion.id));
        }

        return div;
    }

    renderEmailDetailPane(email) {
        if (!this.emailDetailPane) return;

        const subject = email.subject || '(No subject)';
        const from = email.from || 'Unknown';
        const date = new Date(email.date || Date.now()).toLocaleDateString();

        this.emailDetailPane.innerHTML = `
            <div style="background-color: var(--bg-tertiary); padding: var(--spacing-md); border-radius: var(--radius-md);">
                <h3 style="margin: 0 0 var(--spacing-md) 0;">${this.escapeHtml(subject)}</h3>
                <div style="font-size: 13px; color: var(--text-secondary);">
                    <div><strong>From:</strong> ${this.escapeHtml(from)}</div>
                    <div><strong>Date:</strong> ${date}</div>
                    <div><strong>Category:</strong> ${email.category || 'Uncategorized'}</div>
                </div>
                <div style="margin-top: var(--spacing-md); font-size: 13px; line-height: 1.6;">
                    ${this.escapeHtml(email.body || '').substring(0, 200)}...
                </div>
            </div>
        `;
    }

    async completeTask(taskId) {
        try {
            const response = await API.completeTask(taskId);
            if (response.success) {
                this.showNotification('Task marked as complete');
                if (this.selectedEmail) {
                    this.analyzeEmail(this.selectedEmail.id);
                }
            }
        } catch (error) {
            console.error('Complete task error:', error);
            this.showError('Error completing task');
        }
    }

    async acceptSuggestion(suggestionId) {
        try {
            const response = await API.acceptSuggestion(suggestionId);
            if (response.success) {
                this.showNotification('Suggestion saved');
                if (this.selectedEmail) {
                    this.analyzeEmail(this.selectedEmail.id);
                }
            }
        } catch (error) {
            console.error('Accept suggestion error:', error);
            this.showError('Error accepting suggestion');
        }
    }

    // ========== Draft Reply Modal ==========

    openDraftModal(email) {
        this.selectedEmail = email;

        // Populate fields
        if (this.draftTo) this.draftTo.value = email.from || '';
        if (this.draftSubject) {
            const subject = email.subject || '';
            this.draftSubject.value = subject.startsWith('Re:') ? subject : `Re: ${subject}`;
        }
        if (this.draftBody) this.draftBody.value = '';

        this.openModal(this.draftReplyModal);

        // Auto-generate draft for better UX
        this.generateDraft();
    }

    async generateDraft() {
        if (!this.selectedEmail) {
            this.showError('No email selected');
            return;
        }

        try {
            this.showLoading();
            const scope = this.currentScope;
            const response = await API.generateDraftReply(this.selectedEmail.id, scope);

            if (response.success && response.data) {
                const { body, subject, to } = response.data;
                if (this.draftBody) this.draftBody.value = body || '';
                if (this.draftSubject) this.draftSubject.value = subject || this.draftSubject.value;
                if (this.draftTo) this.draftTo.value = to || this.draftTo.value;
                this.showNotification('Draft generated');
            }
        } catch (error) {
            console.error('Generate draft error:', error);
            this.showError('Error generating draft');
        } finally {
            this.hideLoading();
        }
    }

    async sendDraft() {
        const to = this.draftTo?.value;
        const subject = this.draftSubject?.value;
        const body = this.draftBody?.value;

        if (!to || !subject || !body) {
            this.showError('Please fill all fields');
            return;
        }

        // TODO: Implement send draft functionality via API
        this.showNotification('Draft prepared (ready to send)');
        this.closeModal(this.draftReplyModal);
    }

    // ========== Chat Interface ==========

    handleChatOptionClick(action) {
        document.querySelectorAll('.chat-options-container').forEach(el => el.remove());
        this.sendChatMessage(action);
    }

    async sendChatMessage(action = null) {
        const message = action || this.chatInput?.value?.trim();
        if (!message) return;

        // Clear input
        if (!action && this.chatInput) this.chatInput.value = '';

        // Add user message to chat
        if (!message.startsWith('/')) {
            this.appendChatMessage(message, 'user');
        } else if (message.startsWith('/summarize_contact ')) {
            this.appendChatMessage(`Summarize emails from ${message.replace('/summarize_contact ', '')}`, 'user');
        } else if (message.startsWith('/info_email ')) {
            const parts = message.replace('/info_email ', '').split('|');
            const emailTitle = parts[1] || `Email #${parts[0]}`;
            this.appendChatMessage(`Get details about: "${emailTitle}"`, 'user');
        }

        try {
            const scope = this.currentScope;
            const emailId = this.selectedEmail?.id || null;

            const response = await API.sendChatMessage(message, emailId, scope, this.chatSessionId);

            const resData = response.success ? (response.data || response) : null;
            if (response.success && resData) {
                const agentResponse = resData.agent_response || resData.response || '';
                const options = resData.options || [];
                this.appendChatMessage(agentResponse, 'agent', options);
            } else {
                this.appendChatMessage('Sorry, I could not process that request.', 'agent');
            }
        } catch (error) {
            console.error('Chat error:', error);
            this.appendChatMessage('Error processing message.', 'agent');
        }
    }

    appendChatMessage(text, sender = 'agent', options = null) {
        if (!this.chatMessages) return;

        const messageDiv = document.createElement('div');
        messageDiv.className = `chat-message ${sender}`;

        let html = `<div class="message-content">${this.escapeHtml(text)}</div>`;
        if (options && options.length > 0) {
            const optionsHtml = options.map(opt => {
                const actionEscaped = this.escapeHtml(opt.action);
                const labelEscaped = this.escapeHtml(opt.label);
                return `<button class="btn btn-secondary btn-sm" style="margin-top: 4px; margin-right: 4px; font-size: 11px; padding: 4px 8px; border-radius: 4px; border: 1px solid var(--border-color); background: var(--bg-hover); cursor: pointer;" onclick="window.proDashboardInstance.handleChatOptionClick('${actionEscaped}')">${labelEscaped}</button>`;
            }).join('');
            html += `<div class="chat-options-container" style="display:flex; flex-wrap:wrap; gap:4px; margin-top:8px;">${optionsHtml}</div>`;
        }

        messageDiv.innerHTML = html;
        this.chatMessages.appendChild(messageDiv);
        this.scrollChatToBottom();
    }

    scrollChatToBottom() {
        if (this.chatMessages) {
            setTimeout(() => {
                this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
            }, 100);
        }
    }

    // ========== Action Handlers ==========

    async syncEmails() {
        try {
            this.showNotification('Syncing emails...');
            // TODO: Implement sync via existing API
            setTimeout(() => {
                this.loadDashboard();
                this.showNotification('Sync complete');
            }, 1000);
        } catch (error) {
            console.error('Sync error:', error);
            this.showError('Error syncing emails');
        }
    }

    addAccount() {
        // TODO: Implement add account dialog
        this.showNotification('Add account feature coming soon');
    }

    // ========== Modal Helpers ==========

    openModal(modal) {
        if (modal) {
            modal.style.display = 'flex';
            modal.classList.remove('hidden');
        }
    }

    closeModal(modal) {
        if (modal) {
            modal.style.display = 'none';
            modal.classList.add('hidden');
        }
    }

    // ========== Utility Functions ==========

    escapeHtml(text) {
        if (!text) return '';
        const map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        return text.replace(/[&<>"']/g, m => map[m]);
    }

    generateSessionId() {
        return 'session_' + Math.random().toString(36).substr(2, 9) + '_' + Date.now();
    }

    showNotification(message) {
        console.log('📢', message);
        // TODO: Implement toast notification UI
    }

    showError(message) {
        console.error('❌', message);
        // TODO: Implement error notification UI
    }

    showLoading() {
        // TODO: Implement loading spinner
    }

    hideLoading() {
        // TODO: Hide loading spinner
    }
}

// Initialize dashboard when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new MailAgentDashboard();
});
