import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { onAuthStateChanged, signInWithPopup, GoogleAuthProvider, signOut } from 'firebase/auth';
import { Activity, ArrowUpRight, Building2, Check, CircleHelp, Download, FileText, GitBranch, KeyRound, Layers3, LogOut, Menu, MessageSquareText, PanelLeftClose, PanelLeftOpen, Settings2, ShieldCheck, Sparkles, UserRound, Users, X } from 'lucide-react';
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
      if (current) {
        setDemoSession(false);
        localStorage.removeItem('nexushelper-demo-session');
        const token = await current.getIdTokenResult();
        setProfile((old) => ({ ...old, department: token.claims.department || old.department }));
        setProfileOpen(!localStorage.getItem(`profile:${current.uid}`));
      }
    });
  }, []);

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
        method: 'PUT', headers: { 'Content-Type': 'application/json', ...(user ? { Authorization: `Bearer ${token}` } : { 'X-Demo-User': 'emp-alice' }) },
        body: JSON.stringify({ ...profile, keywords: profile.keywords.split(',').map((word) => word.trim()).filter(Boolean) }),
      });
      if (response.ok) {
        if (user) localStorage.setItem(`profile:${user.uid}`, 'complete');
        setProfileOpen(false);
        setNotice('Profile saved. Your title and keywords do not grant access to restricted company data.');
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
        method: 'POST', headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : demoSession ? { 'X-Demo-User': 'emp-alice' } : {}) },
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
      <div className="workspace"><div className="workspace-mark">N</div><div><strong>NexusHelper</strong><small>Company workspace</small></div></div>
      <div className="nav-label">WORKSPACE</div>
      <nav aria-label="Workspace navigation">
        <button className={`nav-item nav-button ${activeSection === 'ask' ? 'active' : ''}`} onClick={() => navigate('ask')}><MessageSquareText size={17}/> <span className="nav-text">Ask NexusHelper</span> <span className="nav-shortcut">⌘ K</span></button>
        <button className={`nav-item nav-button ${activeSection === 'graph' ? 'active' : ''}`} onClick={() => navigate('graph')}><GitBranch size={17}/> <span className="nav-text">Knowledge graph</span></button>
        <button className={`nav-item nav-button ${activeSection === 'sources' ? 'active' : ''}`} onClick={() => navigate('sources')}><FileText size={17}/> <span className="nav-text">Sources</span></button>
        <button className={`nav-item nav-button ${activeSection === 'people' ? 'active' : ''}`} onClick={() => navigate('people')}><Users size={17}/> <span className="nav-text">People &amp; teams</span></button>
        <button className={`nav-item nav-button ${activeSection === 'download' ? 'active' : ''}`} onClick={() => navigate('download')}><Download size={17}/> <span className="nav-text">Install NexusHelper</span></button>
      </nav>
      <div className="nav-label source-label">YOUR CONTEXT</div>
      <div className="context-card"><div className="context-icon"><Building2 size={15}/></div><div><strong>Build your profile</strong><small>Add your role and team keywords</small></div><button aria-label="Set profile" onClick={() => setProfileOpen(true)} title="Set up your profile"><ArrowUpRight size={15}/></button></div>
      <div className="sidebar-bottom"><div className="secure-note"><ShieldCheck size={15}/><span>Access is based on verified<br/>company membership</span></div>
        {activeUser ? <button className="user-row" onClick={() => { if (user) signOut(auth); else { setDemoSession(false); localStorage.removeItem('nexushelper-demo-session'); setNotice('Local demo session ended.'); } }}><img src={activeUser.photoURL || ''} alt=""/><span><b>{activeUser.displayName || activeUser.email}</b><small>Sign out</small></span><LogOut size={15}/></button> : <button className="signin-small" onClick={login}><KeyRound size={15}/> {firebaseConfigured ? 'Sign in' : 'Start local demo'}</button>}
      </div>
    </aside>

    <main className="main-area">
      <header className="topbar"><div className="topbar-leading"><button className="mobile-menu-toggle" aria-label="Open navigation menu" title="Open navigation menu" onClick={() => setMobileMenuOpen(true)}><Menu size={20}/></button><div className="breadcrumbs"><span>Workspace</span><span className="crumb-slash">/</span><b>{activeSection === 'ask' ? 'Ask NexusHelper' : activeSection === 'graph' ? 'Knowledge graph' : activeSection === 'sources' ? 'Sources' : activeSection === 'people' ? 'People & teams' : activeSection === 'download' ? 'Install NexusHelper' : 'Setup & connections'}</b></div></div><div className="top-actions"><label className="theme-control" title="Choose appearance"><span>THEME</span><select aria-label="Theme" value={theme} onChange={(event) => setTheme(event.target.value)}><option value="dark">Dark</option><option value="light">Light</option><option value="warm">Warm</option></select></label><button className="icon-button setup-tab-icon" aria-label="Setup and connections" title="Setup and connections" onClick={() => navigate('help')}><span aria-hidden="true">N</span></button><div className="top-divider"/>{activeUser ? <button className="avatar-button" onClick={() => setProfileOpen(true)}><img src={activeUser.photoURL || ''} alt="Profile"/></button> : <button className="top-signin" onClick={login}>{firebaseConfigured ? 'Sign in' : 'Try demo'} <ArrowUpRight size={14}/></button>}</div></header>
      <section className={`content ${activeSection !== 'ask' ? 'content-page' : ''}`}>
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
        </> : <CapabilityPage section={activeSection} user={activeUser} onLogin={login} onProfile={() => setProfileOpen(true)} showDetails={showSetupDetails} onToggleDetails={() => setShowSetupDetails((value) => !value)} />}
      </section>
      <footer className="page-footer"><span>NEXUSHELPER <i>·</i> COMPANY KNOWLEDGE</span><span><span className="footer-dot"/> Preview · integrations pending</span></footer>
    </main>
    {profileOpen && <div className="modal-backdrop" onClick={() => setProfileOpen(false)}><section className="profile-modal" onClick={(e) => e.stopPropagation()}><button className="modal-close" onClick={() => setProfileOpen(false)}><X size={17}/></button><div className="modal-mark"><UserRound size={20}/></div><div className="eyebrow">MAKE NEXUSHELPER YOURS</div><h2>Set up your work profile</h2><p className="modal-description">Help connect your questions to the right people and knowledge across NexusHelper.</p>{!authenticated && <div className="signin-callout"><KeyRound size={17}/><span>{firebaseConfigured ? 'Sign in with your company account to continue.' : 'Start a local demo or configure Firebase company sign-in.'}</span><button onClick={() => { setProfileOpen(false); login(); }}>{firebaseConfigured ? 'Sign in' : 'Try demo'}</button></div>}<form onSubmit={submitProfile}><label>YOUR DESIGNATION<input required minLength="2" placeholder="e.g. Human Resources Manager" value={profile.designation} onChange={(e) => setProfile({...profile, designation: e.target.value})}/></label><label>DEPARTMENT<select required value={profile.department} onChange={(e) => setProfile({...profile, department: e.target.value})}><option value="">Select your department</option>{departments.map((dep) => <option key={dep}>{dep}</option>)}</select></label><label>KNOWLEDGE KEYWORDS <span className="optional">OPTIONAL</span><input placeholder="e.g. hiring, onboarding, benefits" value={profile.keywords} onChange={(e) => setProfile({...profile, keywords: e.target.value})}/><small>Keywords help people find expertise. They never grant data access.</small></label><div className="access-note"><ShieldCheck size={16}/><span>Company data access is assigned by your administrator, not by your self-entered title.</span></div><button type="submit" className="save-profile" disabled={!authenticated}>Save profile <Check size={16}/></button></form></section></div>}
  </div>;
}


function CapabilityPage({ section, user, onLogin, onProfile, showDetails, onToggleDetails }) {
  const pages = {
    graph: {
      icon: GitBranch, eyebrow: 'NEXUSHELPER KNOWLEDGE', title: 'Knowledge graph',
      description: 'Explore how services, teams, people, decisions, and evidence connect.',
      status: 'Graph database not connected',
      detail: 'Connect a private FalkorDB instance and load the synthetic NexusHelper schema to enable graph exploration. The graph endpoint and credentials are not configured in this workspace.',
      action: 'View graph setup',
    },
    download: {
      icon: Download, eyebrow: 'NEXUSHELPER FOR DESKTOP', title: 'Get NexusHelper',
      description: 'Use the same NexusHelper workspace from your desktop or browser. Sign-in will open securely in your browser and return you to the app.',
      status: 'Desktop installers are being prepared',
      detail: 'Linux, macOS, and Windows downloads will appear here when signed release builds are available. For now, run the web app locally using the developer setup guide.',
      action: 'View install status',
    },
    sources: {
      icon: FileText, eyebrow: 'KNOWLEDGE SOURCES', title: 'Sources',
      description: 'Bring approved documents, tickets, and conversations into one searchable knowledge space.',
      status: 'No source integrations connected',
      detail: 'Document, ticket, chat, and code-host integrations have not been configured. Connect a source only after identity-based access controls and retention rules are set.',
      action: 'View connection details',
    },
    people: {
      icon: Users, eyebrow: 'YOUR ORGANIZATION', title: 'People & teams',
      description: 'Find team ownership and expertise using verified company profiles and memberships.',
      status: user ? 'Directory database not connected' : 'Sign in to view your directory',
      detail: user ? 'The authenticated directory and administrator-managed team memberships are not connected yet.' : 'Sign in with your company account to view people and teams. A profile title or keyword never grants access to private company records.',
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
    } else if (section !== 'download') onToggleDetails();
  };
  return <div className="capability-page">
    <div className="capability-icon"><Icon size={22}/></div>
    <div className="eyebrow">{page.eyebrow}</div>
    <h1>{page.title}</h1>
      <p className="capability-description">{page.description}</p>
    <div className="connection-card">
      <div className="connection-status-icon"><Activity size={18}/></div>
      <div className="connection-copy"><span className="connection-label">WORKSPACE CONNECTION</span><strong>{page.status}</strong><p>{page.detail}</p></div>
      <span className="status-pill"><span/> Not connected</span>
    </div>
    {section === 'download' && <div className="download-platforms"><article><strong>Linux</strong><span>AppImage · .deb</span><small>Coming soon</small></article><article><strong>macOS</strong><span>Apple silicon · Intel</span><small>Coming soon</small></article><article><strong>Windows</strong><span>x64 installer</span><small>Coming soon</small></article></div>}
    {showDetails && <div className="setup-detail"><strong>What you’ll need</strong><p>{section === 'graph' ? 'A private FalkorDB endpoint, credentials stored outside the repository, and the NexusHelper graph schema.' : section === 'sources' ? 'An approved connector, its OAuth/API credentials, and an access policy matching the source system.' : section === 'download' ? 'Release signing, platform packaging, and a published download endpoint. The app will use browser-based company sign-in and connect to the shared NexusHelper service.' : 'Firebase Authentication settings and an administrator-managed directory/membership source.'}</p></div>}
    {section !== 'download' && <div className="capability-actions"><button className="primary-action" onClick={handleAction}>{page.action}<ArrowUpRight size={15}/></button><span>Company data stays unavailable until its connection is configured.</span></div>}
  </div>;
}

createRoot(document.getElementById('root')).render(<App/>);
