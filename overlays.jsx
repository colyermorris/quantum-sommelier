/* Vineyard drawer, Cork modal, Tweaks panel */

function VineyardDrawer({ tasting, openId, onClose, onSelectFinding }) {
  const [activeId, setActiveId] = React.useState(openId);
  React.useEffect(() => { if (openId) setActiveId(openId); }, [openId]);

  React.useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!tasting) return null;
  const findings = tasting.findings;
  const active = findings.find(f => f.id === activeId) || findings[0];

  return (
    <div className="drawer-overlay" onClick={onClose}>
      <aside className="vineyard-drawer" onClick={(e) => e.stopPropagation()}>
        <header className="vd-header">
          <div>
            <div className="uppercase-label">Vineyard Notes</div>
            <h3 className="vd-title display">The paperwork behind the prose.</h3>
          </div>
          <button className="vd-close" onClick={onClose} aria-label="Close">×</button>
        </header>

        <nav className="vd-nav">
          {findings.map(f => (
            <button
              key={f.id}
              className={`vd-nav-item ${active.id === f.id ? 'is-active' : ''}`}
              onClick={() => setActiveId(f.id)}
            >
              <span className={`sev-chip sev-${f.severity}`} />
              <span className="vd-nav-id mono">{f.id}</span>
              <span className="vd-nav-short">{f.short}</span>
            </button>
          ))}
        </nav>

        <div className="vd-body">
          <FindingDetail f={active} />
        </div>
      </aside>
    </div>
  );
}

function CorkModal({ tasting, jobId, onClose }) {
  const [copied, setCopied] = React.useState(false);
  const [imgLoaded, setImgLoaded] = React.useState(false);
  const [imgFailed, setImgFailed] = React.useState(false);
  React.useEffect(() => {
    const handler = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [onClose]);

  if (!tasting) return null;
  const displayUrl = `${(window.location.host || 'quantum-sommelier.app')}/tasting/${jobId || (tasting.repo.owner + '-' + tasting.repo.name)}`;
  const pngHref = jobId ? `/api/v1/tastings/${jobId}/cork.png` : '#';
  const svgHref = jobId ? `/api/v1/tastings/${jobId}/cork.svg` : '#';

  const copyLink = () => {
    navigator.clipboard?.writeText(window.location.origin + '/tasting/' + (jobId || ''));
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="cork-modal" onClick={(e) => e.stopPropagation()}>
        <header className="cork-modal-head">
          <div>
            <div className="uppercase-label">The Cork</div>
            <h3 className="display">Share this tasting.</h3>
          </div>
          <button className="vd-close" onClick={onClose} aria-label="Close">×</button>
        </header>

        <div className="cork-modal-body">
          <div className="cork-stage">
            {jobId && !imgFailed ? (
              <img
                src={pngHref}
                alt="Tasting card preview"
                className={`cork-preview-img ${imgLoaded ? 'is-loaded' : ''}`}
                onLoad={() => setImgLoaded(true)}
                onError={() => setImgFailed(true)}
              />
            ) : (
              <CorkCard tasting={tasting} size="large" />
            )}
          </div>

          <div className="cork-controls">
            <div className="cork-preview-label uppercase-label">1200 × 720 · OG image preview</div>
            <p className="cork-desc">
              The card that unfurls when you drop the link into a Slack or a post.
              Pull-quote selected from <em>The Finish</em>.
            </p>

            <div className="cork-url-box">
              <span className="mono cork-url">{displayUrl}</span>
            </div>

            <div className="cork-btns">
              <a className="btn-primary" href={pngHref} download={`cork-${jobId || 'tasting'}.png`}>
                <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden><path d="M7 1v9m0 0L3 6m4 4l4-4M2 13h10" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round"/></svg>
                Download PNG
              </a>
              <button className="btn-outline" onClick={copyLink}>
                {copied ? 'Copied' : 'Copy link'}
              </button>
              <a className="btn-outline" href={svgHref} download={`cork-${jobId || 'tasting'}.svg`}>
                Download SVG
              </a>
            </div>

            <div className="cork-social">
              <div className="uppercase-label">Unfurls on</div>
              <div className="cork-social-row">
                <span>Slack</span><span className="dot">·</span>
                <span>LinkedIn</span><span className="dot">·</span>
                <span>X</span><span className="dot">·</span>
                <span>Bluesky</span><span className="dot">·</span>
                <span>Discord</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function TweaksPanel({ tweaks, setTweaks, onClose }) {
  const Option = ({ group, value, label }) => (
    <button
      className={`tw-opt ${tweaks[group] === value ? 'is-on' : ''}`}
      onClick={() => setTweaks({ ...tweaks, [group]: value })}
    >{label}</button>
  );

  return (
    <div className="tweaks-panel">
      <header className="tw-head">
        <div className="display tw-title">Tweaks</div>
        <button className="vd-close" onClick={onClose} aria-label="Close">×</button>
      </header>
      <div className="tw-body">
        <div className="tw-group">
          <div className="uppercase-label">Section header ornament</div>
          <div className="tw-row">
            <Option group="ornament" value="dot" label="Dot" />
            <Option group="ornament" value="cellar-key" label="Cellar key" />
            <Option group="ornament" value="ampersand" label="&amp;" />
            <Option group="ornament" value="double-rule" label="Double rule" />
          </div>
        </div>

        <div className="tw-group">
          <div className="uppercase-label">Score card</div>
          <div className="tw-row">
            <Option group="scoreChart" value="bars" label="Bars" />
            <Option group="scoreChart" value="radar" label="Radar" />
          </div>
        </div>

        <div className="tw-group">
          <div className="uppercase-label">Letter grade treatment</div>
          <div className="tw-row">
            <Option group="gradeVariant" value="pill" label="Pill" />
            <Option group="gradeVariant" value="block" label="Block" />
            <Option group="gradeVariant" value="wax-seal" label="Wax seal" />
          </div>
        </div>

        <div className="tw-group">
          <div className="uppercase-label">Wordmark</div>
          <div className="tw-row">
            <Option group="wordmark" value="default" label="Default" />
            <Option group="wordmark" value="serif-condensed" label="Condensed" />
            <Option group="wordmark" value="wonky" label="Wonky display" />
            <Option group="wordmark" value="script" label="Italic script" />
          </div>
        </div>

        <div className="tw-group">
          <div className="uppercase-label">Color temperature</div>
          <div className="tw-row">
            <Option group="temp" value="default" label="Default" />
            <Option group="temp" value="warmer" label="Warmer" />
            <Option group="temp" value="cooler" label="Cooler" />
          </div>
        </div>

        <div className="tw-group">
          <div className="uppercase-label">Hero headline</div>
          <div className="tw-row">
            <Option group="heroHeadline" value="random" label="Random" />
            <Option group="heroHeadline" value="0" label="Paste a repo" />
            <Option group="heroHeadline" value="1" label="What's your code drinking" />
            <Option group="heroHeadline" value="2" label="Taste the terroir" />
            <Option group="heroHeadline" value="3" label="Nose the deps" />
          </div>
        </div>
      </div>
    </div>
  );
}

window.VineyardDrawer = VineyardDrawer;
window.CorkModal = CorkModal;
window.TweaksPanel = TweaksPanel;
