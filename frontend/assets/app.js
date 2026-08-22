/* ==========================================================================
   EduMentor — application shell, router, and views
   Vanilla JS, hash-based routing, no build step required.
   ========================================================================== */

const root = document.getElementById('app');

const State = {
  user: Store.getUser(),
  subjects: [],
  subjectsLoaded: false,
};

function esc(str){
  const d = document.createElement('div');
  d.textContent = str ?? '';
  return d.innerHTML;
}

function fmtDate(iso){
  try{
    return new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }catch(e){ return iso; }
}

function fmtBytes(n){
  if (n < 1024) return `${n} B`;
  if (n < 1024*1024) return `${(n/1024).toFixed(1)} KB`;
  return `${(n/1024/1024).toFixed(1)} MB`;
}

function initials(name){
  if (!name) return '?';
  return name.trim().split(/\s+/).slice(0,2).map(w => w[0].toUpperCase()).join('');
}

// ---------------- toasts ----------------
function toast(message, type = ''){
  let stack = document.querySelector('.toast-stack');
  if (!stack){
    stack = document.createElement('div');
    stack.className = 'toast-stack';
    document.body.appendChild(stack);
  }
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = message;
  stack.appendChild(el);
  setTimeout(() => el.remove(), 4200);
}

function apiErrorMessage(err){
  return err instanceof ApiError ? err.message : (err?.message || 'Something went wrong.');
}

// ---------------- simple modal helper ----------------
function openModal(html, onMount){
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `<div class="modal">${html}</div>`;
  overlay.addEventListener('click', (e) => { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
  if (onMount) onMount(overlay);
  return overlay;
}

// ==========================================================================
// Router
// ==========================================================================

function parseHash(){
  const hash = location.hash.replace(/^#\/?/, '');
  const parts = hash.split('/').filter(Boolean);
  return parts;
}

async function router(){
  const parts = parseHash();

  if (!Store.getToken()){
    renderAuth(parts[0] === 'register' ? 'register' : 'login');
    return;
  }

  // ensure we have a user object
  if (!State.user){
    try{ State.user = await Api.me(); Store.setUser(State.user); }
    catch(e){ Store.clearAuth(); renderAuth('login'); return; }
  }

  if (parts.length === 0 || parts[0] === 'dashboard'){
    renderShell('dashboard');
    return;
  }
  if (parts[0] === 'subjects' && parts.length === 1){
    renderShell('subjects');
    return;
  }
  if (parts[0] === 'subjects' && parts[1]){
    const subjectId = parseInt(parts[1], 10);
    const tab = parts[2] || 'documents';
    const sub = parts[3]; // e.g. quiz id under quizzes
    renderShell('workspace', { subjectId, tab, sub });
    return;
  }
  renderShell('dashboard');
}

window.addEventListener('hashchange', router);

// ==========================================================================
// Auth views
// ==========================================================================

function renderAuth(mode){
  document.body.classList.add('auth-mode');
  const isLogin = mode === 'login';

  root.innerHTML = `
    <div class="auth-wrap">
      <div class="auth-visual">
        <div class="mark">EduMentor</div>
        <div>
          <div class="headline">Your notes, <em>answering back.</em></div>
          <p style="margin-top:16px; max-width:32ch; color:rgba(238,233,221,.7); font-size:14.5px; line-height:1.6;">
            Upload your course material and EduMentor grounds every answer, flashcard,
            and quiz question in what you actually studied — with citations back to the source.
          </p>
        </div>
        <div class="foot">RAG-powered study assistant · chat, flashcards, quizzes &amp; progress tracking, all scoped to your subjects.</div>
      </div>
      <div class="auth-card-wrap">
        <div class="auth-card">
          <div class="mark-mobile">EduMentor</div>
          <h1>${isLogin ? 'Welcome back' : 'Create your account'}</h1>
          <div class="sub">${isLogin ? 'Log in to pick up where you left off.' : 'Start turning your course material into study tools.'}</div>
          <div id="auth-error"></div>
          <form id="auth-form">
            ${isLogin ? '' : `
            <div class="field">
              <label>Full name</label>
              <input type="text" name="name" placeholder="Jordan Rivera" required minlength="2" />
            </div>`}
            <div class="field">
              <label>Email</label>
              <input type="email" name="email" placeholder="you@college.edu" required />
            </div>
            <div class="field">
              <label>Password</label>
              <input type="password" name="password" placeholder="${isLogin ? '••••••••' : 'At least 8 characters'}" required minlength="8" />
            </div>
            <button class="btn btn-amber btn-block" type="submit" id="auth-submit">
              ${isLogin ? 'Log in' : 'Create account'}
            </button>
          </form>
          <div class="auth-switch">
            ${isLogin ? "New to EduMentor?" : "Already have an account?"}
            <button type="button" id="auth-switch-btn">${isLogin ? 'Create an account' : 'Log in'}</button>
          </div>
        </div>
      </div>
    </div>
  `;

  document.getElementById('auth-switch-btn').addEventListener('click', () => {
    location.hash = isLogin ? '#/register' : '#/login';
    renderAuth(isLogin ? 'register' : 'login');
  });

  document.getElementById('auth-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const form = e.target;
    const btn = document.getElementById('auth-submit');
    const errorBox = document.getElementById('auth-error');
    errorBox.innerHTML = '';
    const data = Object.fromEntries(new FormData(form).entries());

    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>`;
    try{
      if (isLogin){
        const res = await Api.login({ email: data.email, password: data.password });
        Store.setToken(res.access_token);
        Store.setUser(res.user);
        State.user = res.user;
      } else {
        await Api.register(data);
        const res = await Api.login({ email: data.email, password: data.password });
        Store.setToken(res.access_token);
        Store.setUser(res.user);
        State.user = res.user;
      }
      document.body.classList.remove('auth-mode');
      State.subjectsLoaded = false;
      location.hash = '#/dashboard';
      router();
    }catch(err){
      errorBox.innerHTML = `<div class="auth-error">${esc(apiErrorMessage(err))}</div>`;
      btn.disabled = false;
      btn.textContent = isLogin ? 'Log in' : 'Create account';
    }
  });
}

// ==========================================================================
// Shell (sidebar + main) — used for every authenticated view
// ==========================================================================

async function ensureSubjects(force = false){
  if (State.subjectsLoaded && !force) return State.subjects;
  try{
    State.subjects = await Api.listSubjects();
    State.subjectsLoaded = true;
  }catch(e){
    toast(apiErrorMessage(e), 'error');
  }
  return State.subjects;
}

async function renderShell(view, params = {}){
  document.body.classList.remove('auth-mode');
  await ensureSubjects();

  const activeSubjectId = params.subjectId;

  root.innerHTML = `
    <div class="shell">
      <div class="mobile-topbar">
        <div class="brand" style="border:none;padding:0;margin:0;">
          <span class="mark">Ed</span><span class="word">EduMentor</span>
        </div>
        <button class="icon-btn" id="mobile-menu-btn" style="border-radius:8px;">☰</button>
      </div>
      <aside class="sidebar" id="sidebar">
        <div class="brand">
          <span class="mark">Ed</span><span class="word">EduMentor</span>
        </div>

        <div class="nav-group">
          <div class="tab-item ${view === 'dashboard' ? 'active' : ''}" data-nav="#/dashboard">
            <span class="dot"></span> Dashboard
          </div>
          <div class="tab-item ${view === 'subjects' ? 'active' : ''}" data-nav="#/subjects">
            <span class="dot"></span> All subjects
          </div>
        </div>

        <div class="nav-group" style="flex:1; display:flex; flex-direction:column; min-height:0;">
          <div class="nav-label">Your subjects</div>
          <div class="subject-list" id="sidebar-subject-list"></div>
        </div>

        <div class="sidebar-footer">
          <div class="user-chip">
            <div class="avatar">${esc(initials(State.user?.name))}</div>
            <div class="who">
              <div class="name">${esc(State.user?.name || '')}</div>
              <div class="email">${esc(State.user?.email || '')}</div>
            </div>
          </div>
          <button class="btn btn-ghost btn-sm btn-block" id="logout-btn">Log out</button>
          <div class="settings-bar">
            <span>API</span>
            <input type="text" id="api-base-input" value="${esc(Store.getApiBase())}" spellcheck="false" />
          </div>
        </div>
      </aside>
      <main class="main" id="main-content"></main>
    </div>
  `;

  // sidebar subject list
  const listEl = document.getElementById('sidebar-subject-list');
  if (!State.subjects.length){
    listEl.innerHTML = `<div style="padding:10px 20px; font-size:12.5px; color:rgba(238,233,221,.4);">No subjects yet</div>`;
  } else {
    listEl.innerHTML = State.subjects.map(s => `
      <div class="subject-item ${s.id === activeSubjectId ? 'active' : ''}" data-subject="${s.id}">
        ${esc(s.name)}
      </div>
    `).join('');
  }

  root.querySelectorAll('[data-nav]').forEach(el => {
    el.addEventListener('click', () => { location.hash = el.dataset.nav; });
  });
  root.querySelectorAll('[data-subject]').forEach(el => {
    el.addEventListener('click', () => { location.hash = `#/subjects/${el.dataset.subject}/documents`; });
  });
  document.getElementById('logout-btn').addEventListener('click', () => {
    Store.clearAuth();
    State.user = null;
    State.subjects = [];
    State.subjectsLoaded = false;
    location.hash = '#/login';
    renderAuth('login');
  });
  document.getElementById('api-base-input').addEventListener('change', (e) => {
    Store.setApiBase(e.target.value.trim());
    toast('API base URL updated.', 'success');
  });
  const menuBtn = document.getElementById('mobile-menu-btn');
  if (menuBtn){
    menuBtn.addEventListener('click', () => document.getElementById('sidebar').classList.toggle('open'));
  }

  const mainEl = document.getElementById('main-content');

  if (view === 'dashboard') return renderDashboard(mainEl);
  if (view === 'subjects') return renderSubjectsList(mainEl);
  if (view === 'workspace') return renderWorkspace(mainEl, params);
}

// ==========================================================================
// Dashboard
// ==========================================================================

async function renderDashboard(el){
  el.innerHTML = `<div class="loading-page"><span class="spinner" style="border-top-color:#202c53; border-color:#d9d0b8; border-top-color:#202c53;"></span> Loading dashboard…</div>`;
  let d;
  try{
    d = await Api.getDashboard();
  }catch(e){
    el.innerHTML = `<div class="empty-state"><h3>Couldn't load your dashboard</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }

  const scoreDisplay = d.average_score_pct === null || d.average_score_pct === undefined ? '—' : `${d.average_score_pct}%`;

  el.innerHTML = `
    <div class="topline">
      <div>
        <div class="eyebrow">Overview</div>
        <h1 class="page-title">Welcome back, ${esc((State.user?.name || '').split(' ')[0])}</h1>
        <p class="page-sub">Everything you've studied across every subject, in one place.</p>
      </div>
      <button class="btn btn-amber" id="dash-new-subject">+ New subject</button>
    </div>

    <div class="grid grid-4" style="margin-bottom:26px;">
      <div class="stat-card"><div class="stat-label">Subjects</div><div class="stat-value">${d.total_subjects}</div></div>
      <div class="stat-card"><div class="stat-label">Documents</div><div class="stat-value">${d.total_documents}</div></div>
      <div class="stat-card"><div class="stat-label">Study hours</div><div class="stat-value">${d.total_study_hours}</div></div>
      <div class="stat-card"><div class="stat-label">Avg quiz score</div><div class="stat-value">${scoreDisplay}</div></div>
    </div>

    <div class="grid grid-2" style="align-items:start;">
      <div class="card">
        <div class="section-head"><h2>Subjects</h2></div>
        ${d.subjects.length ? d.subjects.map(s => `
          <div class="bar-row" style="cursor:pointer;" data-goto="${s.subject_id}">
            <div class="bar-label" title="${esc(s.name)}">${esc(s.name)}</div>
            <div class="bar-track"><div class="bar-fill" style="width:${Math.min(100, (s.study_hours || 0) * 10)}%"></div></div>
            <div class="bar-value">${s.study_hours}h</div>
          </div>
        `).join('') : `<div class="empty-state"><h3>No subjects yet</h3><p>Add a subject to start uploading material.</p></div>`}
      </div>

      <div class="card">
        <div class="section-head"><h2>Topics</h2></div>
        <div style="margin-bottom:14px;">
          <div class="eyebrow" style="color:var(--green);">Strong</div>
          <div class="topic-list">
            ${d.strong_topics.length ? d.strong_topics.map(t => `<span class="pill pill-green">${esc(t)}</span>`).join('') : '<span style="font-size:13px;color:var(--ink-faint);">None yet — take a few quizzes.</span>'}
          </div>
        </div>
        <div>
          <div class="eyebrow" style="color:var(--brick);">Needs work</div>
          <div class="topic-list">
            ${d.weak_topics.length ? d.weak_topics.map(t => `<span class="pill pill-brick">${esc(t)}</span>`).join('') : '<span style="font-size:13px;color:var(--ink-faint);">Nothing flagged yet.</span>'}
          </div>
        </div>
        <div style="margin-top:18px; padding-top:16px; border-top:1px solid var(--line); display:flex; gap:18px; font-size:13px; color:var(--ink-soft);">
          <span><strong class="mono" style="color:var(--navy);">${d.total_flashcards}</strong> flashcards</span>
          <span><strong class="mono" style="color:var(--navy);">${d.total_quiz_attempts}</strong> quiz attempts</span>
        </div>
      </div>
    </div>
  `;

  document.getElementById('dash-new-subject').addEventListener('click', () => openCreateSubjectModal());
  el.querySelectorAll('[data-goto]').forEach(row => {
    row.addEventListener('click', () => { location.hash = `#/subjects/${row.dataset.goto}/documents`; });
  });
}

// ==========================================================================
// Subjects list
// ==========================================================================

async function renderSubjectsList(el){
  el.innerHTML = `<div class="loading-page"><span class="spinner"></span> Loading subjects…</div>`;
  await ensureSubjects(true);
  drawSubjectsList(el);
}

function drawSubjectsList(el){
  el.innerHTML = `
    <div class="topline">
      <div>
        <div class="eyebrow">Library</div>
        <h1 class="page-title">Your subjects</h1>
        <p class="page-sub">Group your course material by subject, then chat, generate flashcards, and quiz yourself against it.</p>
      </div>
    </div>
    <div class="grid grid-3" id="subjects-grid"></div>
  `;

  const grid = document.getElementById('subjects-grid');
  const cards = State.subjects.map(s => `
    <div class="subject-card" data-goto="${s.id}">
      <span class="pill pill-navy sem-tag">Sem ${s.semester}</span>
      <h3>${esc(s.name)}</h3>
      <div class="code">${s.code ? esc(s.code) : 'No course code'}</div>
      <div class="meta">
        <span>Added ${fmtDate(s.created_at)}</span>
      </div>
    </div>
  `).join('');

  grid.innerHTML = cards + `<div class="new-subject-card" id="add-subject-card">+ Add subject</div>`;

  grid.querySelectorAll('[data-goto]').forEach(card => {
    card.addEventListener('click', () => { location.hash = `#/subjects/${card.dataset.goto}/documents`; });
  });
  document.getElementById('add-subject-card').addEventListener('click', () => openCreateSubjectModal());

  if (!State.subjects.length){
    grid.insertAdjacentHTML('afterbegin', '');
  }
}

function openCreateSubjectModal(){
  const overlay = openModal(`
    <h2>New subject</h2>
    <div class="sub">Give it a name and the semester you're taking it.</div>
    <form id="subject-form">
      <div class="field">
        <label>Subject name</label>
        <input type="text" name="name" placeholder="Computer Networks" required minlength="2" />
      </div>
      <div class="row">
        <div class="field">
          <label>Course code <span class="hint">optional</span></label>
          <input type="text" name="code" placeholder="CS-601" />
        </div>
        <div class="field">
          <label>Semester</label>
          <input type="number" name="semester" min="1" max="8" value="1" required />
        </div>
      </div>
      <div id="subject-form-error"></div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" id="subject-cancel">Cancel</button>
        <button type="submit" class="btn btn-amber" id="subject-submit">Create subject</button>
      </div>
    </form>
  `);

  overlay.querySelector('#subject-cancel').addEventListener('click', () => overlay.remove());
  overlay.querySelector('#subject-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    data.semester = parseInt(data.semester, 10);
    if (!data.code) delete data.code;
    const btn = overlay.querySelector('#subject-submit');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span>`;
    try{
      const subject = await Api.createSubject(data);
      overlay.remove();
      await ensureSubjects(true);
      toast(`Created "${subject.name}"`, 'success');
      location.hash = `#/subjects/${subject.id}/documents`;
      router();
    }catch(err){
      overlay.querySelector('#subject-form-error').innerHTML = `<div class="auth-error">${esc(apiErrorMessage(err))}</div>`;
      btn.disabled = false;
      btn.textContent = 'Create subject';
    }
  });
}

// ==========================================================================
// Subject workspace (documents / chat / flashcards / quizzes / progress)
// ==========================================================================

async function renderWorkspace(el, { subjectId, tab, sub }){
  el.innerHTML = `<div class="loading-page"><span class="spinner"></span> Loading subject…</div>`;

  let subject = State.subjects.find(s => s.id === subjectId);
  try{
    subject = await Api.getSubject(subjectId);
  }catch(e){
    el.innerHTML = `<div class="empty-state"><h3>Subject not found</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }

  const tabs = [
    ['documents', 'Documents'],
    ['chat', 'Chat'],
    ['flashcards', 'Flashcards'],
    ['quizzes', 'Quizzes'],
    ['progress', 'Progress'],
  ];

  el.innerHTML = `
    <div class="topline">
      <div>
        <div class="eyebrow">Sem ${subject.semester}${subject.code ? ` · ${esc(subject.code)}` : ''}</div>
        <h1 class="page-title">${esc(subject.name)}</h1>
      </div>
    </div>
    <div class="workspace-tabs">
      ${tabs.map(([key, label]) => `<div class="ws-tab ${tab === key ? 'active' : ''}" data-tab="${key}">${label}</div>`).join('')}
    </div>
    <div id="workspace-body"></div>
  `;

  el.querySelectorAll('[data-tab]').forEach(t => {
    t.addEventListener('click', () => { location.hash = `#/subjects/${subjectId}/${t.dataset.tab}`; });
  });

  const body = document.getElementById('workspace-body');
  if (tab === 'documents') return renderDocumentsTab(body, subject);
  if (tab === 'chat') return renderChatTab(body, subject);
  if (tab === 'flashcards') return renderFlashcardsTab(body, subject);
  if (tab === 'quizzes') return renderQuizzesTab(body, subject, sub);
  if (tab === 'progress') return renderProgressTab(body, subject);
  return renderDocumentsTab(body, subject);
}

// ---------------- Documents tab ----------------

const FILE_TYPE_LABEL = { pdf: 'PDF', docx: 'DOCX', pptx: 'PPTX', txt: 'TXT' };
const STATUS_PILL = {
  completed: 'pill-green', processing: 'pill-amber', pending: 'pill-muted', failed: 'pill-brick',
};

async function renderDocumentsTab(el, subject){
  el.innerHTML = `
    <div class="upload-drop" id="upload-drop">
      <input type="file" id="file-input" multiple accept=".pdf,.docx,.pptx,.txt" />
      <div class="u-title">Drop files here or click to upload</div>
      <div class="u-sub">PDF, DOCX, PPTX or TXT · up to 20MB each</div>
    </div>
    <div class="section-head"><h2>Documents</h2></div>
    <div id="doc-list"><div class="loading-page" style="min-height:120px;"><span class="spinner"></span> Loading…</div></div>
  `;

  const dropZone = document.getElementById('upload-drop');
  const fileInput = document.getElementById('file-input');
  dropZone.addEventListener('click', () => fileInput.click());
  dropZone.addEventListener('dragover', (e) => { e.preventDefault(); dropZone.classList.add('dragover'); });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
  dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) handleUpload(subject.id, e.dataTransfer.files, el);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files.length) handleUpload(subject.id, fileInput.files, el);
  });

  await loadDocumentsList(subject.id, el);
}

async function handleUpload(subjectId, fileList, el){
  const dropZone = document.getElementById('upload-drop');
  const originalHtml = dropZone.innerHTML;
  dropZone.innerHTML = `<span class="spinner" style="border-top-color:var(--navy); border-color:var(--line-strong);"></span> Uploading &amp; embedding ${fileList.length} file(s)…`;
  try{
    const docs = await Api.uploadDocuments(subjectId, fileList);
    const failed = docs.filter(d => d.upload_status === 'failed');
    if (failed.length){
      toast(`${failed.length} file(s) failed to process. Check status below.`, 'error');
    } else {
      toast('Documents uploaded and indexed.', 'success');
    }
  }catch(e){
    toast(apiErrorMessage(e), 'error');
  }
  dropZone.innerHTML = originalHtml;
  document.getElementById('file-input').value = '';
  await loadDocumentsList(subjectId, el);
}

async function loadDocumentsList(subjectId, el){
  const listEl = document.getElementById('doc-list');
  let docs;
  try{
    docs = await Api.listDocuments(subjectId);
  }catch(e){
    listEl.innerHTML = `<div class="empty-state"><h3>Couldn't load documents</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }
  if (!docs.length){
    listEl.innerHTML = `<div class="empty-state"><h3>No documents yet</h3><p>Upload lecture notes, slides, or readings to start chatting with them.</p></div>`;
    return;
  }
  listEl.innerHTML = docs.map(d => `
    <div class="doc-row">
      <div class="doc-icon">${FILE_TYPE_LABEL[d.file_type] || d.file_type.toUpperCase()}</div>
      <div class="doc-info">
        <div class="doc-name">${esc(d.filename)}</div>
        <div class="doc-meta">${fmtBytes(d.size_bytes)} · uploaded ${fmtDate(d.created_at)}</div>
      </div>
      <span class="pill ${STATUS_PILL[d.upload_status] || 'pill-muted'}">${d.upload_status}</span>
      <button class="icon-btn" data-del="${d.id}" title="Delete">✕</button>
    </div>
  `).join('');

  listEl.querySelectorAll('[data-del]').forEach(btn => {
    btn.addEventListener('click', async () => {
      if (!confirm('Delete this document and its indexed content?')) return;
      try{
        await Api.deleteDocument(btn.dataset.del);
        toast('Document deleted.', 'success');
        await loadDocumentsList(subjectId, el);
      }catch(e){ toast(apiErrorMessage(e), 'error'); }
    });
  });
}

// ---------------- Chat tab ----------------

async function renderChatTab(el, subject){
  el.innerHTML = `
    <div class="chat-layout">
      <div class="session-list" id="session-list">
        <div style="padding:10px 12px;"><button class="btn btn-amber btn-sm btn-block" id="new-session-btn">+ New chat</button></div>
      </div>
      <div class="chat-panel">
        <div class="chat-messages" id="chat-messages">
          <div class="empty-state" style="border:none;">
            <h3>Ask anything about ${esc(subject.name)}</h3>
            <p>Start a new chat — answers are grounded in your uploaded documents, with citations.</p>
          </div>
        </div>
        <div class="chat-input-bar">
          <textarea id="chat-input" rows="1" placeholder="Ask a question about your documents…" disabled></textarea>
          <button class="btn btn-amber" id="chat-send" disabled>Send</button>
        </div>
      </div>
    </div>
  `;

  let sessions = [];
  let activeSessionId = null;

  async function loadSessions(){
    try{
      sessions = await Api.listSessions(subject.id);
    }catch(e){ toast(apiErrorMessage(e), 'error'); return; }
    const list = document.getElementById('session-list');
    const btnHtml = `<div style="padding:10px 12px;"><button class="btn btn-amber btn-sm btn-block" id="new-session-btn">+ New chat</button></div>`;
    list.innerHTML = btnHtml + sessions.map(s => `
      <div class="session-item ${s.id === activeSessionId ? 'active' : ''}" data-session="${s.id}">${esc(s.title)}</div>
    `).join('');
    document.getElementById('new-session-btn').addEventListener('click', createNewSession);
    list.querySelectorAll('[data-session]').forEach(item => {
      item.addEventListener('click', () => openSession(item.dataset.session));
    });
  }

  async function createNewSession(){
    try{
      const session = await Api.createSession({ subject_id: subject.id, title: 'New Chat' });
      await loadSessions();
      openSession(session.id);
    }catch(e){ toast(apiErrorMessage(e), 'error'); }
  }

  async function openSession(sessionId){
    activeSessionId = sessionId;
    document.querySelectorAll('[data-session]').forEach(item => {
      item.classList.toggle('active', item.dataset.session === sessionId);
    });
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    input.disabled = false;
    sendBtn.disabled = false;

    const msgBox = document.getElementById('chat-messages');
    msgBox.innerHTML = `<div class="loading-page" style="min-height:100px;"><span class="spinner"></span> Loading messages…</div>`;
    try{
      const messages = await Api.listMessages(sessionId);
      drawMessages(messages);
    }catch(e){
      msgBox.innerHTML = `<div class="empty-state" style="border:none;"><p>${esc(apiErrorMessage(e))}</p></div>`;
    }
  }

  function drawMessages(messages){
    const msgBox = document.getElementById('chat-messages');
    if (!messages.length){
      msgBox.innerHTML = `<div class="empty-state" style="border:none;"><h3>Say hello</h3><p>Ask a question about the documents in this subject.</p></div>`;
      return;
    }
    msgBox.innerHTML = messages.map(renderMessageHtml).join('');
    msgBox.scrollTop = msgBox.scrollHeight;
  }

  function renderMessageHtml(m){
    const citations = (m.citations || []).map(c => `
      <span class="citation-chip" title="Chunk ${c.chunk_index}">📄 ${esc(c.filename)} <span class="rel">${c.relevance}</span></span>
    `).join('');
    return `
      <div class="msg ${m.role}">
        <div class="msg-avatar">${m.role === 'user' ? esc(initials(State.user?.name)) : '🎓'}</div>
        <div>
          <div class="msg-bubble">${esc(m.content)}</div>
          ${citations ? `<div class="citations">${citations}</div>` : ''}
        </div>
      </div>
    `;
  }

  async function sendCurrentMessage(){
    const input = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send');
    const content = input.value.trim();
    if (!content || !activeSessionId) return;

    const msgBox = document.getElementById('chat-messages');
    if (msgBox.querySelector('.empty-state')) msgBox.innerHTML = '';
    msgBox.insertAdjacentHTML('beforeend', renderMessageHtml({ role: 'user', content }));
    msgBox.insertAdjacentHTML('beforeend', `
      <div class="msg assistant" id="typing-indicator">
        <div class="msg-avatar">🎓</div>
        <div class="msg-bubble"><span class="typing-dots"><span></span><span></span><span></span></span></div>
      </div>
    `);
    msgBox.scrollTop = msgBox.scrollHeight;
    input.value = '';
    input.disabled = true;
    sendBtn.disabled = true;

    try{
      const reply = await Api.sendMessage(activeSessionId, content);
      document.getElementById('typing-indicator')?.remove();
      msgBox.insertAdjacentHTML('beforeend', renderMessageHtml(reply));
      msgBox.scrollTop = msgBox.scrollHeight;
    }catch(e){
      document.getElementById('typing-indicator')?.remove();
      toast(apiErrorMessage(e), 'error');
    }
    input.disabled = false;
    sendBtn.disabled = false;
    input.focus();
  }

  document.getElementById('chat-send').addEventListener('click', sendCurrentMessage);
  document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey){
      e.preventDefault();
      sendCurrentMessage();
    }
  });

  await loadSessions();
  if (sessions.length) {
    openSession(sessions[0].id);
  } else {
    createNewSession();
  }
}

// ---------------- Flashcards tab ----------------

const DIFFICULTIES = ['easy', 'medium', 'hard'];

async function renderFlashcardsTab(el, subject){
  el.innerHTML = `
    <div class="section-head">
      <h2>Flashcards</h2>
      <button class="btn btn-amber btn-sm" id="gen-flashcards-btn">✨ Generate flashcards</button>
    </div>
    <div id="flash-body"><div class="loading-page" style="min-height:120px;"><span class="spinner"></span> Loading…</div></div>
  `;

  document.getElementById('gen-flashcards-btn').addEventListener('click', () => openGenerateFlashcardsModal(subject));
  await loadFlashcards(subject);
}

async function loadFlashcards(subject){
  const body = document.getElementById('flash-body');
  let cards;
  try{
    cards = await Api.listFlashcards(subject.id);
  }catch(e){
    body.innerHTML = `<div class="empty-state"><h3>Couldn't load flashcards</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }
  if (!cards.length){
    body.innerHTML = `<div class="empty-state"><h3>No flashcards yet</h3><p>Generate a set from your uploaded documents.</p></div>`;
    return;
  }
  body.innerHTML = `<div class="flash-grid">${cards.map(c => `
    <div class="flashcard" data-id="${c.id}">
      <button class="remove-btn" data-del="${c.id}">✕</button>
      <div class="inner">
        <div class="face front">
          <span class="pill pill-amber" style="align-self:flex-start; margin-bottom:8px;">${c.difficulty}</span>
          <div class="face-text">${esc(c.front)}</div>
          <div class="face-hint">Click to flip</div>
        </div>
        <div class="face back">
          <div class="face-label">Answer</div>
          <div class="face-text">${esc(c.back)}</div>
          <div class="face-hint">Click to flip back</div>
        </div>
      </div>
    </div>
  `).join('')}</div>`;

  body.querySelectorAll('.flashcard').forEach(card => {
    card.addEventListener('click', (e) => {
      if (e.target.closest('[data-del]')) return;
      card.classList.toggle('flipped');
    });
  });
  body.querySelectorAll('[data-del]').forEach(btn => {
    btn.addEventListener('click', async (e) => {
      e.stopPropagation();
      try{
        await Api.deleteFlashcard(btn.dataset.del);
        await loadFlashcards(subject);
      }catch(err){ toast(apiErrorMessage(err), 'error'); }
    });
  });
}

function openGenerateFlashcardsModal(subject){
  const overlay = openModal(`
    <h2>Generate flashcards</h2>
    <div class="sub">Created from this subject's uploaded documents.</div>
    <form id="flash-form">
      <div class="row">
        <div class="field">
          <label>Count</label>
          <input type="number" name="count" min="1" max="20" value="8" required />
        </div>
        <div class="field">
          <label>Difficulty</label>
          <select name="difficulty">
            ${DIFFICULTIES.map(d => `<option value="${d}" ${d==='medium'?'selected':''}>${d}</option>`).join('')}
          </select>
        </div>
      </div>
      <div id="flash-form-error"></div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" id="flash-cancel">Cancel</button>
        <button type="submit" class="btn btn-amber" id="flash-submit">Generate</button>
      </div>
    </form>
  `);
  overlay.querySelector('#flash-cancel').addEventListener('click', () => overlay.remove());
  overlay.querySelector('#flash-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const btn = overlay.querySelector('#flash-submit');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Generating…`;
    try{
      await Api.generateFlashcards({ subject_id: subject.id, count: parseInt(data.count, 10), difficulty: data.difficulty });
      overlay.remove();
      toast('Flashcards generated.', 'success');
      await loadFlashcards(subject);
    }catch(err){
      overlay.querySelector('#flash-form-error').innerHTML = `<div class="auth-error">${esc(apiErrorMessage(err))}</div>`;
      btn.disabled = false;
      btn.textContent = 'Generate';
    }
  });
}

// ---------------- Quizzes tab ----------------

async function renderQuizzesTab(el, subject, quizIdParam){
  if (quizIdParam){
    return renderQuizTaker(el, subject, parseInt(quizIdParam, 10));
  }

  el.innerHTML = `
    <div class="section-head">
      <h2>Quizzes</h2>
      <button class="btn btn-amber btn-sm" id="gen-quiz-btn">✨ Generate quiz</button>
    </div>
    <div id="quiz-list"><div class="loading-page" style="min-height:120px;"><span class="spinner"></span> Loading…</div></div>
  `;
  document.getElementById('gen-quiz-btn').addEventListener('click', () => openGenerateQuizModal(subject));
  await loadQuizzes(subject);
}

async function loadQuizzes(subject){
  const listEl = document.getElementById('quiz-list');
  let quizzes;
  try{
    quizzes = await Api.listQuizzes(subject.id);
  }catch(e){
    listEl.innerHTML = `<div class="empty-state"><h3>Couldn't load quizzes</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }
  if (!quizzes.length){
    listEl.innerHTML = `<div class="empty-state"><h3>No quizzes yet</h3><p>Generate a multiple-choice quiz from your uploaded documents.</p></div>`;
    return;
  }
  listEl.innerHTML = quizzes.map(q => `
    <div class="quiz-card">
      <div>
        <div class="qi-title">${esc(q.title)}</div>
        <div class="qi-meta">${q.questions.length} questions · ${q.difficulty} · created ${fmtDate(q.created_at)}</div>
      </div>
      <button class="btn btn-ghost btn-sm" data-take="${q.id}">Take quiz</button>
    </div>
  `).join('');
  listEl.querySelectorAll('[data-take]').forEach(btn => {
    btn.addEventListener('click', () => { location.hash = `#/subjects/${subject.id}/quizzes/${btn.dataset.take}`; });
  });
}

function openGenerateQuizModal(subject){
  const overlay = openModal(`
    <h2>Generate quiz</h2>
    <div class="sub">Multiple-choice questions from this subject's uploaded documents.</div>
    <form id="quiz-form">
      <div class="row">
        <div class="field">
          <label>Number of questions</label>
          <input type="number" name="count" min="1" max="15" value="5" required />
        </div>
        <div class="field">
          <label>Difficulty</label>
          <select name="difficulty">
            ${DIFFICULTIES.map(d => `<option value="${d}" ${d==='medium'?'selected':''}>${d}</option>`).join('')}
          </select>
        </div>
      </div>
      <div id="quiz-form-error"></div>
      <div class="modal-actions">
        <button type="button" class="btn btn-ghost" id="quiz-cancel">Cancel</button>
        <button type="submit" class="btn btn-amber" id="quiz-submit">Generate</button>
      </div>
    </form>
  `);
  overlay.querySelector('#quiz-cancel').addEventListener('click', () => overlay.remove());
  overlay.querySelector('#quiz-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const data = Object.fromEntries(new FormData(e.target).entries());
    const btn = overlay.querySelector('#quiz-submit');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Generating…`;
    try{
      const quiz = await Api.generateQuiz({ subject_id: subject.id, count: parseInt(data.count, 10), difficulty: data.difficulty });
      overlay.remove();
      toast('Quiz generated.', 'success');
      location.hash = `#/subjects/${subject.id}/quizzes/${quiz.id}`;
      router();
    }catch(err){
      overlay.querySelector('#quiz-form-error').innerHTML = `<div class="auth-error">${esc(apiErrorMessage(err))}</div>`;
      btn.disabled = false;
      btn.textContent = 'Generate';
    }
  });
}

async function renderQuizTaker(el, subject, quizId){
  el.innerHTML = `<div class="loading-page"><span class="spinner"></span> Loading quiz…</div>`;
  let quiz;
  try{
    quiz = await Api.getQuiz(quizId);
  }catch(e){
    el.innerHTML = `<div class="empty-state"><h3>Couldn't load quiz</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }

  const answers = {};
  let submitted = null;

  function draw(){
    el.innerHTML = `
      <div style="margin-bottom:16px;">
        <button class="btn btn-ghost btn-sm" id="back-to-quizzes">← All quizzes</button>
      </div>
      ${submitted ? `
        <div class="score-banner">
          <div class="big">${submitted.score}/${submitted.total_questions}</div>
          <div class="label">${Math.round((submitted.score/submitted.total_questions)*100)}% correct</div>
        </div>
      ` : ''}
      <h2 style="margin-bottom:18px;">${esc(quiz.title)}</h2>
      <div id="questions"></div>
      ${!submitted ? `<button class="btn btn-amber" id="submit-quiz-btn">Submit answers</button>` : `<button class="btn btn-ghost" id="retake-btn">Try again</button>`}
    `;
    document.getElementById('back-to-quizzes').addEventListener('click', () => { location.hash = `#/subjects/${subject.id}/quizzes`; });

    const qContainer = document.getElementById('questions');
    qContainer.innerHTML = quiz.questions.map((q, i) => {
      const graded = submitted ? submitted.answers.find(a => a.question_index === i) : null;
      return `
        <div class="question-block">
          <div class="q-num">Question ${i+1} of ${quiz.questions.length}</div>
          <div class="q-text">${esc(q.question)}</div>
          ${q.options.map(opt => {
            let cls = '';
            if (submitted){
              if (opt === q.correct_answer) cls = 'correct';
              else if (opt === graded?.selected && !graded.is_correct) cls = 'incorrect';
            } else if (answers[i] === opt){
              cls = 'selected';
            }
            return `
              <label class="option-row ${cls}" data-q="${i}" data-opt="${esc(opt)}">
                <input type="radio" name="q${i}" ${answers[i] === opt ? 'checked' : ''} ${submitted ? 'disabled' : ''} />
                <span>${esc(opt)}</span>
              </label>
            `;
          }).join('')}
        </div>
      `;
    }).join('');

    if (!submitted){
      qContainer.querySelectorAll('.option-row').forEach(row => {
        row.addEventListener('click', () => {
          answers[row.dataset.q] = row.dataset.opt;
          draw();
        });
      });
      document.getElementById('submit-quiz-btn').addEventListener('click', async () => {
        if (Object.keys(answers).length < quiz.questions.length){
          if (!confirm(`You've only answered ${Object.keys(answers).length} of ${quiz.questions.length} questions. Submit anyway?`)) return;
        }
        try{
          submitted = await Api.submitQuiz(quiz.id, answers);
          draw();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        }catch(err){ toast(apiErrorMessage(err), 'error'); }
      });
    } else {
      document.getElementById('retake-btn').addEventListener('click', () => {
        submitted = null;
        for (const k in answers) delete answers[k];
        draw();
      });
    }
  }

  draw();
}

// ---------------- Progress tab ----------------

async function renderProgressTab(el, subject){
  el.innerHTML = `<div class="loading-page"><span class="spinner"></span> Loading progress…</div>`;
  let progress;
  try{
    progress = await Api.getSubjectProgress(subject.id);
  }catch(e){
    el.innerHTML = `<div class="empty-state"><h3>Couldn't load progress</h3><p>${esc(apiErrorMessage(e))}</p></div>`;
    return;
  }

  el.innerHTML = `
    <div class="grid grid-3" style="margin-bottom:22px;">
      <div class="stat-card"><div class="stat-label">Study hours</div><div class="stat-value">${progress.study_hours}</div></div>
      <div class="stat-card"><div class="stat-label">Quizzes completed</div><div class="stat-value">${progress.completed_quizzes}</div></div>
      <div class="stat-card"><div class="stat-label">Last updated</div><div class="stat-value" style="font-size:16px;">${fmtDate(progress.updated_at)}</div></div>
    </div>

    <div class="grid grid-2" style="margin-bottom:22px;">
      <div class="card">
        <div class="eyebrow" style="color:var(--green);">Strong topics</div>
        <div class="topic-list" style="margin-top:10px;">
          ${(progress.strong_topics||[]).length ? progress.strong_topics.map(t => `<span class="pill pill-green">${esc(t)}</span>`).join('') : '<span style="font-size:13px;color:var(--ink-faint);">None yet.</span>'}
        </div>
      </div>
      <div class="card">
        <div class="eyebrow" style="color:var(--brick);">Weak topics</div>
        <div class="topic-list" style="margin-top:10px;">
          ${(progress.weak_topics||[]).length ? progress.weak_topics.map(t => `<span class="pill pill-brick">${esc(t)}</span>`).join('') : '<span style="font-size:13px;color:var(--ink-faint);">Nothing flagged.</span>'}
        </div>
      </div>
    </div>

    <div class="card">
      <div class="section-head"><h2>Log study time</h2></div>
      <form id="log-time-form" style="display:flex; gap:10px; align-items:flex-end;">
        <div class="field" style="margin-bottom:0; flex:1; max-width:180px;">
          <label>Hours</label>
          <input type="number" name="hours" min="0.1" max="24" step="0.1" value="1" required />
        </div>
        <button class="btn btn-amber" type="submit">Add time</button>
      </form>
    </div>
  `;

  document.getElementById('log-time-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const hours = parseFloat(new FormData(e.target).get('hours'));
    try{
      await Api.logStudyTime(subject.id, hours);
      toast('Study time logged.', 'success');
      await renderProgressTab(el, subject);
    }catch(err){ toast(apiErrorMessage(err), 'error'); }
  });
}

// ==========================================================================
// Boot
// ==========================================================================

router();
