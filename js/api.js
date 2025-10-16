// LocalStorage helpers
const LS_POSTS = 'ecobite_posts';
const LS_USER  = 'ecobite_user';

function uid() { return Math.random().toString(36).slice(2, 9); }
function nowISO(){ return new Date().toISOString(); }

function readPosts(){
  try { return JSON.parse(localStorage.getItem(LS_POSTS)) || []; }
  catch { return []; }
}
function writePosts(list){ localStorage.setItem(LS_POSTS, JSON.stringify(list)); }

export function getUser(){
  return JSON.parse(localStorage.getItem(LS_USER) || '{"name":"Student","email":"student@campus.edu"}');
}

export async function listPosts(){
  return readPosts();
}

export async function createPost(data){
  const user = getUser();
  const post = {
    id: uid(),
    ownerEmail: user.email,
    ownerName: user.name || user.email.split('@')[0],
    title: data.title,
    category: data.category,
    qty: data.qty || '',
    diet: data.diet || [],
    location: data.location,
    expires: data.expires,          // ISO date string
    createdAt: nowISO(),
    status: 'available',            // available | claimed | expired
    claims: []                      // array of {byEmail, status: pending/approved/rejected}
  };
  const list = readPosts();
  list.unshift(post);
  writePosts(list);
  return post;
}

export async function claimPost(postId){
  const user = getUser();
  const list = readPosts();
  const p = list.find(x=>x.id===postId);
  if(!p) throw new Error('Not found');
  p.claims.push({ id: uid(), byEmail:user.email, status:'pending', createdAt: nowISO() });
  writePosts(list);
  return p;
}

export async function approveClaim(postId, claimId){
  const list = readPosts();
  const p = list.find(x=>x.id===postId);
  if(!p) throw new Error('Not found');
  const c = p.claims.find(c=>c.id===claimId);
  if(!c) throw new Error('Claim not found');
  c.status = 'approved';
  p.status = 'claimed';
  writePosts(list);
  return p;
}

export async function rejectClaim(postId, claimId){
  const list = readPosts();
  const p = list.find(x=>x.id===postId);
  const c = p?.claims.find(c=>c.id===claimId);
  if(c){ c.status='rejected'; writePosts(list); }
  return p;
}

export function computeStats(){
  const list = readPosts();
  // expire automatically
  const now = new Date();
  list.forEach(p=>{
    if(p.status==='available' && new Date(p.expires) < now){ p.status='expired'; }
  });
  writePosts(list);

  const available = list.filter(p=>p.status==='available').length;
  const total = list.length;
  const shared = list.filter(p=>p.status==='claimed').length;
  const savedKg = (shared * 1.2).toFixed(1); // pretend each post saves ~1.2kg
  return {available, total, shared, savedKg, list};
}
