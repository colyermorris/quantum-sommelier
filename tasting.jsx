/* Tasting result — the main editorial magazine layout */

import React from 'react';

function hydrateText(text, findings, onFindingClick) {
  // Replace {{ref:ID}} with <a> and {{grade}} pill handled by caller
  const parts = text.split(/(\{\{ref:[^}]+\}\}|\{\{grade\}\}|`[^`]+`)/g);
  return parts.map((p, i) => {
    const refMatch = p.match(/^\{\{ref:([^}]+)\}\}$/);
    if (refMatch) {
      const f = findings.find((x) => x.id === refMatch[1]);
      if (!f) return <span key={i}>[unknown]</span>;
      return (
        <a
          key={i}
          className={`finding-ref sev-${f.severity}`}
          onClick={(e) => { e.preventDefault(); onFindingClick(f.id); }}
          href={`#${f.id}`}
          data-tooltip={`${f.file}:${f.lines} — ${f.short}`}
        >{f.short}</a>
      );
    }
    if (p === '{{grade}}') return null; // handled in parent with pill
    const codeMatch = p.match(/^`([^`]+)`$/);
    if (codeMatch) return <code key={i} className="inline-code">{codeMatch[1]}</code>;
    return <React.Fragment key={i}>{p}</React.Fragment>;
  });
}

function SectionHeader({ label, ornament }) {
  // Ornament variants: "dot", "cellar-key", "ampersand", "double-rule"
  return (
    <div className={`section-header orn-${ornament}`}>
      <h2 className="section-label">{label}</h2>
      <div className="section-divider">
        {ornament === 'dot' && (<>
          <span className="div-rule" /><span className="div-dot" /><span className="div-rule" />
        </>)}
        {ornament === 'cellar-key' && (<>
          <span className="div-rule" />
          <svg width="22" height="10" viewBox="0 0 22 10" aria-hidden className="div-orn">
            <circle cx="4" cy="5" r="3" stroke="currentColor" strokeWidth="1" fill="none"/>
            <line x1="7" y1="5" x2="18" y2="5" stroke="currentColor" strokeWidth="1"/>
            <line x1="14" y1="5" x2="14" y2="8" stroke="currentColor" strokeWidth="1"/>
            <line x1="17" y1="5" x2="17" y2="8" stroke="currentColor" strokeWidth="1"/>
          </svg>
          <span className="div-rule" />
        </>)}
        {ornament === 'ampersand' && (<>
          <span className="div-rule" />
          <span className="div-amp display">&amp;</span>
          <span className="div-rule" />
        </>)}
        {ornament === 'double-rule' && (<>
          <span className="div-double" />
        </>)}
      </div>
    </div>
  );
}

function GradePill({ grade, variant }) {
  // variant: "pill" | "block" | "wax-seal"
  if (variant === 'block') return (
    <span className={`grade-inline grade-block grade-${grade}`}>{grade}</span>
  );
  if (variant === 'wax-seal') return (
    <span className={`grade-inline grade-wax grade-${grade}`}>
      <svg viewBox="0 0 60 60" width="44" height="44" aria-hidden className="wax-svg">
        <defs>
          <radialGradient id="wax-grad" cx="35%" cy="30%">
            <stop offset="0%" stopColor="#9B4048"/>
            <stop offset="70%" stopColor="#722F37"/>
            <stop offset="100%" stopColor="#4A1C2B"/>
          </radialGradient>
        </defs>
        <path d="M30 4 L38 10 L47 8 L49 17 L56 22 L52 30 L56 38 L49 43 L47 52 L38 50 L30 56 L22 50 L13 52 L11 43 L4 38 L8 30 L4 22 L11 17 L13 8 L22 10 Z" fill="url(#wax-grad)"/>
      </svg>
      <span className="wax-letter">{grade}</span>
    </span>
  );
  return <span className={`grade-inline grade-pill grade-${grade}`}>{grade}</span>;
}

function TastingProse({ text, findings, onFindingClick, grade, gradeVariant }) {
  // Replace {{grade}} specially — split on it
  const withGrade = text.split('{{grade}}');
  return (
    <p>
      {withGrade.map((chunk, i) => (
        <React.Fragment key={i}>
          {hydrateText(chunk, findings, onFindingClick)}
          {i < withGrade.length - 1 && <GradePill grade={grade} variant={gradeVariant} />}
        </React.Fragment>
      ))}
    </p>
  );
}

export function TastingResult({ tasting, jobId, onBack, onFindingClick, openVineyard, onOpenCork, tweaks }) {
  const findings = tasting.findings;
  const axes = tasting.score.axes;

  return (
    <main id="main"><article className="tasting-article">
      {/* Masthead — repo label + meta */}
      <header className="tasting-masthead">
        <button className="back-link" onClick={onBack}>
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden>
            <path d="M7 2L3 6l4 4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          Back to the list
        </button>
        <div className="masthead-rule" />
        <div className="masthead-center">
          <div className="masthead-kicker">A TASTING NOTE</div>
          <h1 className="masthead-title mono">{tasting.repo.owner}/{tasting.repo.name}</h1>
          <div className="masthead-meta">
            <span>{tasting.repo.ref} @ <span className="mono">{tasting.repo.commit_sha}</span></span>
            <span className="sep">·</span>
            <span>{tasting.repo.language}</span>
            <span className="sep">·</span>
            <span>★ {tasting.repo.stars.toLocaleString()}</span>
            <span className="sep">·</span>
            <span>Tasted {tasting.scanned_at}</span>
          </div>
        </div>
      </header>

      {tasting._synthetic && (
        <div className="synth-banner">
          <span className="synth-badge">DEMO</span>
          <span className="synth-text">
            <strong>Synthetic tasting.</strong> The scanner isn't wired up in this prototype. Findings borrowed from a similar vintage.
          </span>
        </div>
      )}

      {/* Big grade + headline block — editorial cover */}
      <section className="cover-block">
        <div className="cover-left">
          <div className="uppercase-label">Quantum readiness</div>
          <div className={`cover-grade grade-${tasting.score.letter_grade}`}>
            {tasting.score.letter_grade}
          </div>
          <div className="cover-rubric mono">{tasting.score.rubric_version}</div>
        </div>
        <div className="cover-right">
          <div className="uppercase-label">The sommelier's headline</div>
          <h2 className="cover-headline">
            <em>{tasting.score.headline}</em>
          </h2>
          <blockquote className="cover-pull">
            <span className="pull-mark">“</span>
            {tasting.pull_quote}
            <span className="pull-mark">”</span>
          </blockquote>
          <div className="sommelier-byline">The Sommelier, tasting notes filed {tasting.scanned_at}</div>
          <div className="drink-window">
            <span className="drink-window-label">DRINK</span>
            <span className="drink-window-text">{
              {'A': 'now, and with smugness, indefinitely',
               'B': 'now, or within three release cycles',
               'C': 'after a stiff decant and a rewrite',
               'D': 'only under supervision',
               'F': 'do not drink. contact the vineyard.'}[tasting.score.letter_grade] || 'consult the cellar log'
            }</span>
          </div>
        </div>
      </section>

      {/* Main layout — prose on the left, stats on the right */}
      <div className="tasting-grid">
        <div className="tasting-main">
          <section className="tasting-section" style={{ animationDelay: '0ms' }}>
            <SectionHeader label="The Nose" ornament={tweaks.ornament} />
            <div className="tasting-prose drop-cap">
              {tasting.nose.prose.map((p, i) => (
                <p key={i}>{hydrateText(p, findings, onFindingClick)}</p>
              ))}
            </div>
          </section>

          <section className="tasting-section" style={{ animationDelay: '200ms' }}>
            <SectionHeader label="The Palate" ornament={tweaks.ornament} />
            <div className="tasting-prose">
              {tasting.palate.paragraphs.map((p, i) => (
                <p key={i}>{hydrateText(p, findings, onFindingClick)}</p>
              ))}
            </div>
          </section>

          <section className="tasting-section" style={{ animationDelay: '400ms' }}>
            <SectionHeader label="The Finish" ornament={tweaks.ornament} />
            <div className="tasting-prose tasting-prose--finish">
              <TastingProse
                text={tasting.finish.prose}
                findings={findings}
                onFindingClick={onFindingClick}
                grade={tasting.score.letter_grade}
                gradeVariant={tweaks.gradeVariant}
              />
            </div>
          </section>

          <section className="tasting-section" style={{ animationDelay: '600ms' }}>
            <SectionHeader label="Pairing Notes" ornament={tweaks.ornament} />
            <div className="tasting-prose">
              <p>{hydrateText(tasting.pairing.prose, findings, onFindingClick)}</p>
              <p>{hydrateText(tasting.pairing.compliance, findings, onFindingClick)}</p>
              <aside className="beverage-callout">
                <div className="bev-label">Suggested pairing</div>
                <p className="bev-prose">{tasting.pairing.beverage}</p>
                <svg width="18" height="24" viewBox="0 0 18 24" className="bev-glyph" aria-hidden>
                  <path d="M5 2h8l-1 9c0 2.5-1.5 4-3 4s-3-1.5-3-4L5 2z M9 15v6 M6 22h6" stroke="currentColor" strokeWidth="1.1" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </aside>
            </div>
          </section>
        </div>

        <aside className="tasting-sidebar">
          <ScoreCard tasting={tasting} chartStyle={tweaks.scoreChart} />
          <VineyardSidebarToggle count={findings.length} onClick={openVineyard} />
          <SidebarMeta tasting={tasting} />
        </aside>
      </div>

      {/* Full-width sections below the grid */}
      <CorkFeature tasting={tasting} jobId={jobId} onExpand={onOpenCork} />
      <FindingsAccordion findings={findings} onFindingClick={onFindingClick} />
    </article></main>
  );
}

/* ── Score Card ── */
function ScoreCard({ tasting, chartStyle }) {
  const axes = tasting.score.axes;
  const axisList = [
    { key: 'hndl_exposure', label: 'HNDL Exposure', val: axes.hndl_exposure },
    { key: 'signature_agility', label: 'Signature Agility', val: axes.signature_agility },
    { key: 'crypto_hygiene', label: 'Crypto Hygiene', val: axes.crypto_hygiene },
    { key: 'pq_adoption_readiness', label: 'PQ Adoption', val: axes.pq_adoption_readiness }
  ];

  return (
    <div className="score-card">
      <div className="uppercase-label score-card-title">Axis Scores</div>
      <div className="score-rubric mono">{tasting.score.rubric_version}</div>

      {chartStyle === 'bars' ? (
        <div className="score-axes">
          {axisList.map((a, i) => (
            <div className="axis-row" key={a.key} style={{ animationDelay: `${i * 100 + 200}ms` }}>
              <span className="axis-label">{a.label}</span>
              <div className="axis-bar-track"><div className="axis-bar-fill" style={{ width: `${a.val}%`, animationDelay: `${i * 100 + 200}ms` }} /></div>
              <span className="axis-value mono">{a.val}</span>
            </div>
          ))}
        </div>
      ) : (
        <RadarChart axes={axisList} />
      )}
    </div>
  );
}

function RadarChart({ axes }) {
  // Diamond: top=HNDL, right=SIG, bottom=HYG, left=PQA
  const cx = 130, cy = 130, r = 100;
  const scale = (v) => (v / 100) * r;
  const pts = [
    [cx, cy - scale(axes[0].val)],             // top
    [cx + scale(axes[1].val), cy],             // right
    [cx, cy + scale(axes[2].val)],             // bottom
    [cx - scale(axes[3].val), cy]              // left
  ];
  const polyPts = pts.map(p => p.join(',')).join(' ');

  const labels = [
    { x: 130, y: 14, text: axes[0].label, anchor: 'middle' },
    { x: 246, y: 134, text: axes[1].label, anchor: 'start' },
    { x: 130, y: 254, text: axes[2].label, anchor: 'middle' },
    { x: 14, y: 134, text: axes[3].label, anchor: 'end' }
  ];
  const vals = [
    { x: 130, y: 30, v: axes[0].val, anchor: 'middle' },
    { x: 230, y: 134, v: axes[1].val, anchor: 'start' },
    { x: 130, y: 238, v: axes[2].val, anchor: 'middle' },
    { x: 30, y: 134, v: axes[3].val, anchor: 'end' }
  ];

  return (
    <svg className="radar-svg" viewBox="0 0 260 260" width="100%" height="260">
      {[25, 50, 75, 100].map(pct => (
        <polygon key={pct} className="radar-grid"
          points={`${cx},${cy - (pct/100)*r} ${cx + (pct/100)*r},${cy} ${cx},${cy + (pct/100)*r} ${cx - (pct/100)*r},${cy}`}
        />
      ))}
      <line x1={cx} y1={cy - r} x2={cx} y2={cy + r} className="radar-axis" />
      <line x1={cx - r} y1={cy} x2={cx + r} y2={cy} className="radar-axis" />
      <polygon className="radar-shape" points={polyPts} />
      {pts.map((p, i) => <circle key={i} className="radar-dot" cx={p[0]} cy={p[1]} r="3.5" />)}
      {labels.map((l, i) => (
        <text key={i} className="radar-label" x={l.x} y={l.y} textAnchor={l.anchor}>{l.text.toUpperCase()}</text>
      ))}
      {vals.map((v, i) => (
        <text key={i} className="radar-value mono" x={v.x} y={v.y} textAnchor={v.anchor}>{v.v}</text>
      ))}
    </svg>
  );
}

function VineyardSidebarToggle({ count, onClick }) {
  return (
    <button className="vineyard-toggle" onClick={onClick}>
      <div className="vt-inner">
        <div className="vt-count">{count}</div>
        <div className="vt-body">
          <div className="vt-label">Vineyard Notes</div>
          <div className="vt-sub">Evidence, citations, remediation</div>
        </div>
        <div className="vt-arrow">→</div>
      </div>
    </button>
  );
}

function SidebarMeta({ tasting }) {
  const counts = tasting.findings.reduce((m, f) => { m[f.severity] = (m[f.severity]||0)+1; return m; }, {});
  const order = ['critical', 'high', 'medium', 'low', 'info'];
  return (
    <div className="sidebar-meta">
      <div className="uppercase-label">Findings, at a glance</div>
      <ul className="sev-list">
        {order.map(sev => counts[sev] ? (
          <li key={sev} className={`sev-item sev-${sev}`}>
            <span className="sev-chip" />
            <span className="sev-name">{sev}</span>
            <span className="sev-count mono">{counts[sev]}</span>
          </li>
        ) : null)}
      </ul>
    </div>
  );
}

/* ── Cork feature (full-width, prominent) ── */
function CorkFeature({ tasting, jobId, onExpand }) {
  const [imgFailed, setImgFailed] = React.useState(false);
  const pngHref = jobId ? `/api/v1/tastings/${jobId}/cork.png` : null;

  return (
    <section className="cork-feature">
      <div className="cork-feature-inner">
        <div className="cork-feature-copy">
          <div className="uppercase-label">The Cork</div>
          <h3 className="cork-feature-title display">Bottle this tasting.</h3>
          <p className="cork-feature-dek">
            A 1200 × 720 share card — pull-quote, grade, axis scores, and the vintage. Drops neatly into Slack, LinkedIn, X, Bluesky, Discord.
          </p>
          <div className="cork-feature-actions">
            <button className="btn-primary cork-feature-cta" onClick={onExpand}>
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden><path d="M2 10V3m0 0L6 7M2 3l-4 4M8 13h4v-4" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" strokeLinejoin="round" transform="rotate(45 6 7)"/></svg>
              Preview &amp; share
            </button>
            <button className="btn-outline" onClick={onExpand}>Download PNG</button>
          </div>
        </div>
        <div className="cork-feature-card" onClick={onExpand} role="button" tabIndex="0">
          {pngHref && !imgFailed ? (
            <img
              src={pngHref}
              alt="Tasting card preview"
              className="cork-feature-img"
              onError={() => setImgFailed(true)}
            />
          ) : (
            <CorkCard tasting={tasting} />
          )}
        </div>
      </div>
    </section>
  );
}

export function CorkCard({ tasting, size='default' }) {
  const axes = tasting.score.axes;
  const grade = tasting.score.letter_grade;
  const shelfLife = {
    'A': 'Cellar until 2035. Bring out for holidays.',
    'B': 'Drink now, or within three release cycles.',
    'C': 'Decant immediately. Ventilate aggressively.',
    'D': 'Consume under supervision.',
    'F': 'Do not serve. Quarantine. Contact the vineyard.'
  }[grade] || 'Drinking window: undefined.';

  const servingNotes = [
    { lbl: 'Nose', v: grade === 'A' || grade === 'B' ? 'Restrained, confident' : grade === 'C' ? 'Assertive' : 'Alarming' },
    { lbl: 'Finish', v: grade === 'A' ? 'Long, clean' : grade === 'B' ? 'Clean' : grade === 'C' ? 'Metallic' : 'A fire alarm' },
    { lbl: 'Pair with', v: grade === 'A' ? 'Champagne + smugness' : grade === 'B' ? 'A Tuesday' : grade === 'C' ? 'A rewrite' : 'A lawyer' }
  ];

  return (
    <div className={`cork-card cork-${size}`}>
      <div className="cork-inner">
        <div className="cork-frame">

          {/* rotating stamp */}
          <svg className="cork-notary" viewBox="0 0 120 120" aria-hidden>
            <defs>
              <path id="cork-stamp-path" d="M60,60 m-46,0 a46,46 0 1,1 92,0 a46,46 0 1,1 -92,0" />
            </defs>
            <circle cx="60" cy="60" r="52" fill="none" stroke="currentColor" strokeWidth="1"/>
            <circle cx="60" cy="60" r="46" fill="none" stroke="currentColor" strokeWidth="0.6"/>
            <text fontSize="8" letterSpacing="2.5" fill="currentColor">
              <textPath href="#cork-stamp-path" startOffset="0">TASTED · CITED · FILED · {tasting.scanned_at.toUpperCase()} · </textPath>
            </text>
            <text x="60" y="56" textAnchor="middle" fontSize="9" letterSpacing="1" fill="currentColor" fontWeight="600">RUBRIC</text>
            <text x="60" y="70" textAnchor="middle" fontSize="7" fill="currentColor" fontFamily="monospace">QS-1.0.0</text>
          </svg>

          {/* corner flourishes */}
          <svg className="cork-flourish cork-flourish--tl" viewBox="0 0 40 40" aria-hidden>
            <path d="M2 2 L2 20 M2 2 L20 2 M2 2 L14 14" stroke="currentColor" strokeWidth="0.8" fill="none"/>
            <circle cx="2" cy="2" r="1.5" fill="currentColor"/>
          </svg>
          <svg className="cork-flourish cork-flourish--tr" viewBox="0 0 40 40" aria-hidden>
            <path d="M38 2 L38 20 M38 2 L20 2 M38 2 L26 14" stroke="currentColor" strokeWidth="0.8" fill="none"/>
            <circle cx="38" cy="2" r="1.5" fill="currentColor"/>
          </svg>
          <svg className="cork-flourish cork-flourish--bl" viewBox="0 0 40 40" aria-hidden>
            <path d="M2 38 L2 20 M2 38 L20 38 M2 38 L14 26" stroke="currentColor" strokeWidth="0.8" fill="none"/>
            <circle cx="2" cy="38" r="1.5" fill="currentColor"/>
          </svg>
          <svg className="cork-flourish cork-flourish--br" viewBox="0 0 40 40" aria-hidden>
            <path d="M38 38 L38 20 M38 38 L20 38 M38 38 L26 26" stroke="currentColor" strokeWidth="0.8" fill="none"/>
            <circle cx="38" cy="38" r="1.5" fill="currentColor"/>
          </svg>

          <div className="cork-topbar">
            <span className="cork-topbar-tag">VOL I · Nº 04</span>
            <span className="cork-topbar-tag">TASTED ONCE · CITED FOREVER</span>
          </div>

          <div className="cork-ornament">
            <span className="cork-rule" />
            <span className="cork-diamond" />
            <span className="cork-amp display">&amp;</span>
            <span className="cork-diamond" />
            <span className="cork-rule" />
          </div>

          <div className="cork-wordmark">QUANTUM · SOMMELIER</div>

          <div className="cork-row cork-row--main">
            <div className="cork-main-left">
              <div className="cork-kicker">A TASTING NOTE FOR</div>
              <div className="cork-repo mono">{tasting.repo.owner}/{tasting.repo.name}</div>
              <div className="cork-vintage mono">{tasting.repo.ref} @ {tasting.repo.commit_sha} · {tasting.repo.language}</div>
            </div>
            <div className={`cork-grade grade-${grade}`}>
              <span className="cork-grade-letter">{grade}</span>
              <span className="cork-grade-ring" />
            </div>
          </div>

          <blockquote className="cork-pull">
            <span className="cork-quote-mk">“</span>
            {tasting.pull_quote}
            <span className="cork-quote-mk">”</span>
          </blockquote>

          <div className="cork-rule-mid" />

          <div className="cork-body">
            <div className="cork-body-col">
              <div className="cork-body-label">SERVING NOTES</div>
              <ul className="cork-serving">
                {servingNotes.map((s, i) => (
                  <li key={i}><span className="cork-sv-lbl">{s.lbl}.</span> <em>{s.v}</em></li>
                ))}
              </ul>
            </div>
            <div className="cork-body-col">
              <div className="cork-body-label">AXIS SCORES</div>
              <div className="cork-axes">
                {[['HNDL', axes.hndl_exposure], ['SIG', axes.signature_agility], ['HYG', axes.crypto_hygiene], ['PQA', axes.pq_adoption_readiness]].map(([lbl, v]) => (
                  <div className="cork-axis" key={lbl}>
                    <span className="cork-axis-lbl">{lbl}</span>
                    <div className="cork-axis-track"><div className="cork-axis-fill" style={{ width: `${v}%` }} /></div>
                    <span className="cork-axis-val mono">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="cork-shelf">
            <span className="cork-shelf-lbl">SHELF LIFE</span>
            <em className="cork-shelf-txt">{shelfLife}</em>
          </div>

          <div className="cork-foot">
            <span className="mono">{tasting.score.rubric_version}</span>
            <span className="cork-foot-orn">· ❦ ·</span>
            <span className="mono">{tasting.scanned_at}</span>
          </div>

          <div className="cork-barcode" aria-hidden>
            {Array.from({length: 28}).map((_, i) => (
              <span key={i} style={{ width: `${(i * 7 % 4) + 1}px` }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Findings accordion (mobile / inline) ── */
function FindingsAccordion({ findings, onFindingClick }) {
  const [open, setOpen] = React.useState(null);
  return (
    <section className="findings-accordion">
      <div className="uppercase-label">Vineyard Notes · Inline evidence</div>
      <h3 className="accordion-title display">All {findings.length} findings, with their paperwork.</h3>
      <ul className="findings-list">
        {findings.map((f) => (
          <li key={f.id} className={`finding-item ${open === f.id ? 'is-open' : ''}`}>
            <button className="finding-header" onClick={() => setOpen(open === f.id ? null : f.id)}>
              <span className={`finding-sev sev-chip sev-${f.severity}`} />
              <span className="finding-id mono">{f.id}</span>
              <span className="finding-headline">{f.short}</span>
              <span className="finding-toggle">{open === f.id ? '−' : '+'}</span>
            </button>
            {open === f.id && <FindingDetail f={f} />}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function FindingDetail({ f }) {
  return (
    <div className="finding-detail" id={f.id}>
      <div className="fd-meta">
        <span className={`sev-badge sev-${f.severity}`}>{f.severity}</span>
        <span className="fd-category">{f.category.replace(/_/g, ' ')}</span>
        {f.algorithm && <span className="fd-algo mono">{f.algorithm}</span>}
      </div>
      <div className="fd-evidence">
        <div className="fd-evidence-head">
          <span className="uppercase-label">Evidence</span>
          <a className="fd-file mono" href="#" onClick={(e)=>e.preventDefault()}>
            {f.file}:{f.lines}
          </a>
        </div>
        <pre className="fd-snippet mono"><code>{f.snippet}</code></pre>
      </div>
      <div className="fd-edu">
        <div className="fd-edu-block">
          <div className="uppercase-label">What this is</div>
          <p>{f.what}</p>
        </div>
        <div className="fd-edu-block">
          <div className="uppercase-label">Why it matters for PQC</div>
          <p>{f.why_pqc}</p>
        </div>
        <div className="fd-edu-block">
          <div className="uppercase-label">What to do about it</div>
          <p>{f.remediation}</p>
        </div>
      </div>
    </div>
  );
}

