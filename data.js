// Static frontend data — headlines, scanning stage copy, and a fallback
// trending list used while /api/v1/trending is in flight.

export const HERO_HEADLINES = [
  { main: "Paste a repo.",              sub: "Get a tasting note." },
  { main: "What vintage",               sub: "is your cryptography?" },
  { main: "Let's see",                  sub: "what you're running." },
  { main: "The dependency graph",       sub: "has a bouquet." },
  { main: "Every repo",                 sub: "has a drinking window." },
  { main: "Nose the cipher suite.",     sub: "Palate the protocol." },
  { main: "Uncork your package.json.",  sub: "Decant responsibly." },
  { main: "Some codebases",             sub: "don't age well." },
  { main: "Terroir for developers.",    sub: "Served at room temperature." },
  { main: "Is it a library,",           sub: "or is it a liability?" },
  { main: "Your crypto stack",          sub: "has notes of panic." },
  { main: "A 2021 JavaScript",          sub: "with aggressive RSA on the nose." },
  { main: "What are you",               sub: "serving in production?" },
  { main: "The sommelier",              sub: "would like a word." },
  { main: "Harvest now,",               sub: "decrypt whenever." },
  { main: "Shor's algorithm",           sub: "is on the wine list." },
  { main: "Post-quantum ready,",        sub: "or post-quantum sorry?" },
  { main: "Pair this codebase",         sub: "with a stiff decant." },
  { main: "Some findings",              sub: "need a second opinion." },
  { main: "Your cellar",                sub: "has legacy holdings." },
  { main: "Vintage 2014.",              sub: "Still shipping MD5." },
  { main: "The finish is acrid.",       sub: "The grade is not." },
  { main: "Taste the terroir.",         sub: "Check the handshake." },
  { main: "Not every cipher",           sub: "deserves a cellar slot." },
  { main: "The quantum clock",          sub: "is already ticking." }
];

export const TRENDING_REPOS = [
  { name: 'juhoen/hybrid-crypto-js',    owner: 'juhoen',        url: 'https://github.com/juhoen/hybrid-crypto-js',        lang: 'JavaScript', stars: 144,  blurb: 'RSA + AES hybrid encryption for Node, React Native, and browsers.' },
  { name: 'openpgpjs/openpgpjs',        owner: 'openpgpjs',     url: 'https://github.com/openpgpjs/openpgpjs',            lang: 'JavaScript', stars: 5900, blurb: 'OpenPGP implementation for JavaScript — signing, encryption, keys.' },
  { name: 'digitalbazaar/forge',        owner: 'digitalbazaar', url: 'https://github.com/digitalbazaar/forge',            lang: 'JavaScript', stars: 5200, blurb: 'node-forge — TLS, ASN.1, RSA, ECC, hashes, all in pure JS.' },
  { name: 'pyca/cryptography',          owner: 'pyca',          url: 'https://github.com/pyca/cryptography',              lang: 'Python',     stars: 6800, blurb: 'Python cryptographic recipes and primitives. The serious one.' },
  { name: 'jpadilla/pyjwt',             owner: 'jpadilla',      url: 'https://github.com/jpadilla/pyjwt',                 lang: 'Python',     stars: 5300, blurb: 'JSON Web Token implementation for Python — HS256, RS256, ES256.' }
];

export const SCANNING_STAGES = [
  {
    key: 'fetch',
    label: 'Cloning the vineyard',
    subs: [
      "Opening the bottle",
      "Pulling the repo, not the cork",
      "Shallow clone, single branch",
      "Decanting the default branch",
      "Authenticating with the vineyard",
      "Skipping the submodule cellar",
      "Letting git breathe for a moment",
      "Fetching only what we need to taste",
      "Checking out the vintage commit",
      "Negotiating with the remote"
    ]
  },
  {
    key: 'scan',
    label: 'Nosing the dependency graph',
    subs: [
      "Reading the requirements.txt like a wine list",
      "Checking for notes of crypto-js",
      "This package.json has seen things",
      "Parsing imports for cryptographic bouquet",
      "The tree-sitter is hard at work",
      "Flagging every RSA on the palate",
      "Separating fermented code from still-good vintages",
      "Counting the MD5s so you don't have to",
      "Walking the module graph breadth-first",
      "Distinguishing AES from a variable called Aesop",
      "Looking for unlabelled bottles in node_modules",
      "Tasting for hashlib, paramiko, and friends"
    ]
  },
  {
    key: 'judge',
    label: 'The sommelier is deliberating',
    subs: [
      "Is that RSA or a variable named Regional Sales Authority",
      "Separating the signal from the sediment",
      "Some of these findings need a second opinion",
      "The LLM is weighing the evidence",
      "Rejecting test fixtures with quiet disdain",
      "Confirming the real ones, rejecting the comments",
      "Consulting the rubric for marginal cases",
      "Asking whether that's a key or a key name",
      "The Judge does not suffer false positives gladly",
      "Granting clemency to documented examples",
      "Upgrading the uncertain to confirmed",
      "Rulings are final; rationales are recorded"
    ]
  },
  {
    key: 'score',
    label: 'Computing the terroir',
    subs: [
      "Weighing the HNDL exposure",
      "Assigning the appropriate level of concern",
      "Applying the versioned rubric",
      "Averaging across the four axes",
      "Penalizing every 1024-bit RSA in sight",
      "Crediting the @noble/post-quantum sightings",
      "Tallying signature agility",
      "Assessing crypto hygiene by the ppm",
      "The letter grade is forming",
      "Rounding with a firm but fair hand",
      "Citing FIPS 203 where relevant",
      "Consulting CNSA 2.0 in the margins"
    ]
  },
  {
    key: 'synth',
    label: 'Composing the tasting note',
    subs: [
      "Choosing words for your SHA-1",
      "The sommelier has thoughts",
      "Pairing your findings with a beverage",
      "Drafting the nose, palate, and finish",
      "Selecting a pull quote for the cork",
      "Deciding if 'austere' or 'assertive' fits better",
      "Penning a headline that won't age well",
      "Threading citations through the prose",
      "Auditioning metaphors for quantum risk",
      "The finish wants to be memorable",
      "Calibrating the drink-now vs cellar verdict",
      "Signing off with the vintage"
    ]
  }
];
