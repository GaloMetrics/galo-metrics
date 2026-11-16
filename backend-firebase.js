/* Galo Metrics: login e banco fora do Claude (Firebase).
   Só liga quando o site NÃO está rodando dentro do Claude e existe window.GM_FIREBASE.
   Imita a mesma interface de window.claude.use('user' | 'db' | 'assets') que o app já usa. */
(function(){
  if (window.claude && window.claude.use) return;
  const CFG = window.GM_FIREBASE;
  if (!CFG || !CFG.apiKey) return;
  const V = '10.12.2', B = 'https://www.gstatic.com/firebasejs/' + V + '/';
  window.GM_BACKEND = 'firebase';
  window.GM_BACKEND_READY = (async () => {
    const [app, auth, fs] = await Promise.all([import(B+'firebase-app.js'), import(B+'firebase-auth.js'), import(B+'firebase-firestore.js')]);
    const A = app.initializeApp(CFG), AU = auth.getAuth(A), DB = fs.getFirestore(A);
    try { await auth.setPersistence(AU, auth.browserLocalPersistence); } catch(e){}
    try { await auth.getRedirectResult(AU); } catch(e){ console.warn(e); }
    const user = await new Promise(r => { const off = auth.onAuthStateChanged(AU, u => { off(); r(u); }); });
    let dono = false;
    if (user) { try { await fs.getDoc(fs.doc(DB, 'admin/dono')); dono = true; } catch(e){ dono = false; } }
    const enc = o => ({ _j: JSON.stringify(o ?? null) });
    const dec = d => { const x = d.data() || {}; if (typeof x._j === 'string') { try { return JSON.parse(x._j); } catch(e){ return {}; } } return x; };
    const snap = d => ({ id: d.id, exists: d.exists(), data: () => dec(d) });
    const docApi = p => { const r = fs.doc(DB, p); return { get: async () => snap(await fs.getDoc(r)), set: async o => { await fs.setDoc(r, enc(o)); }, delete: async () => { await fs.deleteDoc(r); } }; };
    const colApi = p => { let n = 1000; const api = { limit(k){ n = k; return api; }, async get(){ const s = await fs.getDocs(fs.query(fs.collection(DB, p), fs.limit(n))); return { docs: s.docs.map(snap) }; } }; return api; };
    // Imagens: reduz no navegador e guarda em uploads/{id} (sem precisar do Storage pago).
    const reduz = file => new Promise((ok, bad) => { const img = new Image(); img.onload = () => { const M = 640, s = Math.min(1, M / Math.max(img.width, img.height)); const c = document.createElement('canvas'); c.width = Math.round(img.width*s); c.height = Math.round(img.height*s); c.getContext('2d').drawImage(img, 0, 0, c.width, c.height); let q = .85, u = c.toDataURL('image/webp', q); while (u.length > 700000 && q > .35) { q -= .15; u = c.toDataURL('image/webp', q); } URL.revokeObjectURL(img.src); u.length > 900000 ? bad(new Error('imagem grande demais')) : ok(u); }; img.onerror = () => bad(new Error('arquivo de imagem inválido')); img.src = URL.createObjectURL(file); });
    const assets = { async upload(file){ if (!user) throw new Error('entre para enviar'); const d = await reduz(file); const r = fs.doc(fs.collection(DB, 'uploads')); await fs.setDoc(r, { uid: user.uid, d, em: new Date().toISOString() }); return { id: r.id, url: 'fb:' + r.id, sizeBytes: d.length, contentType: 'image/webp' }; } };
    const CACHE = {};
    window.GM_UP_GET = async id => { if (CACHE[id]) return CACHE[id]; const s = await fs.getDoc(fs.doc(DB, 'uploads/' + id)); return CACHE[id] = s.exists() ? s.data().d : ''; };
    window.GM_LOGIN = async () => { const p = new auth.GoogleAuthProvider(); try { await auth.signInWithPopup(AU, p); location.reload(); } catch(e){ if (/popup/.test(e.code||'')) await auth.signInWithRedirect(AU, p); else { console.error(e); alert('Não foi possível entrar agora.'); } } };
    window.GM_LOGOUT = async () => { await auth.signOut(AU); location.reload(); };
    window.GM_USER_NAME = user ? (user.displayName || (user.email||'').split('@')[0]) : '';
    window.GM_USER_PHOTO = user ? (user.photoURL || '') : '';
    window.claude = { use: async k => {
      if (k === 'user') return user ? { id: async () => user.uid, isOwner: async () => dono, name: window.GM_USER_NAME } : null;
      if (k === 'db') return { doc: docApi, collection: colApi };
      if (k === 'assets') return user ? assets : null;
      return null;
    } };
  })().catch(e => { console.error('Firebase indisponível', e); });
})();
