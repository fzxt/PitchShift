import { useEffect, useMemo, useRef, useState } from 'react';
import type { Pitcher, Report, WindowSize } from './types';
import { count, date, strength } from './format';
import { Methodology } from './components/Methodology';
import { ScoutingCard } from './components/ScoutingCard';

const REPO = 'https://github.com/fzxt/PitchShift';
function readSaved(): Set<string> { try { const ids: unknown = JSON.parse(localStorage.getItem('pitchshift-watchlist') || '[]'); return new Set(Array.isArray(ids) ? ids.map(String) : []); } catch { return new Set(); } }
function initialSelection() { const hash = new URLSearchParams(location.hash.slice(1)); return { id: hash.get('pitcher'), window: (hash.get('window') === '200' ? '200' : '100') as WindowSize }; }
function validateReport(raw: unknown): Report {
  const report = raw as Report;
  if (report?.schemaVersion !== 1 || !['100', '200'].every(w => Array.isArray(report.windows?.[w as WindowSize]?.pitchers) && report.windows[w as WindowSize].pitchers.length > 0)) throw new Error('Snapshot is missing analyzed windows');
  return report;
}
function Overview({ report, pitchers, window }: { report: Report; pitchers: Pitcher[]; window: WindowSize }) {
  const stats = [[count(pitchers.length), 'Pitchers tracked', 'Selected research cohort'], [count(pitchers.filter(p => p.status === 'review').length), 'Worth a closer look', 'At least one change signal'], [window, 'Recent pitches', 'Compared with the prior 500'], [count(report.source.pitchCount || 0), 'Pitches in snapshot', 'Public Statcast data']];
  return <section className="overview-strip" aria-label="Dataset summary">{stats.map(([n, label, detail]) => <div className="overview-stat" key={label}><strong>{n}</strong><span><b>{label}</b>{detail}</span></div>)}</section>;
}
export default function App() {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [selection, setSelection] = useState(initialSelection);
  const [query, setQuery] = useState('');
  const [team, setTeam] = useState('all');
  const [status, setStatus] = useState('all');
  const [saved, setSaved] = useState(readSaved);
  const [methodOpen, setMethodOpen] = useState(false);
  const [toast, setToast] = useState('');
  const search = useRef<HTMLInputElement>(null);
  const pitchers = report?.windows[selection.window].pitchers ?? [];
  const sorted = useMemo(() => [...pitchers].sort((a, b) => strength(b) - strength(a) || a.name.localeCompare(b.name)), [pitchers]);
  const selected = pitchers.find(p => String(p.id) === selection.id) || pitchers.find(p => String(p.id) === '592332' && p.alerts.length > 0) || sorted[0];
  const visible = sorted.filter(p => p.name.toLowerCase().includes(query.toLowerCase().trim()) && (team === 'all' || p.team === team) && (status === 'all' || (status === 'saved' ? saved.has(String(p.id)) : p.status === status)));
  const teams = [...new Set(pitchers.map(p => p.team).filter(Boolean))].sort();
  useEffect(() => {
    const controller = new AbortController(); setError(false);
    fetch(`${import.meta.env.BASE_URL}data/pitchshift.json`, { signal: controller.signal }).then(res => { if (!res.ok) throw new Error('Snapshot unavailable'); return res.json(); }).then(raw => setReport(validateReport(raw))).catch(err => { if (err.name !== 'AbortError') setError(true); });
    return () => controller.abort();
  }, [attempt]);
  useEffect(() => { if (!toast) return; const timer = setTimeout(() => setToast(''), 3500); return () => clearTimeout(timer); }, [toast]);
  useEffect(() => { const keydown = (e: KeyboardEvent) => { if (e.key === '/' && !['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName || '') && !methodOpen) { e.preventDefault(); search.current?.focus(); } }; document.addEventListener('keydown', keydown); return () => document.removeEventListener('keydown', keydown); }, [methodOpen]);
  useEffect(() => { const hashChange = () => setSelection(initialSelection()); window.addEventListener('hashchange', hashChange); return () => window.removeEventListener('hashchange', hashChange); }, []);
  function select(id: string, windowSize = selection.window) { setSelection({ id, window: windowSize }); history.replaceState(null, '', `#pitcher=${encodeURIComponent(id)}&window=${windowSize}`); }
  function toggleSave() {
    const id = String(selected.id), next = new Set(saved); next.has(id) ? next.delete(id) : next.add(id); setSaved(next);
    let message = next.has(id) ? `${selected.name} added to your watchlist on this device.` : `${selected.name} removed from your watchlist.`;
    try { localStorage.setItem('pitchshift-watchlist', JSON.stringify([...next])); } catch { message = 'Saved for this session. Browser storage is unavailable.'; }
    setToast(message);
  }
  const dataEnd = report?.source.dataEnd || [...pitchers].map(p => p.recentEnd).sort().at(-1);
  return <><a className="skip-link" href="#main">Skip to scouting report</a>
    <header className="masthead"><a className="brand" href="./" aria-label="PitchShift home"><img src={`${import.meta.env.BASE_URL}favicon.svg`} width="32" height="32" alt="" /><span>PitchShift<span className="brand-dot">.</span></span></a><div className="brand-context">BASEBALL RESEARCH <span>/</span> ADVANCE SCOUTING</div><button className="text-button" onClick={() => setMethodOpen(true)}>Methodology <span aria-hidden="true">↗</span></button></header>
    <main id="main"><section className="page-heading"><div><div className="eyebrow"><span className="live-dot" /> PITCHER CHANGE DETECTOR</div><h1>A closer look at<br className="mobile-break" /> what’s changed.</h1><p>Recent pitch characteristics. A historical baseline. A reason to take another look.</p></div><div className="snapshot-meta"><span className="eyebrow">STATCAST SNAPSHOT</span><strong>{report ? `Through ${date(dataEnd, true)}` : error ? 'Data unavailable' : 'Loading data…'}</strong>{report && <small>2026 season · {pitchers.length} selected pitchers</small>}</div></section>
      {report && <Overview report={report} pitchers={pitchers} window={selection.window} />}{report?.source.notice && <div className="data-notice">{report.source.notice}</div>}
      <section className="workspace"><aside className="pitcher-browser" aria-label="Pitcher selection"><div className="browser-title"><h2>The watchboard</h2><span className="count-pill">{report ? visible.length : '—'}</span></div><label className="search-wrap"><span aria-hidden="true">⌕</span><input ref={search} type="search" placeholder="Find a pitcher…" aria-label="Search pitchers" autoComplete="off" value={query} onChange={e => setQuery(e.target.value)} /><kbd>/</kbd></label><div className="browser-filters"><label className="sr-only" htmlFor="team">Filter team</label><select id="team" value={team} onChange={e => setTeam(e.target.value)}><option value="all">All teams</option>{teams.map(t => <option key={t} value={t}>{t}</option>)}</select><label className="sr-only" htmlFor="status">Filter signals</label><select id="status" value={status} onChange={e => setStatus(e.target.value)}><option value="all">All pitchers</option><option value="review">With signals</option><option value="saved">My watchlist</option></select></div><div className="list-heading"><span>PITCHER</span><span>SIGNALS</span></div><div className="pitcher-list" role="list">
      {visible.map(p => <div role="listitem" key={p.id}><button className={`pitcher-row ${p.id === selected?.id ? 'active' : ''}`} aria-pressed={p.id === selected?.id} onClick={() => select(String(p.id))}><span className="avatar">{p.name.split(/\s+/).map(n => n[0]).slice(0, 2).join('')}</span><span><span className="pitcher-row-name">{p.name}</span><span className="pitcher-row-sub" style={{ display: 'block' }}>{p.team || 'MLB'} · {p.throws || '?'}HP{saved.has(String(p.id)) ? ' · ★' : ''}</span></span><span className={`signal-count ${p.alerts.length ? '' : 'zero'}`} aria-label={`${p.alerts.length} change signals`}>{p.alerts.length || '—'}</span></button></div>)}
      {report && !visible.length && <div className="empty-state"><h3>No pitchers match</h3><p>Try another search or filter.</p></div>}</div><div className="browser-foot">Sorted by strongest detected change.<br />Signals are prompts for review.</div></aside>
      {error ? <div className="error-state" role="alert"><h2>The data could not be loaded.</h2><p>Check your connection and reload. For local development, run <code>npm run dev</code>.</p><button onClick={() => setAttempt(n => n + 1)}>Try again</button></div> : report && selected ? <ScoutingCard key={selected.id} pitcher={selected} window={selection.window} onWindow={w => select(String(selected.id), w)} saved={saved.has(String(selected.id))} onSave={toggleSave} onMethod={() => setMethodOpen(true)} generatedAt={report.generatedAt} onToast={setToast} /> : <div className="loading-state" role="status"><div className="loading-ball" /><h2>Preparing the scouting report</h2><p>Loading the latest analyzed Statcast snapshot.</p></div>}
      </section><footer><p><strong>PitchShift</strong> <span>Independent baseball research. Built by Fahad Ahmad.</span></p><div><a href="https://baseballsavant.mlb.com/" target="_blank" rel="noreferrer">Data: Baseball Savant ↗</a><a href={REPO} target="_blank" rel="noreferrer">Source & research ↗</a></div></footer>
    </main><Methodology open={methodOpen} onClose={() => setMethodOpen(false)} />{toast && <div className="toast" role="status">{toast}</div>}
  </>;
}
