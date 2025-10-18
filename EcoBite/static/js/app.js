import { listPosts, createPost, claimPost, approveClaim, rejectClaim, computeStats, getUser } from './api.js';

/* ---------- Sidebar highlighting + user badge ---------- */
export function navActivate(key){
  const a = document.querySelector(`.nav a[data-nav="${key}"]`);
  if(a){ document.querySelectorAll('.nav a').forEach(x=>x.classList.remove('active')); a.classList.add('active'); }
  const u = getUser();
  const sbN = document.getElementById('sbUser'); if(sbN) sbN.textContent = u.name || 'Eco Member';
  const sbE = document.getElementById('sbEmail'); if(sbE) sbE.textContent = u.email;
}

/* ---------- FEED ---------- */
export async function renderFeed(){
  hydrateUserOnSidebar();
  const state = { scope:'available' };

  // tabs
  document.querySelectorAll('.tab').forEach(btn=>{
    btn.addEventListener('click', ()=>{
      document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
      btn.classList.add('active');
      state.scope = btn.dataset.scope;
      draw();
    });
  });

  ['search','type','sort'].forEach(id=>{
    const el = document.getElementById(id);
    if(el) el.addEventListener('input', draw);
  });

  draw();

  function draw(){
    const { available, total, shared, savedKg, list } = computeStats();
    set('#stAvailable', available);
    set('#stTotal', total);
    set('#stShared', shared);
    set('#stWaste', `${savedKg}kg`);

    const q = (val('search')||'').toLowerCase();
    const type = val('type') || 'all';
    const scope = state.scope;

    let items = list.filter(p=>{
      const mScope = scope==='available' ? p.status==='available'
                  : scope==='claimed'   ? p.status==='claimed'
                  : p.status==='expired';
      const mType = type==='all' ? true : (p.category===type || p.category===singular(type));
      const mQ = !q || (p.title||'').toLowerCase().includes(q);
      return mScope && mType && mQ;
    });

    // sort
    if(val('sort')==='new'){
      items.sort((a,b)=> new Date(b.createdAt)-new Date(a.createdAt));
    }

    const feed = byId('feed');
    feed.innerHTML = '';
    items.forEach(p=>{
      feed.appendChild(card(p, {
        cta: p.status==='available' ? {label:'Claim', click:()=> { claimPost(p.id).then(draw);} } : null,
        showOwner:true
      }));
    });

    byId('emptyFeed').style.display = items.length ? 'none' : 'block';
  }
}

/* ---------- CREATE ---------- */
export function bindCreate(){
  hydrateUserOnSidebar();
  const form = byId('createForm');
  form.addEventListener('submit', async e=>{
    e.preventDefault();
    const fd = new FormData(form);
    const diet = fd.getAll('diet');
    const data = {
      title: fd.get('title').trim(),
      category: fd.get('category'),
      qty: fd.get('qty'),
      diet,
      location: fd.get('location').trim(),
      expires: fd.get('expires')
    };
    await createPost(data);
    location.href = 'index.html';
  });
}

/* ---------- MY POSTS ---------- */
export async function renderMyPosts(){
  hydrateUserOnSidebar();
  const user = getUser();
  const list = (await listPosts()).filter(p=>p.ownerEmail===user.email);
  const wrap = byId('myPosts');
  wrap.innerHTML = '';
  list.forEach(p=>{
    const pending = p.claims.filter(c=>c.status==='pending');
    const first = pending[0];
    wrap.appendChild(card(p,{
      extra: first ? buttons([
        {label:'Approve', type:'primary', click:()=> approveClaim(p.id, first.id).then(()=>location.reload()) },
        {label:'Reject',  click:()=> rejectClaim(p.id, first.id).then(()=>location.reload()) }
      ]) : null
    }));
  });
  byId('emptyMine').style.display = list.length ? 'none' : 'block';
}

/* ---------- REQUESTS ---------- */
export async function renderRequests(){
  hydrateUserOnSidebar();
  const user = getUser();
  const list = (await listPosts());

  const pending = [];
  const history = [];
  list.forEach(p=>{
    p.claims.forEach(c=>{
      if(c.byEmail===user.email){
        const item = {...p, _claim:c};
        (c.status==='pending' ? pending : history).push(item);
      }
    });
  });

  const pWrap = byId('reqPending'); pWrap.innerHTML='';
  pending.forEach(p=>{
    pWrap.appendChild(card(p, { extra: tag('span','badge','⏳ Pending') }));
  });

  const hWrap = byId('reqHistory'); hWrap.innerHTML='';
  history.forEach(p=>{
    const status = p._claim.status==='approved' ? '✅ Approved' : '❌ Rejected';
    hWrap.appendChild(card(p, { extra: tag('span','badge',status) }));
  });
}

/* ---------- PROFILE ---------- */
export async function renderProfile(){
  hydrateUserOnSidebar();
  const user = getUser();
  set('#pfName', user.name || 'Eco Member'); set('#pfEmail', user.email);

  const { shared, savedKg, list } = computeStats();
  const mine = list.filter(p=>p.ownerEmail===user.email);
  set('#kPosts', mine.length);
  set('#kFed', shared);
  set('#kSaved', `${savedKg}kg`);
  set('#kStreak', '0 days');
  set('#impactCO2', `${savedKg} kg`);
  set('#impactMeals', shared);

  const pts = mine.length*10 + shared*20; // pretend point model
  set('#levelPts', `${pts} total points`);
  byId('levelBar').style.width = Math.min(100, (pts/50)*100) + '%';

  const act = byId('pfActivity'); act.innerHTML='';
  mine.slice(0,4).forEach(p=> act.appendChild(card(p)));
}

/* ---------- small UI helpers ---------- */
function card(p, opts={}){
  const root = tag('div','card');
  const t = tag('div','thumb','🍱'); root.appendChild(t);
  const body = tag('div'); root.appendChild(body);

  const title = tag('h5',null,p.title || '(no title)'); body.appendChild(title);
  const meta = tag('div','meta',[
    `Category: ${p.category}`, `Qty: ${p.qty||'-'}`, `Location: ${p.location||'-'}`,
    `Expires: ${formatDT(p.expires)}`
  ].join(' • ')); body.appendChild(meta);

  if(opts.showOwner){
    body.appendChild(tag('div','badge',`👤 ${p.ownerName || p.ownerEmail}`));
  }

  const row = tag('div','actions'); body.appendChild(row);
  if(opts.cta){ row.appendChild(btn(opts.cta.label, 'primary', opts.cta.click)); }
  if(opts.extra){ row.appendChild(opts.extra); }

  return root;
}
function btn(label, type='ghost', click){ const b = tag('button', `btn ${type}`, label); b.onclick=click; return b; }
function buttons(arr){ const w=tag('div','actions'); arr.forEach(d=>w.appendChild(btn(d.label, d.type, d.click))); return w; }

function tag(el, cls, content){
  const e = document.createElement(el);
  if(cls) e.className = cls;
  if(content!==undefined) e.innerHTML = content;
  return e;
}
function set(sel, v){ const el=byId(sel.slice(1)); if(el) el.textContent=v; }
function val(id){ const el=byId(id); return el ? el.value : ''; }
function byId(id){ return document.getElementById(id); }
function singular(s){ return s.replace(/s$/,''); }
function formatDT(iso){ try{return new Date(iso).toLocaleString()}catch{return iso} }

function hydrateUserOnSidebar(){
  const u = getUser();
  const w = new MutationObserver(()=>{
    const n = document.getElementById('sbUser'); const e = document.getElementById('sbEmail');
    if(n&&e){ n.textContent = u.name || 'Eco Member'; e.textContent = u.email; w.disconnect(); }
  });
  w.observe(document.body, {subtree:true, childList:true});
}
