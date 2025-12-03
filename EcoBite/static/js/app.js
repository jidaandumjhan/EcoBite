
import { listPosts, createPost, claimPost, approveClaim, rejectClaim, computeStats, getUser } from './api.js';

/* ---------- Sidebar highlighting + user badge ---------- */
export function navActivate(key) {
  const a = document.querySelector(`.nav a[data-nav="${key}"]`);
  if (a) { document.querySelectorAll('.nav a').forEach(x => x.classList.remove('active')); a.classList.add('active'); }
  const u = getUser();
  const sbN = document.getElementById('sbUser'); if (sbN) sbN.textContent = u.name || 'Eco Member';
  const sbE = document.getElementById('sbEmail'); if (sbE) sbE.textContent = u.email;
}

/* ---------- FEED ---------- */
export async function renderFeed() {
  hydrateUserOnSidebar();
  const state = { scope: 'available' };

  // tabs
  document.querySelectorAll('.tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(x => x.classList.remove('active'));
      btn.classList.add('active');
      state.scope = btn.dataset.scope;
      draw();
    });
  });

  ['search', 'type', 'sort'].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.addEventListener('input', draw);
  });

  // Dietary popup toggle
  const dietBtn = byId('dietBtn');
  const dietPopup = byId('dietPopup');
  if (dietBtn && dietPopup) {
    dietBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      dietPopup.style.display = dietPopup.style.display === 'none' ? 'block' : 'none';
    });
    document.addEventListener('click', () => {
      if (dietPopup) dietPopup.style.display = 'none';
      document.querySelectorAll('.custom-select').forEach(s => s.classList.remove('open'));
    });
    if (dietPopup) dietPopup.addEventListener('click', (e) => e.stopPropagation());
  }

  initCustomDropdowns();
  await draw();


  async function draw() {
    // Fetch global stats
    try {
      const res = await fetch('/api/stats/global');
      if (res.ok) {
        const stats = await res.json();
        set('#stAvailable', stats.available_now);
        set('#stTotal', stats.total_posts);
        set('#stShared', stats.successfully_shared);
        set('#stWaste', `${stats.food_waste_prevented_kg.toFixed(1)}kg`);
      }
    } catch (e) { console.error("Stats error", e); }

    const q = (val('search') || '').toLowerCase();
    const type = val('type') || 'all';
    const scope = state.scope;
    const sort = val('sort') || 'newest';

    // Fetch posts with filters
    const params = {
      status: scope,
      search: q,
      type: type,
      sort: sort
    };

    let items = [];
    try {
      items = await listPosts(params);
    } catch (e) { console.error("Feed error", e); }

    const feed = byId('feed');
    feed.innerHTML = '';
    items.forEach(p => {
      // Logic for request button: if not owner and available
      // API returns owner_email. We check against current user email.
      const user = getUser();
      const isOwner = p.owner_email === user.email;
      const isAvailable = p.status === 'active';

      feed.appendChild(card(p, {
        cta: (isAvailable && !isOwner) ? { label: 'Request', click: () => { openClaimModal(p); } } : null,
        showOwner: true
      }));
    });

    byId('emptyFeed').style.display = items.length ? 'none' : 'block';
  }
}

function openClaimModal(post) {
  const qty = prompt(`Requesting: ${post.title}\nHow much do you need? (e.g. "2 slices")`, "1");
  if (qty) {
    const msg = prompt("Optional message for the donor:", "I would like to pick this up!");
    claimPost(post.id, { requested_quantity: qty, message: msg })
      .then(() => { alert("Request sent!"); renderFeed(); })
      .catch(e => alert(e.message));
  }
}

/* ---------- CREATE ---------- */
export function bindCreate() {
  hydrateUserOnSidebar();
  initCustomDropdowns();
  initMap();

  const form = byId('createForm');
  if (form) {
    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const fd = new FormData(form);
      const data = {
        title: fd.get('description'),
        description: fd.get('description'),
        category: fd.get('category'),
        quantity: fd.get('qty'),
        dietary_tags: fd.getAll('diet'),
        location_text: fd.get('location'),
        pickup_window_end: fd.get('expiry_time'),
        expires_at: fd.get('expiry_time')
      };

      try {
        await createPost(data);
        window.location.href = '/';
      } catch (err) {
        alert('Failed to create post: ' + err.message);
      }
    });
  }
}

function initMap() {
  const mapEl = byId('map');
  if (!mapEl || !window.L) return;
  const defaultLoc = [40.7128, -74.0060];
  const map = L.map('map').setView(defaultLoc, 15);
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { attribution: '© OpenStreetMap contributors' }).addTo(map);
  let marker = L.marker(defaultLoc, { draggable: true }).addTo(map);

  const updateInput = async (lat, lng) => {
    const input = byId('locationInput');
    if (!input) return;
    input.value = `${lat.toFixed(5)}, ${lng.toFixed(5)} (Loading address...)`;
    try {
      const resp = await fetch(`https://nominatim.openstreetmap.org/reverse?format=json&lat=${lat}&lon=${lng}`);
      if (resp.ok) {
        const data = await resp.json();
        if (data && data.display_name) input.value = data.display_name;
      } else { input.value = `${lat.toFixed(5)}, ${lng.toFixed(5)}`; }
    } catch (e) { input.value = `${lat.toFixed(5)}, ${lng.toFixed(5)}`; }
  };

  if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(pos => {
      const { latitude, longitude } = pos.coords;
      map.setView([latitude, longitude], 15);
      marker.setLatLng([latitude, longitude]);
      updateInput(latitude, longitude);
    });
  }
  marker.on('dragend', function (e) { const { lat, lng } = marker.getLatLng(); updateInput(lat, lng); });
  map.on('click', function (e) { const { lat, lng } = e.latlng; marker.setLatLng(e.latlng); updateInput(lat, lng); });
}

function initCustomDropdowns() {
  document.querySelectorAll('.custom-select').forEach(sel => {
    const trigger = sel.querySelector('.select-trigger');
    const options = sel.querySelectorAll('.option');
    const hiddenSelect = sel.querySelector('select');
    const triggerText = sel.querySelector('.trigger-text');
    const newTrigger = trigger.cloneNode(true);
    trigger.parentNode.replaceChild(newTrigger, trigger);
    newTrigger.addEventListener('click', (e) => {
      e.stopPropagation();
      document.querySelectorAll('.custom-select').forEach(s => { if (s !== sel) s.classList.remove('open'); });
      sel.classList.toggle('open');
    });
    options.forEach(opt => {
      const newOpt = opt.cloneNode(true);
      opt.parentNode.replaceChild(newOpt, opt);
      newOpt.addEventListener('click', (e) => {
        e.stopPropagation();
        sel.querySelectorAll('.option').forEach(o => o.classList.remove('selected'));
        newOpt.classList.add('selected');
        triggerText.textContent = newOpt.textContent;
        sel.classList.remove('open');
        if (hiddenSelect) { hiddenSelect.value = newOpt.dataset.value; hiddenSelect.dispatchEvent(new Event('input')); }
      });
    });
  });
  document.addEventListener('click', () => { document.querySelectorAll('.custom-select').forEach(s => s.classList.remove('open')); });
}

/* ---------- MY POSTS ---------- */
export async function renderMyPosts() {
  hydrateUserOnSidebar();
  await fetchAndGroupClaims();
  let list = [];
  try {
    const res = await fetch('/api/food-posts/mine');
    if (res.ok) list = await res.json();
  } catch (e) { console.error("Failed to load my posts", e); }

  const wrap = byId('mypostsGrid');
  wrap.innerHTML = '';

  if (list.length === 0) {
    byId('emptyMyPosts').style.display = 'block';
    return;
  }
  byId('emptyMyPosts').style.display = 'none';

  list.forEach(p => {
    const card = document.createElement('div');
    card.className = 'my-post-card';
    const pendingCount = p.claims_summary ? p.claims_summary.pending : 0;
    const requestBadge = pendingCount > 0
      ? `<span class="req-count-badge">${pendingCount} request${pendingCount !== 1 ? 's' : ''}</span>`
      : `<span class="req-count-badge zero">0 requests</span>`;

    let dietTags = '';
    try {
      const diet = typeof p.dietary_json === 'string' ? JSON.parse(p.dietary_json) : (p.dietary_json || []);
      dietTags = diet.map(d => `<span class="diet-tag">${d}</span>`).join('');
    } catch (e) { }

    const postClaims = (window._claimsByPost || {})[p.id] || [];

    card.innerHTML = `
      <div class="mp-header">
        <h4>${p.title || p.description || 'Untitled Post'}</h4>
        ${requestBadge}
      </div>
      <div class="mp-body">
        <div class="mp-info">
          <div class="mp-main-row">
            <div class="mp-thumb">🍱</div>
            <div>
              <h5 class="mp-title">${p.title || p.description || 'Untitled'}</h5>
              <div class="mp-meta">
                <span>📦 ${p.quantity || '1 unit'}</span>
              </div>
              <div class="mp-tags">${dietTags}</div>
            </div>
          </div>
          <div class="mp-details">
            <div class="mp-detail-row">📍 ${p.location || 'No location'}</div>
            <div class="mp-detail-row ${isExpired(p.expires_at) ? 'text-danger' : ''}">
              ⏰ ${isExpired(p.expires_at) ? 'Expired' : 'Expires in ' + timeUntil(p.expires_at)}
            </div>
            <div class="mp-detail-row">Status: ${p.status}</div>
          </div>
        </div>

        <div class="mp-requests">
          <h5 class="req-header">👥 Requests</h5>
          <div class="req-list">
            ${postClaims.length === 0 ? '<p class="muted" style="font-size:13px; font-style:italic">No requests yet</p>' : ''}
            ${postClaims.map(c => `
              <div class="req-item">
                <div class="req-user">
                  <div class="req-avatar">👤</div>
                  <div>
                    <div class="req-name">${c.claimer_email.split('@')[0]}</div>
                    <div class="req-email">${c.claimer_email}</div>
                  </div>
                  <span class="req-status ${c.status}">${c.status}</span>
                </div>
                <div class="req-msg">
                  💬 ${c.message || 'I would like to claim this!'}
                </div>
                <div class="req-qty">
                  Requested: ${c.requested_quantity || '1'}
                </div>
                ${c.status === 'pending' ? `
                  <div class="req-actions">
                    <button class="btn-sm primary" onclick="window.handleApprove('${p.id}', '${c.id}')">Approve</button>
                    <button class="btn-sm" onclick="window.handleReject('${p.id}', '${c.id}')">Reject</button>
                  </div>
                ` : ''}
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
    wrap.appendChild(card);
  });

  window.handleApprove = (pid, cid) => approveClaim(pid, cid).then(() => renderMyPosts());
  window.handleReject = (pid, cid) => rejectClaim(pid, cid).then(() => renderMyPosts());
}

async function fetchAndGroupClaims() {
  try {
    const res = await fetch('/api/claims/for-my-posts');
    if (res.ok) {
      const claims = await res.json();
      const byPost = {};
      claims.forEach(c => {
        if (!byPost[c.post_id]) byPost[c.post_id] = [];
        byPost[c.post_id].push(c);
      });
      window._claimsByPost = byPost;
    }
  } catch (e) { console.error("Failed to load claims", e); }
}


/* ---------- REQUESTS ---------- */
export async function renderRequests() {
  hydrateUserOnSidebar();
  const user = getUser();

  // 1. Incoming Requests (For My Posts)
  let incoming = [];
  try {
    const res = await fetch('/api/claims/for-my-posts');
    if (res.ok) incoming = await res.json();
  } catch (e) { console.error(e); }

  const iWrap = byId('reqIncoming');
  if (iWrap) {
    iWrap.innerHTML = '';
    if (incoming.length === 0) {
      iWrap.innerHTML = '<p class="muted">No incoming requests.</p>';
    } else {
      incoming.forEach(c => {
        const p = {
          title: c.post_title,
          location: 'My Post', // Or fetch post details if needed
          expires_at: null, // Not critical here
          ownerEmail: user.email, // I am the owner
          status: c.status
        };
        // Custom card content for incoming request
        const item = document.createElement('div');
        item.className = 'card';
        item.innerHTML = `
                  <div class="thumb">👤</div>
                  <div>
                      <h5>${c.post_title || 'Untitled Post'}</h5>
                      <div class="meta">
                          Requested by: ${c.claimer_email}<br>
                          Qty: ${c.requested_quantity} • Msg: "${c.message || ''}"
                      </div>
                      <div class="actions">
                          ${c.status === 'pending' ? `
                              <button class="btn primary" onclick="window.handleApproveReq('${c.post_id}', '${c.id}')">Approve</button>
                              <button class="btn" onclick="window.handleRejectReq('${c.post_id}', '${c.id}')">Reject</button>
                          ` : `<span class="badge ${c.status}">${c.status}</span>`}
                      </div>
                  </div>
              `;
        iWrap.appendChild(item);
      });
    }
  }

  // 2. Requests I Made
  let myClaims = [];
  try {
    const res = await fetch('/api/claims/mine');
    if (res.ok) myClaims = await res.json();
  } catch (e) { console.error(e); }

  const pWrap = byId('reqPending'); if (pWrap) pWrap.innerHTML = '';
  const hWrap = byId('reqHistory'); if (hWrap) hWrap.innerHTML = '';

  myClaims.forEach(c => {
    const p = {
      title: c.post_title,
      location: c.location,
      expires_at: c.expires_at,
      ownerEmail: c.owner_email,
      status: c.status
    };
    const item = card(p, {
      extra: tag('span', 'badge', c.status === 'pending' ? '⏳ Pending' : (c.status === 'approved' ? '✅ Approved' : '❌ Rejected'))
    });
    if (c.status === 'pending') {
      const cancelBtn = btn('Cancel', 'ghost', () => cancelClaim(c.id));
      item.querySelector('.actions').appendChild(cancelBtn);
      if (pWrap) pWrap.appendChild(item);
    } else {
      if (hWrap) hWrap.appendChild(item);
    }
  });

  window.handleApproveReq = (pid, cid) => approveClaim(pid, cid).then(() => renderRequests());
  window.handleRejectReq = (pid, cid) => rejectClaim(pid, cid).then(() => renderRequests());
}

async function cancelClaim(id) {
  if (!confirm("Cancel this request?")) return;
  try {
    const res = await fetch(`/api/claims/${id}/cancel`, { method: 'PATCH' });
    if (res.ok) renderRequests();
  } catch (e) { alert(e.message); }
}

/* ---------- PROFILE ---------- */
export async function renderProfile() {
  hydrateUserOnSidebar();
  const user = getUser();
  set('#sbUser', user.name || user.email.split('@')[0] || 'Eco Member');
  set('#sbEmail', user.email);

  try {
    const res = await fetch('/api/stats/me');
    if (res.ok) {
      const stats = await res.json();
      set('#kPosts', stats.posts_created);
      set('#kFed', stats.posts_shared);
      set('#kSaved', `${stats.weight_shared_kg.toFixed(1)}kg`);
      set('#kStreak', stats.join_date ? `${Math.floor((new Date() - new Date(stats.join_date)) / (1000 * 60 * 60 * 24))} days` : '0 days');

      set('#impactCO2', `${stats.weight_shared_kg.toFixed(1)} kg`);
      set('#impactMeals', stats.posts_shared);

      set('#actPosts', stats.posts_created);
      set('#actClaims', stats.posts_shared);
      set('#actClaimed', stats.claims_accepted);

      const pts = stats.posts_created * 10 + stats.posts_shared * 20;
      set('#levelPts', `${pts} total points`);
      set('#levelProgress', `${pts}/50 pts`);
      const levelBar = byId('levelBar');
      if (levelBar) levelBar.style.width = Math.min(100, (pts / 50) * 100) + '%';

      const achProgress = Math.min(10, Math.floor(stats.posts_created / 3) + Math.floor(stats.posts_shared / 2));
      set('#achProgress', `${achProgress}/10`);
    }
  } catch (e) { console.error("Profile stats error", e); }
}

/* ---------- small UI helpers ---------- */
function card(p, opts = {}) {
  const root = tag('div', 'card');
  const t = tag('div', 'thumb', '🍱'); root.appendChild(t);
  const body = tag('div'); root.appendChild(body);

  const title = tag('h5', null, p.title || p.description || '(no title)'); body.appendChild(title);
  const meta = tag('div', 'meta', [
    `Category: ${p.category || 'Other'}`, `Qty: ${p.quantity || p.qty || '-'}`, `Location: ${p.location || '-'}`,
    `Expires: ${formatDT(p.expires || p.expires_at)}`
  ].join(' • ')); body.appendChild(meta);

  if (opts.showOwner) {
    body.appendChild(tag('div', 'badge', `👤 ${p.ownerName || p.ownerEmail || 'Unknown'}`));
  }

  const row = tag('div', 'actions'); body.appendChild(row);
  if (opts.cta) { row.appendChild(btn(opts.cta.label, 'primary', opts.cta.click)); }
  if (opts.extra) { row.appendChild(opts.extra); }

  return root;
}
function btn(label, type = 'ghost', click) { const b = tag('button', `btn ${type}`, label); b.onclick = click; return b; }
function tag(el, cls, content) {
  const e = document.createElement(el);
  if (cls) e.className = cls;
  if (content !== undefined) e.innerHTML = content;
  return e;
}
function set(sel, v) { const el = byId(sel.slice(1)); if (el) el.textContent = v; }
function val(id) { const el = byId(id); return el ? el.value : ''; }
function byId(id) { return document.getElementById(id); }
function singular(s) { return s.replace(/s$/, ''); }
function formatDT(iso) { try { return new Date(iso).toLocaleString() } catch { return iso } }
function isExpired(iso) { return new Date(iso) < new Date(); }
function timeUntil(iso) {
  const diff = new Date(iso) - new Date();
  const days = Math.ceil(diff / (1000 * 60 * 60 * 24));
  return days > 0 ? `${days} days` : 'today';
}
function hydrateUserOnSidebar() {
  const u = getUser();
  const w = new MutationObserver(() => {
    const n = document.getElementById('sbUser'); const e = document.getElementById('sbEmail');
    if (n && e) { n.textContent = u.name || 'Eco Member'; e.textContent = u.email; w.disconnect(); }
  });
  w.observe(document.body, { subtree: true, childList: true });
}
