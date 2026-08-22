/* ==========================================================================
   EduMentor — API client
   Thin wrapper around fetch() for the FastAPI backend built in Phase 2.
   Base URL is editable at runtime (bottom of the sidebar) and persisted
   in localStorage, since the backend usually runs on localhost:8000.
   ========================================================================== */

// When this frontend is served BY the FastAPI backend itself (the default
// setup — see backend/app/main.py's StaticFiles mount), the browser's own
// origin already points at the API, so a relative path is correct and needs
// no configuration. If you instead serve the frontend separately (e.g.
// `python -m http.server` on a different port than the backend), override
// this via the "API" field at the bottom of the sidebar, which is saved to
// localStorage and takes priority over this default.
const DEFAULT_API_BASE = `${location.origin}/api/v1`;

const Store = {
  getApiBase(){ return localStorage.getItem('edumentor_api_base') || DEFAULT_API_BASE; },
  setApiBase(v){ localStorage.setItem('edumentor_api_base', v || DEFAULT_API_BASE); },
  getToken(){ return localStorage.getItem('edumentor_token'); },
  setToken(t){ if(t) localStorage.setItem('edumentor_token', t); else localStorage.removeItem('edumentor_token'); },
  getUser(){ try{ return JSON.parse(localStorage.getItem('edumentor_user')); } catch(e){ return null; } },
  setUser(u){ if(u) localStorage.setItem('edumentor_user', JSON.stringify(u)); else localStorage.removeItem('edumentor_user'); },
  clearAuth(){ this.setToken(null); this.setUser(null); },
};

class ApiError extends Error{
  constructor(message, status, detail){
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, { method = 'GET', body, isForm = false, auth = true } = {}){
  const headers = {};
  if (!isForm) headers['Content-Type'] = 'application/json';
  if (auth){
    const token = Store.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;
  }

  let res;
  try{
    res = await fetch(`${Store.getApiBase()}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : (isForm ? body : JSON.stringify(body)),
    });
  }catch(networkErr){
    throw new ApiError(
      `Can't reach the API at ${Store.getApiBase()}. Is the backend running and is the URL correct?`,
      0, null
    );
  }

  if (res.status === 204) return null;

  let payload = null;
  const text = await res.text();
  if (text){
    try{ payload = JSON.parse(text); }catch(e){ payload = text; }
  }

  if (!res.ok){
    let detail = payload && payload.detail ? payload.detail : (typeof payload === 'string' ? payload : res.statusText);
    if (Array.isArray(detail)){
      // FastAPI validation errors
      detail = detail.map(d => d.msg || JSON.stringify(d)).join('; ');
    }
    if (res.status === 401){
      Store.clearAuth();
    }
    throw new ApiError(detail || `Request failed (${res.status})`, res.status, payload);
  }

  return payload;
}

const Api = {
  // ---------------- auth ----------------
  register(data){ return request('/auth/register', { method: 'POST', body: data, auth: false }); },
  login(data){ return request('/auth/login', { method: 'POST', body: data, auth: false }); },
  me(){ return request('/auth/me'); },

  // ---------------- subjects ----------------
  listSubjects(semester){ return request(`/subjects/${semester ? `?semester=${semester}` : ''}`); },
  getSubject(id){ return request(`/subjects/${id}`); },
  createSubject(data){ return request('/subjects/', { method: 'POST', body: data }); },

  // ---------------- documents ----------------
  listDocuments(subjectId){ return request(`/documents/subject/${subjectId}`); },
  uploadDocuments(subjectId, files){
    const form = new FormData();
    form.append('subject_id', subjectId);
    for (const f of files) form.append('files', f);
    return request('/documents/upload', { method: 'POST', body: form, isForm: true });
  },
  deleteDocument(id){ return request(`/documents/${id}`, { method: 'DELETE' }); },

  // ---------------- chat ----------------
  listSessions(subjectId){ return request(`/chat/sessions${subjectId ? `?subject_id=${subjectId}` : ''}`); },
  createSession(data){ return request('/chat/sessions', { method: 'POST', body: data }); },
  listMessages(sessionId){ return request(`/chat/sessions/${sessionId}/messages`); },
  sendMessage(sessionId, content){ return request(`/chat/sessions/${sessionId}/messages`, { method: 'POST', body: { content } }); },
  deleteSession(sessionId){ return request(`/chat/sessions/${sessionId}`, { method: 'DELETE' }); },

  // ---------------- study tools: flashcards ----------------
  generateFlashcards(data){ return request('/study-tools/flashcards/generate', { method: 'POST', body: data }); },
  listFlashcards(subjectId, documentId){
    let q = `?subject_id=${subjectId}`;
    if (documentId) q += `&document_id=${documentId}`;
    return request(`/study-tools/flashcards${q}`);
  },
  deleteFlashcard(id){ return request(`/study-tools/flashcards/${id}`, { method: 'DELETE' }); },

  // ---------------- study tools: quizzes ----------------
  generateQuiz(data){ return request('/study-tools/quizzes/generate', { method: 'POST', body: data }); },
  listQuizzes(subjectId){ return request(`/study-tools/quizzes?subject_id=${subjectId}`); },
  getQuiz(id){ return request(`/study-tools/quizzes/${id}`); },
  submitQuiz(id, answers){ return request(`/study-tools/quizzes/${id}/submit`, { method: 'POST', body: { answers } }); },
  listQuizAttempts(id){ return request(`/study-tools/quizzes/${id}/attempts`); },

  // ---------------- analytics ----------------
  getDashboard(){ return request('/analytics/dashboard'); },
  getSubjectProgress(subjectId){ return request(`/analytics/progress/${subjectId}`); },
  listProgress(){ return request('/analytics/progress'); },
  logStudyTime(subjectId, hours){ return request('/analytics/progress/study-time', { method: 'POST', body: { subject_id: subjectId, hours } }); },
};
