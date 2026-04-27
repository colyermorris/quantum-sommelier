/* Landing page — hero + trending (live from /api/v1/trending) */

const HEADLINES = window.HERO_HEADLINES;
const TRENDING_FALLBACK = window.TRENDING_REPOS;

function Landing({ onScan, tweaks, rateLimitMsg }) {
  const [headlineIdx, setHeadlineIdx] = React.useState(() => Math.floor(Math.random() * HEADLINES.length));
  const [url, setUrl] = React.useState('');
  const [err, setErr] = React.useState('');
  const [trending, setTrending] = React.useState(TRENDING_FALLBACK);
  const headline = tweaks.heroHeadline === 'random'
    ? HEADLINES[headlineIdx]
    : HEADLINES[Number(tweaks.heroHeadline)] || HEADLINES[0];

  React.useEffect(() => {
    let alive = true;
    window.QS_API.trending().then((items) => {
      if (alive && Array.isArray(items) && items.length) setTrending(items);
    }).catch(() => {});
    return () => { alive = false; };
  }, []);

  const validate = (u) => {
    const trimmed = u.trim();
    if (!trimmed) { setErr("Paste a repo URL, or pick one below."); return null; }
    const short = trimmed.match(/^([\w.-]+)\/([\w.-]+)$/);
    const full = trimmed.match(/^https?:\/\/github\.com\/([\w.-]+)\/([\w.-]+?)(?:\.git)?(?:\/.*)?$/i);
    if (!short && !full) {
      setErr("Not a vineyard we recognize. That URL doesn't point to a public GitHub repo.");
      return null;
    }
    const m = short || full;
    return `${m[1]}/${m[2]}`;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const slug = validate(url);
    if (!slug) return;
    onScan(slug);
  };

  const handleQuickScan = (slug) => { setUrl(slug); setErr(''); onScan(slug); };

  return (
    <div className="landing">
      <section className="hero">
        <div className="issue-marker">
          <span className="issue-num">ISSUE Nº 0027</span>
          <span className="issue-sep">·</span>
          <span className="issue-date">SPRING 2026</span>
          <span className="issue-sep">·</span>
          <span className="issue-price">PQ-SCREENING, ONE REPO AT A TIME</span>
        </div>

        <h1 className="hero-headline">
          <span className="hero-line-1">{headline.main}</span>
          <span className="hero-line-2">
            <em>{headline.sub}</em>
          </span>
        </h1>

        <p className="hero-dek">
          Post-quantum readiness screening for public GitHub repos. Real analysis. Committed sommelier.
        </p>

        <form className="hero-form" onSubmit={handleSubmit}>
          <div className={`url-field ${err || rateLimitMsg ? 'url-field--err' : ''}`}>
            <span className="url-prefix">github.com/</span>
            <input
              type="text"
              className="url-input"
              placeholder="owner/repo or paste full URL"
              value={url}
              onChange={(e) => {
                let v = e.target.value;
                const full = v.match(/^(?:https?:\/\/)?(?:www\.)?github\.com\/([\w.-]+\/[\w.-]+?)(?:\.git)?(?:\/.*)?$/i);
                if (full) v = full[1];
                setUrl(v);
                setErr('');
              }}
              spellCheck={false}
              autoComplete="off"
            />
            <button type="submit" className="btn-taste">
              <span>Taste This</span>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden>
                <path d="M2 7h10M8 3l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>
          {err ? <p className="url-err">{err}</p> : rateLimitMsg ? (
            <p className="url-err">{rateLimitMsg}</p>
          ) : (
            <p className="url-note">Public GitHub repos only. We clone, scan, delete. We never install your dependencies.</p>
          )}
        </form>
      </section>

      <section className="trending">
        <header className="trending-head">
          <span className="uppercase-label">Rising on GitHub</span>
          <span className="trending-kicker">Fresh repos, tastable in one click.</span>
        </header>
        <ul className="trending-list">
          {trending.map((repo, i) => (
            <li
              key={repo.name}
              className="trending-row"
              onClick={() => handleQuickScan(repo.name)}
              role="button"
              tabIndex="0"
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleQuickScan(repo.name); }}
            >
              <span className="trending-rank">{String(i+1).padStart(2, '0')}</span>
              <span className="trending-name">{repo.name}</span>
              <span className="trending-blurb">{repo.blurb}</span>
              <span className="trending-lang">{repo.lang}</span>
              <span className="trending-stars">
                <svg width="11" height="11" viewBox="0 0 12 12" aria-hidden>
                  <path d="M6 1l1.5 3.2 3.5.4-2.6 2.4.7 3.5L6 8.8 2.9 10.5l.7-3.5L1 4.6l3.5-.4L6 1z" fill="currentColor" opacity="0.6"/>
                </svg>
                {repo.stars.toLocaleString()}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="faq">
        <div className="faq-row">
          <div>
            <div className="uppercase-label">What does this scan</div>
            <p>Dependency manifests, source code, configs, and committed secrets in Python and JavaScript repos.</p>
          </div>
          <div>
            <div className="uppercase-label">Is it real</div>
            <p>Real scanner, real tree-sitter AST, real Claude Haiku. The sommelier adds personality.</p>
          </div>
          <div>
            <div className="uppercase-label">Do you store my code</div>
            <p>No. We clone, scan, delete. Nothing persists.</p>
          </div>
        </div>
      </section>
    </div>
  );
}

window.Landing = Landing;
