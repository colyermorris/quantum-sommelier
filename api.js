const base = (typeof window !== 'undefined' ? window.location.origin : '') + '/api/v1';

const j = async (res) => {
  const body = await res.json().catch(() => ({}));
  if (!res.ok && res.status !== 202) {
    const err = new Error(body?.error?.message || body?.detail?.message || 'Request failed');
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
};

export const QS_API = {
  trending: () => fetch(base + '/trending').then(j),
  startTasting: (repoUrl) => fetch(base + '/tastings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repo_url: repoUrl, ref: 'main' }),
  }).then(j),
  pollTasting: (jobId) => fetch(base + '/tastings/' + jobId).then(j),
  corkPngUrl: (jobId) => base + '/tastings/' + jobId + '/cork.png',
};
