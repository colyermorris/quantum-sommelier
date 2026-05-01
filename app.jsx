/* Quantum Sommelier — bundle entry point.
   esbuild reads this and produces a single minified app.js. */

import React from 'react';
import { createRoot } from 'react-dom/client';

import { Landing } from './landing.jsx';
import { Scanning } from './scanning.jsx';
import { TastingResult } from './tasting.jsx';
import { VineyardDrawer, CorkModal, TweaksPanel } from './overlays.jsx';
import { QS_API } from './api.js';
import { normalizeTasting } from './edu.js';

function SiteHeader({ onHome, view }) {
  return (
    <div className="site site--topbar">
      <nav className="site-nav" data-view={view} aria-label="Primary">
        <a className="nav-wordmark" onClick={(e) => { e.preventDefault(); onHome(); }} href="#home">
          <svg className="nav-glyph" viewBox="0 0 28 32" width="22" height="26" aria-hidden>
            <path d="M5 3 Q5 15 14 15 Q23 15 23 3 Z" fill="var(--color-oxblood)" opacity="0.18"/>
            <path d="M5 3 Q5 15 14 15 Q23 15 23 3 Z" fill="none" stroke="var(--color-oxblood)" strokeWidth="1.2" strokeLinejoin="round"/>
            <path d="M6.5 5 Q10 6.5 14 6.5 Q18 6.5 21.5 5" fill="none" stroke="var(--color-oxblood)" strokeWidth="0.9" opacity="0.7"/>
            <text x="14" y="12" textAnchor="middle" fontSize="6.2" fontFamily="ui-monospace, 'JetBrains Mono', monospace" fontWeight="600" fill="var(--color-oxblood)" letterSpacing="-0.3">&lt;/&gt;</text>
            <line x1="14" y1="15" x2="14" y2="27" stroke="var(--color-ink)" strokeWidth="1.1" strokeLinecap="round"/>
            <line x1="8" y1="29" x2="20" y2="29" stroke="var(--color-ink)" strokeWidth="1.4" strokeLinecap="round"/>
            <ellipse cx="14" cy="29" rx="6" ry="1.2" fill="none" stroke="var(--color-ink)" strokeWidth="0.4" opacity="0.35"/>
          </svg>
          <span>Quantum Sommelier</span>
        </a>
        <div className="nav-meta">
          <span className="issue">VOL I · NO. 04</span>
          <span className="dot" aria-hidden />
          <span>April 2026</span>
          <span className="dot" aria-hidden />
          <span>qs-rubric-1.0.0</span>
        </div>
      </nav>
    </div>
  );
}

function SiteFooter() {
  return (
    <div className="site">
      <footer className="site-footer">
        <div className="footer-mark">A Morris Mediocre Masterpiece.</div>
        <div className="footer-meta">
          <div>Rubric qs-rubric-1.0.0 · Vintage April 2026</div>
          <div>Tastings are opinions, not audits.</div>
        </div>
      </footer>
    </div>
  );
}

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "ornament": "cellar-key",
  "scoreChart": "bars",
  "gradeVariant": "pill",
  "wordmark": "wonky",
  "temp": "default",
  "heroHeadline": "random"
}/*EDITMODE-END*/;

const STORAGE_KEY = 'quantum-sommelier-state-v2';

function App() {
  const persisted = React.useMemo(() => {
    try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); } catch { return {}; }
  }, []);
  const [tweaks, setTweaks] = React.useState({ ...TWEAK_DEFAULTS, ...(persisted.tweaks || {}) });
  const [tweaksOpen, setTweaksOpen] = React.useState(false);
  const [view, setView] = React.useState('landing'); // landing | scanning | tasting
  const [repoSlug, setRepoSlug] = React.useState('');
  const [jobId, setJobId] = React.useState(null);
  const [tasting, setTasting] = React.useState(null);
  const [rateLimitMsg, setRateLimitMsg] = React.useState(null);
  const [drawerFinding, setDrawerFinding] = React.useState(null);
  const [corkOpen, setCorkOpen] = React.useState(false);

  React.useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ tweaks }));
  }, [tweaks]);

  React.useEffect(() => {
    document.body.dataset.temp = tweaks.temp;
    document.body.dataset.wordmark = tweaks.wordmark;
  }, [tweaks.temp, tweaks.wordmark]);

  React.useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === '__activate_edit_mode') setTweaksOpen(true);
      if (e.data?.type === '__deactivate_edit_mode') setTweaksOpen(false);
    };
    window.addEventListener('message', handler);
    window.parent.postMessage({ type: '__edit_mode_available' }, '*');
    return () => window.removeEventListener('message', handler);
  }, []);

  const startScan = async (slugOrUrl) => {
    setRateLimitMsg(null);
    const repoUrl = /^https?:\/\//.test(slugOrUrl)
      ? slugOrUrl
      : `https://github.com/${slugOrUrl}`;
    setRepoSlug(slugOrUrl);
    setTasting(null);
    setView('scanning');
    window.scrollTo({ top: 0, behavior: 'instant' });
    try {
      const { job_id } = await QS_API.startTasting(repoUrl);
      setJobId(job_id);
    } catch (err) {
      if (err.status === 429) {
        setRateLimitMsg(err.body?.error?.message || "The cellar is shut — too many tastings this hour.");
        setView('landing');
      } else {
        setRateLimitMsg(err.body?.detail?.message || err.message || 'Could not start tasting.');
        setView('landing');
      }
    }
  };

  const finishScan = (apiTasting) => {
    setTasting(normalizeTasting(apiTasting));
    setView('tasting');
    window.scrollTo({ top: 0, behavior: 'instant' });
  };
  const goHome = () => {
    setView('landing');
    setJobId(null);
    setTasting(null);
    setDrawerFinding(null);
    setCorkOpen(false);
  };

  return (
    <>
      <a className="skip-link" href="#main">Skip to main content</a>
      <SiteHeader onHome={goHome} view={view} />
      {view === 'landing' && <Landing onScan={startScan} tweaks={tweaks} rateLimitMsg={rateLimitMsg} />}
      {view === 'scanning' && (
        <Scanning
          repoSlug={repoSlug}
          jobId={jobId}
          onDone={finishScan}
          onCancel={goHome}
          onError={(msg) => { setRateLimitMsg(msg); setView('landing'); }}
          tweaks={tweaks}
        />
      )}
      {view === 'tasting' && tasting && (
        <TastingResult
          tasting={tasting}
          jobId={jobId}
          tweaks={tweaks}
          onBack={goHome}
          onFindingClick={(id) => setDrawerFinding(id || tasting.findings[0]?.id)}
          openVineyard={() => setDrawerFinding(tasting.findings[0]?.id)}
          onOpenCork={() => setCorkOpen(true)}
        />
      )}
      {view === 'tasting' && tasting && drawerFinding && (
        <VineyardDrawer tasting={tasting} openId={drawerFinding} onClose={() => setDrawerFinding(null)} />
      )}
      {view === 'tasting' && tasting && corkOpen && (
        <CorkModal tasting={tasting} jobId={jobId} tweaks={tweaks} onClose={() => setCorkOpen(false)} />
      )}
      <SiteFooter />
      {tweaksOpen && <TweaksPanel tweaks={tweaks} setTweaks={(next) => {
        const changed = {};
        Object.keys(next).forEach(k => { if (next[k] !== tweaks[k]) changed[k] = next[k]; });
        setTweaks(next);
        if (Object.keys(changed).length) {
          window.parent.postMessage({ type: '__edit_mode_set_keys', edits: changed }, '*');
        }
      }} onClose={() => setTweaksOpen(false)} />}
    </>
  );
}

createRoot(document.getElementById('root')).render(<App />);
