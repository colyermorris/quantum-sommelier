// Educational templates for finding detail panels.
// Keyed by (algorithm || category || library). Falls back to generic text.

export const FINDING_EDU = {
  RSA: {
    what: "RSA is a public-key cryptosystem whose security rests on the difficulty of factoring large semiprimes. It's used for key exchange, digital signatures, and sometimes bulk encryption.",
    why_pqc: "Shor's algorithm on a sufficiently large quantum computer factors RSA moduli in polynomial time. Every RSA key size — 2048, 3072, even 4096 bits — is broken by a cryptographically-relevant quantum computer. RSA has no quantum safety margin.",
    remediation: "Plan a migration to NIST-standardized post-quantum primitives. For key exchange, use ML-KEM (Kyber); for signatures, ML-DSA (Dilithium) or SLH-DSA (SPHINCS+). Deploy hybrid modes (classical + PQ) during the transition."
  },
  ECDSA: {
    what: "ECDSA is the elliptic-curve variant of DSA, widely used for digital signatures in TLS, JWT, and blockchain systems. Common curves: P-256, P-384, secp256k1.",
    why_pqc: "Shor's algorithm solves the elliptic-curve discrete logarithm problem too. Every named ECDSA curve falls to the same quantum machine that breaks RSA, at lower key sizes and with less quantum resource.",
    remediation: "Replace ECDSA signatures with ML-DSA (Dilithium) or SLH-DSA (SPHINCS+). For code-signing and long-lived signatures, plan the migration now — signatures minted today are verified for years."
  },
  ECDH: {
    what: "Elliptic-curve Diffie-Hellman is the key-exchange half of most modern TLS handshakes and secure messaging protocols. Same curves as ECDSA.",
    why_pqc: "HNDL (Harvest-Now-Decrypt-Later): a network observer can record today's ECDH handshakes and decrypt them once a CRQC exists. Secrecy expires retroactively.",
    remediation: "Move to hybrid ML-KEM + X25519 in TLS 1.3 (RFC draft-ietf-tls-hybrid-design). Chrome and Cloudflare already deploy X25519MLKEM768."
  },
  MD5: {
    what: "MD5 is a 128-bit hash function. Collision attacks have been practical since 2004; preimage attacks are still infeasible classically.",
    why_pqc: "Grover's algorithm gives a quadratic speedup on preimage search, halving the effective bit-strength of any hash. MD5's 64-bit post-quantum preimage security is catastrophic. But the real issue is MD5 is already broken *classically* — this isn't primarily a quantum problem.",
    remediation: "Replace MD5 with SHA-256 at minimum; SHA-384 or SHA-3-384 for new systems. For HMAC specifically, even HMAC-MD5 retains some strength but should still be rotated out."
  },
  SHA1: {
    what: "SHA-1 is a 160-bit hash function. SHAttered (2017) demonstrated practical chosen-prefix collisions. Deprecated by NIST, CA/Browser Forum, and effectively every serious cryptographic standard.",
    why_pqc: "Grover halves preimage security to 80 bits, which is uncomfortably close to feasible. But again, SHA-1's classical collision attacks already disqualify it.",
    remediation: "Upgrade to SHA-256 for general hashing, SHA-384 where extra margin is warranted. For HMAC, HMAC-SHA-256."
  },
  DES: {
    what: "DES (and its successor 3DES) is a symmetric block cipher from the 1970s. Banned by NIST for new systems in 2017; 3DES formally deprecated in 2023.",
    why_pqc: "Grover reduces DES's 56-bit key to 28 bits effective — trivially brute-forceable. 3DES fares marginally better but is still below modern thresholds.",
    remediation: "AES-256 in GCM or ChaCha20-Poly1305 for authenticated encryption. Never deploy DES or 3DES in new code."
  },
  AES: {
    what: "AES is the NIST-standard symmetric block cipher. AES-128, AES-192, and AES-256 are all FIPS-approved.",
    why_pqc: "Grover gives a square-root speedup on key search. AES-128's 128-bit key drops to 64-bit effective post-quantum — borderline. AES-256 retains a full 128-bit margin and is considered quantum-safe.",
    remediation: "Prefer AES-256 for new deployments, especially for data with a long confidentiality horizon. AES-128 is acceptable for short-lived session keys."
  }
};

export const FINDING_CATEGORY_EDU = {
  committed_secret: {
    what: "A credential — API key, private key, token, or password — was committed to the repository. Git history preserves it even if later removed.",
    why_pqc: "This is a classical compromise, not a quantum one: the secret is already out. Post-quantum considerations are moot if the credential itself has leaked.",
    remediation: "Rotate the secret immediately with the issuing provider. Purge from git history (BFG Repo-Cleaner or git-filter-repo). Add a pre-commit secret scanner (gitleaks, trufflehog)."
  },
  config_weakness: {
    what: "A configuration file declares a cipher suite, key size, or protocol option that is weaker than current best practice.",
    why_pqc: "Misconfiguration compounds cryptographic debt: a strong algorithm deployed with weak parameters is no better than a weak algorithm.",
    remediation: "Align with CNSA 2.0 or Mozilla's 'Modern' TLS configuration. Remove deprecated cipher suites; pin minimum protocol versions."
  },
  deprecated_primitive: {
    what: "An algorithm that has been formally deprecated by a standards body (NIST, IETF, CA/Browser Forum) appears in code or dependencies.",
    why_pqc: "Deprecated primitives are ahead of PQ in the queue — they're already broken or on-track to be broken by classical attacks before quantum even matters.",
    remediation: "Replace with the standards body's recommended successor. Document the migration path in a SECURITY.md or ADR."
  },
  pqc_adoption: {
    what: "The repository is actively using a post-quantum primitive — ML-KEM, ML-DSA, SLH-DSA, or a hybrid construction.",
    why_pqc: "This is the good news. The codebase has begun the transition and is ahead of the curve on CNSA 2.0 timelines.",
    remediation: "Verify the parameter sets match NIST final standards (FIPS 203/204/205). Ensure hybrid modes combine PQ with a classical primitive, not PQ alone."
  },
  hybrid_scheme: {
    what: "A hybrid construction combines a classical primitive (e.g., X25519) with a post-quantum primitive (e.g., ML-KEM) so the result is at least as secure as the stronger of the two.",
    why_pqc: "This is the recommended migration strategy. The classical half guards against flaws in the still-new PQ algorithms; the PQ half guards against future quantum attacks.",
    remediation: "Confirm the hybrid combines components with independent assumptions. Follow RFC 9180 (HPKE) or the TLS hybrid KEM drafts."
  },
  quantum_vulnerable: {
    what: "A primitive whose security is broken by a cryptographically-relevant quantum computer (CRQC) — RSA, ECDSA, ECDH, DH, classical DSA.",
    why_pqc: "These are the primary targets of the PQ migration. Any traffic or signature produced with these primitives loses confidentiality or authenticity once a CRQC exists.",
    remediation: "Inventory every call site, then migrate to the NIST PQ suite or a hybrid. Prioritize long-lived signatures and high-value secrets."
  },
  suspected: {
    what: "The scanner surfaced a candidate that could be a cryptographic primitive but the judge wasn't fully confident — often a variable name or string that looks cryptographic in context.",
    why_pqc: "Cannot assess without confirming the finding. Worth a human glance.",
    remediation: "Review the flagged line. If it's a real crypto call, treat it according to its algorithm; if it's a false positive (e.g., 'RSA' standing for 'Regional Sales Authority'), close it."
  }
};

// Library-keyed edu. Takes priority over algorithm / category when a finding
// has a .library set (e.g. import-consolidated findings).
export const FINDING_LIBRARY_EDU = {
  "cryptography": {
    what: "pyca/cryptography is the serious Python crypto library — AES, RSA, ECDSA, ECDH, Ed25519, x25519, Fernet, HMAC, HKDF, X.509. The surface area is almost entirely classical.",
    why_pqc: "No post-quantum primitives yet. RSA and the EC families are exactly what Shor's algorithm breaks; the AES and hash primitives are Grover-diminished but not broken. A repo that leans on pyca/cryptography will have a wide classical blast radius to migrate.",
    remediation: "Inventory every call site (sign/verify, encrypt/decrypt, key exchange). Tag each with its confidentiality horizon. When NIST PQ wrappers land in pyca, migrate long-horizon call sites to ML-KEM/ML-DSA. Hybrid until the PQ algorithms age a few years in production."
  },
  "pycrypto(dome)": {
    what: "PyCrypto / PyCryptodome — classical symmetric and public-key primitives. PyCrypto itself is unmaintained; PyCryptodome is the active fork.",
    why_pqc: "No PQ algorithms. AES/SHA are Grover-weakened; RSA/DSA/ECDSA are Shor-broken. In any long-horizon use, this library is on the migration list.",
    remediation: "Prefer pyca/cryptography for new work; it has a more careful API and active maintenance. Plan PQ migration identically to pyca's classical surface."
  },
  "rsa": {
    what: "The `rsa` package — pure-Python RSA key generation, signing, and encryption. Simple API, narrow surface.",
    why_pqc: "RSA is broken in polynomial time by Shor's algorithm on a CRQC. Every bit of RSA in this repo is quantum-vulnerable regardless of key size.",
    remediation: "Migrate signatures to ML-DSA (CRYSTALS-Dilithium) and key exchange / encryption to ML-KEM (CRYSTALS-Kyber). Use hybrid (RSA + ML-KEM) during the transition period."
  },
  "ecdsa": {
    what: "Pure-Python ECDSA — elliptic-curve digital signatures over NIST curves, secp256k1, and Ed25519-adjacent curves.",
    why_pqc: "ECDSA's security reduces to the elliptic-curve discrete log problem, which Shor's algorithm also solves in polynomial time. Broken by a CRQC across every curve.",
    remediation: "Migrate to ML-DSA or SLH-DSA. Hybrid signatures (ECDSA + PQ) during the transition preserve security against both classical and quantum attackers."
  },
  "PyJWT": {
    what: "PyJWT signs and verifies JSON Web Tokens. Common algorithms: HS256 (symmetric), RS256 (RSA), ES256 (ECDSA over P-256), EdDSA.",
    why_pqc: "RS256, ES256, EdDSA are all quantum-vulnerable signature algorithms. HS256 (HMAC) is Grover-weakened but still practical with a 256-bit key. No standardized PQ JWT algorithms exist yet — draft-ietf-cose-post-quantum-signatures is moving.",
    remediation: "For long-lived tokens, plan to adopt COSE PQ signatures when standardized. For short-lived tokens (<1 hour), the quantum risk is lower. Audit which algorithm each service accepts and drop RSA ≤ 2048."
  },
  "paramiko": {
    what: "Paramiko is an SSH-2 protocol implementation in Python — key exchange, host-key verification, authenticated channels.",
    why_pqc: "SSH host keys (RSA / ECDSA / Ed25519) and key exchange (classical DH / ECDH) are quantum-vulnerable. OpenSSH is rolling out sntrup761x25519 and ML-KEM hybrids; paramiko lags.",
    remediation: "Track paramiko's PQ roadmap. For high-value SSH sessions, prefer OpenSSH's hybrid KEX today via the `ssh` CLI until paramiko catches up."
  },
  "node:crypto": {
    what: "Node.js built-in crypto module — wraps the OpenSSL/BoringSSL runtime. Exposes symmetric ciphers, RSA/EC keys, hashes, HKDF, KDFs, and `getRandomValues` via `webcrypto`.",
    why_pqc: "Most node:crypto use is classical — RSA-OAEP, RSA-PSS, ECDSA, ECDH. Node added ML-KEM/ML-DSA through OpenSSL 3.2+ providers in recent versions, but usage is still rare.",
    remediation: "Audit which primitives the codebase actually calls (`createSign`, `generateKeyPair`, `diffieHellman`). Plan to swap to `ml-kem` / `ml-dsa` wrappers as Node exposes them, or use @noble/post-quantum for pure-JS PQ."
  },
  "@noble/post-quantum": {
    what: "@noble/post-quantum — audited pure-JS implementations of ML-KEM, ML-DSA, and SLH-DSA (NIST final standards FIPS 203/204/205).",
    why_pqc: "This IS the PQ path. A repo depending on this library is already executing the post-quantum migration in JavaScript.",
    remediation: "Verify parameter sets match FIPS finals (ML-KEM-768, ML-DSA-65, SLH-DSA-128s recommended for most use cases). Prefer hybrid constructions: wrap with a classical primitive via @noble/curves for defense in depth during the PQ algorithms' early years."
  },
  "@noble/hashes": {
    what: "@noble/hashes — audited pure-JS hash primitives: SHA-2, SHA-3, BLAKE2/3, HMAC, HKDF, PBKDF2, scrypt.",
    why_pqc: "Hashes are weakened by Grover (effective strength halved) but not broken. SHA-256 remains ~128-bit post-Grover, which is marginally acceptable. Nothing here is Shor-broken.",
    remediation: "For long-horizon use, prefer SHA-384 / SHA-512 / SHA-3 to keep ≥192-bit post-Grover margin. HMAC is fine at SHA-256."
  },
  "@noble/curves": {
    what: "@noble/curves — audited pure-JS elliptic-curve primitives: secp256k1, P-256, P-384, P-521, Ed25519, x25519, BLS12-381.",
    why_pqc: "All of these curves are quantum-vulnerable. Ed25519 and x25519 are classically stronger than the NIST P-curves but fall to Shor just the same.",
    remediation: "For new signatures / KEX on long-horizon systems, prefer @noble/post-quantum. Classical curves remain fine for short-horizon use or hybrid constructions."
  },
  "crypto-js": {
    what: "crypto-js — legacy pure-JS crypto library: AES, DES, Triple-DES, RC4, Rabbit, SHA-1/2/3, HMAC, PBKDF2.",
    why_pqc: "Presence of crypto-js is a soft yellow flag even before PQ — the library ships weak defaults (ECB mode when you ask for AES with no mode, odd IV handling) and DES/RC4 are entirely broken classically. Whatever PQ roadmap follows, get off crypto-js first.",
    remediation: "Migrate to @noble/hashes + @noble/ciphers or the WebCrypto API. For PQ, pair WebCrypto with @noble/post-quantum."
  },
  "jsonwebtoken": {
    what: "jsonwebtoken — Node.js library for signing and verifying JSON Web Tokens. Shares algorithm names with PyJWT (HS256/RS256/ES256/EdDSA).",
    why_pqc: "Same story as PyJWT: RS256, ES256, EdDSA are all quantum-vulnerable. No PQ JWT algorithms standardized yet.",
    remediation: "Shorten token lifetimes where possible. Track IETF COSE PQ signatures work. For RS256, enforce ≥ 3072-bit keys as a near-term mitigation."
  },
  "hashlib": {
    what: "hashlib — Python standard library hash primitives: MD5, SHA-1, SHA-2, SHA-3, BLAKE2, plus PBKDF2 and scrypt KDFs.",
    why_pqc: "Hashes are Grover-weakened, not Shor-broken. SHA-256 → ~128-bit post-Grover, which is marginal for long-horizon applications. MD5/SHA-1 are already broken classically for collision resistance.",
    remediation: "Audit each call for whether classical collision resistance is required (signatures, commitments) versus just preimage (HMAC). Prefer SHA-384 / SHA-3-256 / BLAKE2 for new work on long-horizon systems."
  }
};

export function normalizeTasting(t) {
  if (!t) return null;
  const eduFor = (f) => {
    const byLib = f.library && FINDING_LIBRARY_EDU[f.library];
    const byAlg = f.algorithm && FINDING_EDU[f.algorithm.toUpperCase().replace(/[- ]/g, '')];
    const byCat = f.category && FINDING_CATEGORY_EDU[f.category];
    return byLib || byAlg || byCat || {
      what: f.rule_description || "The scanner flagged this pattern for sommelier review.",
      why_pqc: "Any cryptographic primitive requires a post-quantum audit: if it's classical RSA/ECC/DH, it's on the migration list. If it's a hash, Grover cuts the bit-strength in half. If it's symmetric with a 128-bit key, the margin is narrow but intact.",
      remediation: "Consult the NIST PQC migration guide (NIST IR 8547). Inventory every usage site, triage by confidentiality horizon, schedule replacement with ML-KEM / ML-DSA / SLH-DSA as appropriate."
    };
  };
  const normFindings = (t.findings || []).map((f) => {
    const edu = eduFor(f);
    return {
      ...f,
      short: f.short || f.rule_description || f.id,
      file: f.file || f.file_path || '',
      lines: f.lines || (f.line_start && f.line_end ? (f.line_start === f.line_end ? String(f.line_start) : `${f.line_start}-${f.line_end}`) : ''),
      snippet: f.snippet || f.code_snippet || '',
      what: f.what || edu.what,
      why_pqc: f.why_pqc || edu.why_pqc,
      remediation: f.remediation || edu.remediation,
    };
  });
  return {
    ...t,
    repo: { ...t.repo, language: t.repo.primary_language || t.repo.language || 'unknown' },
    palate: { paragraphs: (t.palate && t.palate.prose) || [] },
    finish: { prose: ((t.finish && t.finish.prose) || []).join('\n\n') },
    findings: normFindings,
  };
}
