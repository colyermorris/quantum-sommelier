/* Scanning state — polls the real backend job and renders progress.
   Maps API stages (fetching/scanning/judging/scoring/synthesizing/validating)
   onto the 5 editorial stages the UI already has. */

import React from 'react';
import { SCANNING_STAGES } from './data.js';
import { QS_API } from './api.js';

const STAGE_MAP = {
  fetching: 0,
  scanning: 1,
  judging: 2,
  scoring: 3,
  synthesizing: 4,
  validating: 4,
};

export function Scanning({ repoSlug, jobId, onDone, onCancel, onError, tweaks }) {
  const [stageIdx, setStageIdx] = React.useState(0);
  const [subIdx, setSubIdx] = React.useState(0);
  const [progress, setProgress] = React.useState(5);

  React.useEffect(() => {
    const subs = SCANNING_STAGES[stageIdx]?.subs || [];
    if (!subs.length) return;
    setSubIdx(Math.floor(Math.random() * subs.length));
    const t = setInterval(() => setSubIdx((s) => (s + 1) % subs.length), 3200);
    return () => clearInterval(t);
  }, [stageIdx]);

  React.useEffect(() => {
    if (!jobId) return;
    let alive = true;
    let ticks = 0;
    const tick = async () => {
      if (!alive) return;
      ticks += 1;
      try {
        const data = await QS_API.pollTasting(jobId);
        if (!alive) return;
        if (data.status === 'complete') {
          setStageIdx(SCANNING_STAGES.length - 1);
          setProgress(100);
          setTimeout(() => { if (alive) onDone(data.tasting); }, 400);
          return;
        }
        if (data.status === 'failed') {
          onError(data.error?.message || 'The sommelier is indisposed.');
          return;
        }
        if (data.status === 'running') {
          const idx = STAGE_MAP[data.stage];
          if (typeof idx === 'number') setStageIdx(idx);
          if (typeof data.progress_pct === 'number') setProgress(data.progress_pct);
        }
      } catch (err) {
        if (err.status === 429) {
          onError(err.body?.error?.message || 'Rate limited.');
          return;
        }
        if (ticks > 60) {
          onError('The sommelier is not responding.');
          return;
        }
      }
      if (alive) setTimeout(tick, 1200);
    };
    const id = setTimeout(tick, 800);
    return () => { alive = false; clearTimeout(id); };
  }, [jobId, onDone, onError]);

  return (
    <main className="scanning" id="main" aria-live="polite">
      <div className="scanning-top">
        <div className="uppercase-label">In the cellar</div>
        <h1 className="scanning-repo mono">{repoSlug}</h1>
        <p className="scanning-sub">The sommelier is working. Real clone, real scan, real tasting note — usually 15–45 seconds.</p>
      </div>

      <ol className="stage-list">
        {SCANNING_STAGES.map((stage, i) => {
          const state = i < stageIdx ? 'done' : i === stageIdx ? 'active' : 'pending';
          return (
            <li key={stage.key} className={`stage stage--${state}`}>
              <div className="stage-glyph">
                {state === 'done' ? (
                  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden>
                    <path d="M3 8.5l3.2 3.2L13 5" stroke="currentColor" strokeWidth="1.8" fill="none" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                ) : state === 'active' ? (
                  <div className="pour">
                    <div className="pour-stream" />
                    <div className="pour-pool" />
                  </div>
                ) : (
                  <div className="stage-dot" />
                )}
              </div>
              <div className="stage-body">
                <div className="stage-label">
                  <span>{stage.label}</span>
                  {state === 'active' && <span className="stage-ellipsis">…</span>}
                </div>
                {state === 'active' && (
                  <div key={subIdx} className="stage-sub">{stage.subs[subIdx]}</div>
                )}
                {state === 'done' && (
                  <div className="stage-sub stage-sub--done">Poured</div>
                )}
              </div>
              <div className="stage-stamp mono">
                {String(i+1).padStart(2,'0')}
              </div>
            </li>
          );
        })}
      </ol>

      <div className="scanning-bar" role="progressbar" aria-valuenow={progress} aria-valuemin="0" aria-valuemax="100">
        <div className="scanning-bar-fill" style={{ width: `${progress}%` }} />
        <div className="scanning-bar-label mono">{progress}%</div>
      </div>

      <button className="btn-ghost" onClick={onCancel}>Cancel the pour</button>
    </main>
  );
}
