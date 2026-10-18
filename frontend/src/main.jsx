import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { onAuthStateChanged, signInWithPopup, GoogleAuthProvider, signOut } from 'firebase/auth';
import { Activity, ArrowUpRight, Building2, Check, CircleHelp, FileText, GitBranch, KeyRound, Layers3, LogOut, Menu, MessageSquareText, PanelLeftClose, PanelLeftOpen, Settings2, ShieldCheck, Sparkles, UserRound, Users, X } from 'lucide-react';
import { auth, firebaseConfigured } from './firebase';
import './style.css';

const suggestions = [
  'Why has Service A failed after recent deployments?',
  'Who owns the authentication service?',
  'Show me the deployment procedure for Service A',
];
const API_BASE = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '');

function App() {
  const [user, setUser] = useState(null);
  const [companies, setCompanies] = useState([]);
  const [companyId, setCompanyId] = useState(() => localStorage.getItem('nexushelper-company-id') || '');
  const [demoSession, setDemoSession] = useState(() => localStorage.getItem('nexushelper-demo-session') === 'emp-alice');
  const [query, setQuery] = useState('');
  const [profileOpen, setProfileOpen] = useState(false);
  const [profile, setProfile] = useState({ designation: '', department: '', keywords: '' });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');
  const [theme, setTheme] = useState(() => localStorage.getItem('nexushelper-theme') || 'dark');
  const [activeSection, setActiveSection] = useState('ask');
  const [showSetupDetails, setShowSetupDetails] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('nexushelper-sidebar-collapsed') === 'true');
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  function navigate(section) {
    setActiveSection(section);
    setNotice('');
    setMobileMenuOpen(false);
  }

  function toggleSidebar() {
    setSidebarCollapsed((current) => {
      localStorage.setItem('nexushelper-sidebar-collapsed', String(!current));
      return !current;
    });
  }

  useEffect(() => {
    document.body.dataset.theme = theme;
    localStorage.setItem('nexushelper-theme', theme);
  }, [theme]);

  useEffect(() => {
    if (!auth) return;
    return onAuthStateChanged(auth, async (current) => {
      setUser(current);
      setCompanies([]);
      if (current) {
        setDemoSession(false);
        localStorage.removeItem('nexushelper-demo-session');
        const token = await current.getIdTokenResult();
        setProfile((old) => ({ ...old, department: token.claims.department || old.department }));
        try {
          const companyResponse = await fetch(`${API_BASE}/api/companies`, { headers: { Authorization: `Bearer ${await current.getIdToken()}` } });
          if (companyResponse.ok) {
            const list = await companyResponse.json(); setCompanies(list);
            const selected = list.some((item) => item.id === companyId) ? companyId : (list.length === 1 ? list[0].id : '');
            setCompanyId(selected); if (selected) localStorage.setItem('nexushelper-company-id', selected); else localStorage.removeItem('nexushelper-company-id');
          }
        } catch { /* The workspace remains usable if account metadata is briefly unavailable. */ }
        setProfileOpen(!localStorage.getItem(`profile:${current.uid}`));
      }
    });
  }, []);

  useEffect(() => { if (demoSession) setCompanies([{ id: 'demo', name: 'NexusHelper Demo', role: 'owner', team_ids: ['team-platform'] }]); }, [demoSession]);

  async function login() {
    if (!auth) {
      if (import.meta.env.DEV || import.meta.env.VITE_DEMO_AUTH_ENABLED === 'true') {
        localStorage.setItem('nexushelper-demo-session', 'emp-alice');
        setDemoSession(true);
        setNotice('Local demo session started as Alice (Platform). This synthetic identity is for development only.');
      } else setNotice('Sign-in is not connected yet. Add your Firebase Web App settings to frontend/.env, then restart the frontend.');
      return;
    }
    try { await signInWithPopup(auth, new GoogleAuthProvider()); }
    catch (error) { setNotice(error.message); }
  }

  async function submitProfile(event) {
    event.preventDefault();
    if (!user && !demoSession) return;
    const token = user ? await user.getIdToken() : '';
    try {
      const response = await fetch(`${API_BASE}/api/me/profile`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json', ...(user ? { Authorization: `Bearer ${token}` } : { 'X-Demo-User': 'emp-alice' }), ...(companyId ? { 'X-Company-ID': companyId } : {}) },
        body: JSON.stringify({ ...profile, keywords: profile.keywords.split(',').map((word) => word.trim()).filter(Boolean) }),
      });
      if (response.ok) {
        if (user) localStorage.setItem(`profile:${user.uid}`, 'complete');
        setProfileOpen(false);
        setNotice('Profile saved. Your designation and keywords are searchable profile details.');
      } else setNotice('Could not save profile. Check that the API is running.');
    } catch { setNotice('Could not reach the NexusHelper API. Start the local API or check its configured URL.'); }
  }

  async function ask(question = query) {
    const text = question.trim();
    if (!text) return;
    if (!user && !demoSession) {
      setActiveSection('ask');
      setNotice(firebaseConfigured ? 'Sign in to NexusHelper before asking about company records.' : 'Start a local demo session or configure Firebase sign-in and the NexusHelper API.');
      return;
    }
    setQuery(text); setLoading(true); setResult(null); setNotice('');
    try {
      const token = user ? await user.getIdToken() : '';
      const response = await fetch(`${API_BASE}/api/query`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : demoSession ? { 'X-Demo-User': 'emp-alice' } : {}), ...(companyId ? { 'X-Company-ID': companyId } : {}) },
        body: JSON.stringify({ query: text }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail || 'The request could not be completed.');
      setResult(body);
    } catch (error) { setNotice(error.message); }
    finally { setLoading(false); }
  }

  const departments = ['Engineering', 'Human Resources', 'Finance', 'Operations', 'Security', 'Customer Support', 'Other'];
  const activeUser = user || (demoSession ? { displayName: 'Alice Rao · Local demo', email: 'emp-alice@local', photoURL: '' } : null);
  const authenticated = Boolean(user || demoSession);

  return <div className={`app-shell ${sidebarCollapsed ? 'sidebar-collapsed' : ''} ${mobileMenuOpen ? 'mobile-menu-open' : ''}`}>
    {mobileMenuOpen && <button className="mobile-scrim" aria-label="Close navigation menu" onClick={() => setMobileMenuOpen(false)}/>}
    <aside className="sidebar">
      <div className="sidebar-heading"><a className="brand" href="#" onClick={(event) => { event.preventDefault(); navigate('ask'); }}><span className="brand-name">NexusHelper</span><span className="beta">BETA</span></a><button className="sidebar-collapse" onClick={toggleSidebar} aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'} title={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}>{sidebarCollapsed ? <PanelLeftOpen size={17}/> : <PanelLeftClose size={17}/>}</button></div>
      <div className="workspace"><div className="workspace-mark">N</div><div><strong>{companies.find((item) => item.id === companyId)?.name || 'NexusHelper'}</strong><small>Company workspace</small></div>{companies.length > 1 && <select aria-label="Select company" value={companyId} onChange={(e) => { setCompanyId(e.target.value); localStorage.setItem('nexushelper-company-id', e.target.value); }}><option value="">Select</option>{companies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>}</div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Workspace navigation">
        <button className={`nav-item nav-button ${activeSection === 'ask' ? 'active' : ''}`} onClick={() => navigate('ask')}><MessageSquareText size={17}/> <span className="nav-text">Ask NexusHelper</span> <span className="nav-shortcut">⌘ K</span></button>
        <button className={`nav-item nav-button ${activeSection === 'graph' ? 'active' : ''}`} onClick={() => navigate('graph')}><GitBranch size={17}/> <span className="nav-text">Knowledge graph</span></button>
        <button className={`nav-item nav-button ${activeSection === 'sources' ? 'active' : ''}`} onClick={() => navigate('sources')}><FileText size={17}/> <span className="nav-text">Sources</span></button>
        <button className={`nav-item nav-button ${activeSection === 'people' ? 'active' : ''}`} onClick={() => navigate('people')}><Users size={17}/> <span className="nav-text">People &amp; teams</span></button>
        <button className={`nav-item nav-button ${activeSection === 'companies' ? 'active' : ''}`} onClick={() => navigate('companies')}><Building2 size={17}/> <span className="nav-text">Companies &amp; teams</span></button>
      </nav>
      <div className="nav-label source-label">YOUR CONTEXT</div>
      <div className="context-card"><div className="context-icon"><Building2 size={15}/></div><div><strong>Build your profile</strong><small>Add your role and team keywords</small></div><button aria-label="Set profile" onClick={() => setProfileOpen(true)} title="Set up your profile"><ArrowUpRight size={15}/></button></div>
      <div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={15}/><span>Access is based on verified<br/>company membership</span></div>
        {activeUser ? <button className="user-row" onClick={() => { if (user) signOut(auth); else { setDemoSession(false); localStorage.removeItem('nexushelper-demo-session'); setNotice('Local demo session ended.'); } }}><img src={activeUser.photoURL || ''} alt=""/><span><b>{activeUser.displayName || activeUser.email}</b><small>Sign out</small></span><LogOut size={15}/></button> : <button className="signin-small" onClick={login}><KeyRound size={15}/> {firebaseConfigured ? 'Sign in' : 'Start local demo'}</button>}
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="topbar-leading"><button className="mobile-menu-toggle" aria-label="Open navigation menu" title="Open navigation menu" onClick={() => setMobileMenuOpen(true)}><Menu size={20}/></button><div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><b>{activeSection === 'ask' ? 'Ask NexusHelper' : activeSection === 'graph' ? 'Knowledge graph' : activeSection === 'sources' ? 'Sources' : activeSection === 'people' ? 'People & teams' : activeSection === 'companies' ? 'Companies & teams' : 'Setup & connections'}</b></div></div><div className="top-actions"><label className="theme-control" title="Choose appearance"><span>THEME</span><select aria-label="Theme" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="dark">Dark</option><option value="light">Light</option><option value="warm">Warm</option></select></label><button className="icon-button setup-tab-icon" aria-label="Setup and connections" title="Setup and connections" onClick={() => navigate('help')}><span aria-hidden="true">N</span></button><div className="top-divider"/>{activeUser ? <button className="avatar-button" onClick={() => setProfileOpen(true)}><img src={activeUser.photoURL || ''} alt="Profile"/></button> : <button className="top-signin" onClick={login}>{firebaseConfigured ? 'Sign in' : 'Try demo'} <ArrowUpRight size={14}/></button>}</div></header>
      <section className={`content ${activeSection !== 'ask' ? 'content-page' : ''}`}>
        {activeSection === 'companies' ? <CompanyHubPage firebaseUser={user} companies={companies} selectedCompanyId={companyId} onCompaniesChange={(list, selected) => { setCompanies(list); setCompanyId(selected || ''); if (selected) localStorage.setItem('nexushelper-company-id', selected); }} onLogin={login} /> : <>
        {activeSection === 'ask' ? <>
        <div className="eyebrow"><span className="live-dot"/> NEXUSHELPER KNOWLEDGE, CONNECTED</div>
        <h1>Find answers<br/><span>across your company.</span></h1>
        <p className="intro">Ask across teams, projects, and decisions.<br/>Get answers connected to their sources.</p>
        {!firebaseConfigured && <div className="config-callout"><span className="connection-indicator" aria-hidden="true"/><p><strong>Preview mode · connections not configured</strong><span>Add Firebase settings and start the NexusHelper API to enable sign-in and company queries.</span></p><button onClick={() => setNotice('In Firebase Console, create a Web App, enable Google sign-in in Authentication, and copy its config values into frontend/.env.')}><ArrowUpRight size={15}/></button></div>}
        <div className="ask-box"><textarea value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); ask(); } }} placeholder="Ask a question about your company..." rows={2}/><div className="ask-footer"><span><Sparkles size={14}/> Answers include evidence</span><button disabled={loading || !query.trim()} onClick={() => ask()}>{loading ? 'Searching…' : 'Ask'}<span>↗</span></button></div></div>
        {!result && <div className="suggestions"><span className="section-kicker">TRY ASKING</span>{suggestions.map((item) => <button key={item} onClick={() => ask(item)}>{item}<ArrowUpRight size={14}/></button>)}</div>}
        {notice && <div className="notice"><CircleHelp size={16}/><span>{notice}</span><button onClick={() => setNotice('')}><X size={15}/></button></div>}
        {result && <section className="answer-panel"><div className="answer-heading"><div><span className="answer-tag"><Sparkles size={13}/> NEXUSHELPER RESPONSE</span><h2>{result.abstained ? 'Here’s what I found' : 'Answer'}</h2></div><div className="confidence">{Math.round((result.confidence || 0) * 100)}% confidence</div></div><p className="answer-text">{result.answer}</p><div className="result-meta"><span><Layers3 size={14}/> Tier {result.trace.tier}: {result.trace.tier_name}</span><span><Activity size={14}/>{result.trace.model_calls} model calls</span><span>{result.trace.latency_ms} ms</span></div><div className="evidence-title"><span>CONNECTED EVIDENCE</span><span>{result.evidence.length} records</span></div>{result.evidence.length ? <div className="evidence-list">{result.evidence.map((entry) => <article className="evidence-card" key={entry.node_id}><div className="evidence-type"><FileText size={15}/></div><div className="evidence-copy"><strong>{entry.label}</strong><p>{entry.summary}</p><small>{entry.node_id} · {entry.status.replace('_', ' ')}</small></div>{entry.source_url && <a href={entry.source_url} target="_blank" rel="noreferrer"><ArrowUpRight size={15}/></a>}</article>)}</div> : <div className="empty-evidence">No accessible records matched this question.</div>}</section>}
        <div className="privacy-foot"><ShieldCheck size={14}/> Your access scope is checked before records are retrieved.</div>
        </> : <CapabilityPage section={activeSection} user={activeUser} firebaseUser={user} demoSession={demoSession} companyId={companyId} onLogin={login} onProfile={() => setProfileOpen(true)} showDetails={showSetupDetails} onToggleDetails={() => setShowSetupDetails((value) => !value)} />}</>}
      </section>
      <footer className="page-footer"><span>NEXUSHELPER <i>·</i> COMPANY KNOWLEDGE</span><span><span className="footer-dot"/> Firebase identity · shared graph</span></footer>
    </main>
    {profileOpen && <div className="modal-backdrop" onClick={() => setProfileOpen(false)}><section className="profile-modal" onClick={(e) => e.stopPropagation()}><button className="modal-close" onClick={() => setProfileOpen(false)}><X size={17}/></button><div className="modal-mark"><UserRound size={20}/></div><div className="eyebrow">MAKE NEXUSHELPER YOURS</div><h2>Set up your work profile</h2><p className="modal-description">Help connect your questions to the right people and knowledge across NexusHelper.</p>{!authenticated && <div className="signin-callout"><KeyRound size={17}/><span>{firebaseConfigured ? 'Sign in with your company account to continue.' : 'Start a local demo or configure Firebase company sign-in.'}</span><button onClick={() => { setProfileOpen(false); login(); }}>{firebaseConfigured ? 'Sign in' : 'Try demo'}</button></div>}<form onSubmit={submitProfile}><label>YOUR DESIGNATION<input required minLength="2" placeholder="e.g. Human Resources Manager" value={profile.designation} onChange={(e) => setProfile({...profile, designation: e.target.value})}/></label><label>DEPARTMENT<select required value={profile.department} onChange={(e) => setProfile({...profile, department: e.target.value})}><option value="">Select your department</option>{departments.map((dep) => <option key={dep}>{dep}</option>)}</select></label><label>KNOWLEDGE KEYWORDS <span className="optional">OPTIONAL</span><input placeholder="e.g. hiring, onboarding, benefits" value={profile.keywords} onChange={(e) => setProfile({...profile, keywords: e.target.value})}/><small>Keywords help people find expertise. They never grant data access.</small></label><div className="access-note"><ShieldCheck size={16}/><span>Company and team access comes from verified membership.</span></div><button type="submit" className="save-profile" disabled={!authenticated}>Save profile <Check size={16}/></button></form></section></div>}
  </div>;
}


function CompanyHubPage({ firebaseUser, companies, selectedCompanyId, onCompaniesChange, onLogin }) {
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [email, setEmail] = useState('');
  const [teams, setTeams] = useState('');
  const [days, setDays] = useState('');
  const [members, setMembers] = useState([]);
  const [message, setMessage] = useState('');
  const [invite, setInvite] = useState('');
  const company = companies.find((item) => item.id === selectedCompanyId);
  async function request(path, options = {}, companyHeader = selectedCompanyId) {
    if (!firebaseUser) throw new Error('Sign in with your verified company account to continue.');
    const response = await fetch(`${API_BASE}${path}`, { ...options, headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${await firebaseUser.getIdToken()}`, ...(companyHeader ? { 'X-Company-ID': companyHeader } : {}), ...(options.headers || {}) } });
    const body = await response.json(); if (!response.ok) throw new Error(body.detail || 'The request could not be completed.'); return body;
  }
  async function refresh() {
    if (!firebaseUser) return;
    try { const list = await request('/api/companies', {}, ''); onCompaniesChange(list, selectedCompanyId || list[0]?.id || '');
      if (selectedCompanyId && company?.role === 'owner') setMembers(await request(`/api/companies/${selectedCompanyId}/members`));
    } catch (error) { setMessage(error.message); }
  }
  useEffect(() => { refresh(); }, [firebaseUser, selectedCompanyId]);
  async function create(event) { event.preventDefault(); try { const created = await request('/api/companies', { method: 'POST', body: JSON.stringify({ name }) }, ''); const list = await request('/api/companies', {}, ''); onCompaniesChange(list, created.id); setMessage(`Company “${created.name}” created. You own this workspace.`); setName(''); } catch (error) { setMessage(error.message); } }
  async function accept(event) { event.preventDefault(); try { const joined = await request('/api/companies/invitations/accept', { method: 'POST', body: JSON.stringify({ code }) }, ''); const list = await request('/api/companies', {}, ''); onCompaniesChange(list, joined.id); setMessage(`Joined ${joined.name || 'company'}.`); setCode(''); } catch (error) { setMessage(error.message); } }
  async function sendInvite(event) { event.preventDefault(); try { const result = await request(`/api/companies/${selectedCompanyId}/invitations`, { method: 'POST', body: JSON.stringify({ email, team_ids: teams.split(',').map((item) => item.trim()).filter(Boolean), expires_in_days: days ? Number(days) : null }) }); setInvite(result.code); setMessage(`Invitation created for ${result.email}. Copy the one-time code and send it to them.`); } catch (error) { setMessage(error.message); } }
  async function makeOwner(member) { try { await request(`/api/companies/${selectedCompanyId}/members/${encodeURIComponent(member.user_id)}`, { method: 'PUT', body: JSON.stringify({ team_ids: member.team_ids || [], role: 'owner', expires_in_days: null }) }); setMembers(await request(`/api/companies/${selectedCompanyId}/members`)); setMessage('Company ownership updated.'); } catch (error) { setMessage(error.message); } }
  return <div className="capability-page company-hub"><div className="capability-icon"><Building2 size={22}/></div><div className="eyebrow">COMPANY WORKSPACES</div><h1>Companies &amp; teams</h1><p className="capability-description">Each company has its own knowledge graph. Invite people by verified email and give them all-company or temporary team access.</p>
    {!firebaseUser ? <div className="connection-card"><div className="connection-copy"><strong>Sign in to create or join a company.</strong></div><button className="primary-action" onClick={onLogin}>Sign in<ArrowUpRight size={15}/></button></div> : <>
      {companies.length > 1 && <label className="company-picker">ACTIVE COMPANY<select value={selectedCompanyId} onChange={(e) => onCompaniesChange(companies, e.target.value)}>{companies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>}
      {company && <div className="connection-card"><div className="connection-status-icon"><Building2 size={18}/></div><div className="connection-copy"><span className="connection-label">ACTIVE WORKSPACE</span><strong>{company.name} · {company.role}</strong><p>Teams: {company.team_ids?.join(', ') || 'No team scopes assigned'}{company.expires_at ? ` · access expires ${new Date(company.expires_at * 1000).toLocaleDateString()}` : ''}</p></div></div>}
      <div className="company-forms"><form onSubmit={create}><h2>Create a company</h2><p>You become the first owner and can invite colleagues.</p><input required minLength="2" maxLength="100" placeholder="Company name" value={name} onChange={(e) => setName(e.target.value)}/><button className="primary-action">Create company<Check size={15}/></button></form>
      <form onSubmit={accept}><h2>Join with an invitation</h2><p>Use the one-time code sent to your verified email.</p><input required minLength="20" placeholder="Invitation code" value={code} onChange={(e) => setCode(e.target.value)}/><button className="primary-action">Join company<ArrowUpRight size={15}/></button></form></div>
      {company?.role === 'owner' && <><form className="company-invite-form" onSubmit={sendInvite}><h2>Invite a teammate</h2><label>Verified email<input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="colleague@company.com"/></label><label>Team IDs<input value={teams} onChange={(e) => setTeams(e.target.value)} placeholder="team-platform, team-support"/><small>Leave blank for company-wide graph access.</small></label><label>Temporary access · days<input type="number" min="1" max="90" value={days} onChange={(e) => setDays(e.target.value)} placeholder="Leave blank for ongoing access"/></label><button className="primary-action">Create invitation<ArrowUpRight size={15}/></button></form>{invite && <div className="invite-code"><strong>One-time invitation code</strong><code>{invite}</code><button onClick={() => navigator.clipboard?.writeText(invite)}>Copy code</button></div>}<h2>Company members</h2><div className="download-platforms">{members.map((member) => <article key={member.user_id}><strong>{member.user_id}</strong><span>{member.team_ids?.join(', ') || 'Company-wide'} · {member.role}</span>{member.expires_at && <small>Expires {new Date(member.expires_at * 1000).toLocaleDateString()}</small>}{member.role !== 'owner' && <button className="member-owner-action" onClick={() => makeOwner(member)}>Make owner</button>}</article>)}</div></>}
    </>}{message && <div className="notice"><CircleHelp size={16}/><span>{message}</span></div>}</div>;
}

function CapabilityPage({ section, user, firebaseUser, demoSession, companyId, onLogin, onProfile, showDetails, onToggleDetails }) {
  const [workspace, setWorkspace] = useState(null);
  const [workspaceError, setWorkspaceError] = useState('');
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  useEffect(() => {
    if (!['graph', 'sources', 'people'].includes(section) || !user) return;
    let cancelled = false;
    setWorkspaceLoading(true);
    (async () => {
      try {
        const token = firebaseUser ? await firebaseUser.getIdToken() : '';
        const response = await fetch(`${API_BASE}/api/workspace`, { headers: { ...(token ? { Authorization: `Bearer ${token}` } : demoSession ? { 'X-Demo-User': 'emp-alice' } : {}), ...(companyId ? { 'X-Company-ID': companyId } : {}) } });
        const body = await response.json();
        if (!response.ok) throw new Error(body.detail || 'Could not load workspace data.');
        if (!cancelled) { setWorkspace(body); setWorkspaceError(''); }
      } catch (error) { if (!cancelled) setWorkspaceError(error.message); }
      finally { if (!cancelled) setWorkspaceLoading(false); }
    })();
    return () => { cancelled = true; };
  }, [section, user, firebaseUser, demoSession, companyId]);
  const pages = {
    graph: {
      icon: GitBranch, eyebrow: 'NEXUSHELPER KNOWLEDGE', title: 'Knowledge graph',
      description: 'Explore how services, teams, people, decisions, and evidence connect.',
      status: workspace?.connected ? `FalkorDB connected · ${workspace.services.length} visible services` : workspaceLoading ? 'Checking company graph…' : 'Company graph not connected · general AI available',
      detail: workspaceError || (workspace?.connected ? 'Live services and ownership are loaded from the company-specific FalkorDB graph using your verified access scope.' : 'NexusHelper can answer general questions without FalkorDB. Connect a graph only when you need company records and evidence.'),
      action: 'View graph setup',
    },
    sources: {
      icon: FileText, eyebrow: 'KNOWLEDGE SOURCES', title: 'Sources',
      description: 'Bring approved documents, tickets, and conversations into one searchable knowledge space.',
      status: workspace?.connected ? `${workspace.sources.length} evidence sources in FalkorDB` : workspaceLoading ? 'Checking company graph…' : 'No graph sources connected',
      detail: workspaceError || (workspace?.connected ? 'Sources linked to visible incidents and evidence are loaded from the shared knowledge graph. External sync connectors are separate integrations.' : 'General NexusHelper answers remain available. Company documents and source evidence require a connected graph.'),
      action: 'View connection details',
    },
    people: {
      icon: Users, eyebrow: 'YOUR ORGANIZATION', title: 'People & teams',
      description: 'Find team ownership and expertise using verified company profiles and memberships.',
      status: user ? (workspace?.connected ? `${workspace.people.length} people · ${new Set(workspace.services.map((s) => s.team_id).filter(Boolean)).size} teams in scope` : workspaceLoading ? 'Loading verified directory…' : 'Company directory not connected') : 'Sign in to view your directory',
      detail: workspaceError || (workspace?.connected ? `Signed in as ${workspace.identity?.display_name || user.displayName || user.email || 'verified user'}. Team access comes from trusted membership, not profile text.` : user ? 'The directory needs company graph data. You can still ask general questions in Ask NexusHelper.' : 'Sign in with your company account to see identity-scoped team information.'),
      action: user ? 'Set up your profile' : 'Sign in to continue',
    },
    help: {
      icon: Settings2, eyebrow: 'NEXUSHELPER STATUS', title: 'Setup & connections',
      description: 'The workspace shell is ready. Connect the services below to enable company-specific features.',
      status: firebaseConfigured ? 'Firebase web settings detected' : 'Firebase sign-in not connected',
      detail: 'For local setup, configure Firebase Authentication, start the API, then connect a private FalkorDB graph. Until those services are available, NexusHelper will not retrieve company records.',
      action: 'View setup details',
    },
  };
  const page = pages[section] || pages.help;
  const Icon = page.icon;
  const handleAction = () => {
    if (section === 'people') {
      if (user) onProfile(); else onLogin();
    } else onToggleDetails();
  };
  return <div className="capability-page">
    <div className="capability-icon"><Icon size={22}/></div>
    <div className="eyebrow">{page.eyebrow}</div>
    <h1>{page.title}</h1>
      <p className="capability-description">{page.description}</p>
    <div className="connection-card">
      <div className="connection-status-icon"><Activity size={18}/></div>
      <div className="connection-copy"><span className="connection-label">WORKSPACE CONNECTION</span><strong>{page.status}</strong><p>{page.detail}</p></div>
      <span className="status-pill"><span/> {workspace?.connected ? 'Connected' : workspaceLoading ? 'Loading' : user ? 'General AI ready' : 'Sign in'}</span>
    </div>
    {workspace && section === 'graph' && <div className="download-platforms">{workspace.services.map((item) => <article key={item.id}><strong>{item.name}</strong><span>{item.team_name ? `Owned by ${item.team_name}` : 'No owner recorded'}</span><small>{item.id}</small></article>)}</div>}
    {workspace && section === 'sources' && <div className="download-platforms">{workspace.sources.length ? workspace.sources.map((item) => <article key={item.id}><strong>{item.type || 'Evidence source'}</strong><span>{item.url || item.id}</span><small>{item.id}</small></article>) : <article><strong>No linked sources yet</strong><span>The graph has no source records visible to this identity.</span></article>}</div>}
    {workspace && section === 'people' && <div className="download-platforms">{workspace.people.length ? workspace.people.map((item) => <article key={item.id}><strong>{item.name}</strong><span>{item.role} · {item.team_name}</span><small>{item.id}</small></article>) : <article><strong>No team directory entries in your access scope</strong><span>Your verified sign-in works. Join a company workspace or ask a teammate for an invitation.</span></article>}</div>}
    {!user && ['graph', 'sources', 'people'].includes(section) && <div className="capability-actions"><button className="primary-action" onClick={onLogin}>Sign in to load company data<ArrowUpRight size={15}/></button></div>}
    {showDetails && <div className="setup-detail"><strong>What you’ll need</strong><p>{section === 'graph' ? 'A private FalkorDB endpoint, credentials stored outside the repository, and the NexusHelper graph schema.' : section === 'sources' ? 'An approved connector, its OAuth/API credentials, and an access policy matching the source system.' : 'Firebase Authentication settings and Firestore company membership data.'}</p></div>}
    <div className="capability-actions"><button className="primary-action" onClick={handleAction}>{page.action}<ArrowUpRight size={15}/></button><span>{workspace?.connected ? 'Data shown is scoped to your verified identity.' : 'Company records are unavailable; general NexusHelper questions can still be answered.'}</span></div>
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
