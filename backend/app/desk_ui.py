"""Desk UI — serves a single-page HTML app at /desk/ui.

Matches the showroom's dark theme. Pipeline counts, listing table,
status/note controls, registry editor, sniffer.
"""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()


@router.get("/desk", response_class=HTMLResponse)
def desk_page():
    return DESK_HTML


DESK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Kestrel Desk</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root{--bg:#0c0e14;--bg-card:#161923;--bg-hover:#1c2030;--bg-panel:#12141c;--border:#2a2d3a;--text:#e4e4e7;--text-muted:#8b8d98;--text-dim:#5c5e6b;--accent:#60a5fa;--green:#4ade80;--amber:#fbbf24;--red:#f87171;--radius:8px}
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Inter',-apple-system,sans-serif;background:var(--bg);color:var(--text);line-height:1.5;-webkit-font-smoothing:antialiased}
.desk{max-width:960px;margin:0 auto;padding:1rem 1rem 4rem}
h1{font-size:1.5rem;font-weight:700;margin-bottom:1rem}.brand{color:var(--accent)}
h2{font-size:1rem;font-weight:600;margin:1.5rem 0 0.5rem;color:var(--text-muted)}

/* Pipeline */
.pipeline{display:flex;gap:0.5rem;flex-wrap:wrap;margin-bottom:1.5rem}
.stage{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:0.5rem 1rem;text-align:center;min-width:100px}
.stage .count{font-size:1.5rem;font-weight:700;color:var(--accent)}
.stage .label{font-size:0.7rem;color:var(--text-dim);text-transform:uppercase}

/* Table */
table{width:100%;border-collapse:collapse;font-size:0.82rem}
th{text-align:left;padding:0.4rem 0.5rem;border-bottom:1px solid var(--border);color:var(--text-dim);font-weight:500}
td{padding:0.4rem 0.5rem;border-bottom:1px solid rgba(42,45,58,0.5);vertical-align:top}
tr:hover td{background:var(--bg-hover)}
.score-cell{font-weight:700}

/* Forms */
select,input[type=text],textarea,button{font-family:inherit;font-size:0.82rem;background:var(--bg);border:1px solid var(--border);color:var(--text);border-radius:4px;padding:0.3rem 0.5rem}
select:focus,input:focus,textarea:focus{border-color:var(--accent);outline:none}
button{cursor:pointer;background:var(--accent);color:#0c0e14;font-weight:600;border:none;padding:0.4rem 0.75rem}
button:hover{opacity:0.9}
button.secondary{background:transparent;border:1px solid var(--border);color:var(--text-muted)}
textarea{width:100%;resize:vertical;min-height:60px}
.inline-form{display:flex;gap:0.4rem;align-items:center;margin:0.3rem 0}
.form-row{display:flex;gap:0.5rem;align-items:center;margin-bottom:0.5rem;flex-wrap:wrap}

/* Tags */
.tag{display:inline-block;padding:0.1rem 0.4rem;border-radius:3px;font-size:0.68rem;font-weight:500}
.tag.remote{background:rgba(96,165,250,0.12);color:var(--accent)}

/* Panels */
.panel{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius);padding:1rem;margin-bottom:1rem}
.sniff-result{margin-top:0.5rem;font-size:0.82rem;color:var(--text-muted)}
.sniff-result.success{color:var(--green)}
.sniff-result.fail{color:var(--red)}

/* Tabs */
.tabs{display:flex;gap:0;margin-bottom:1rem;border-bottom:1px solid var(--border)}
.tab{padding:0.5rem 1rem;cursor:pointer;color:var(--text-dim);border-bottom:2px solid transparent;font-size:0.85rem}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}

#msg{position:fixed;top:1rem;right:1rem;background:var(--green);color:#0c0e14;padding:0.4rem 0.75rem;border-radius:4px;font-size:0.8rem;font-weight:600;display:none;z-index:100}
</style>
</head>
<body>
<div class="desk">
<h1><span class="brand">Kestrel</span> Desk</h1>
<div id="msg"></div>

<div id="pipeline" class="pipeline"></div>

<div id="profile-bar" class="form-row" style="margin-bottom:1rem">
  <span style="color:var(--text-dim);font-size:0.8rem">Profile:</span>
  <select id="profile-select" onchange="switchProfile(this.value)" style="font-size:0.8rem"></select>
</div>

<div class="tabs">
  <div class="tab active" onclick="showTab('tracker')">Tracker</div>
  <div class="tab" onclick="showTab('registry')">Registry</div>
  <div class="tab" onclick="showTab('sniffer')">Sniffer</div>
  <div class="tab" onclick="showTab('resumes')">Resumes</div>
</div>

<!-- Tracker Tab -->
<div id="tab-tracker">
<h2>Active Listings</h2>
<table>
<thead><tr><th>Score</th><th>Company</th><th>Title</th><th>Location</th><th>Status</th><th>Actions</th></tr></thead>
<tbody id="listing-rows"></tbody>
</table>
</div>

<!-- Registry Tab -->
<div id="tab-registry" style="display:none">
<h2>Company Registry</h2>
<div class="form-row">
  <input type="text" id="reg-company" placeholder="Company name">
  <select id="reg-platform"><option value="greenhouse">Greenhouse</option><option value="lever">Lever</option><option value="ashby">Ashby</option><option value="recruitee">Recruitee</option></select>
  <input type="text" id="reg-slug" placeholder="Board slug">
  <button onclick="addRegistry()">Add</button>
</div>
<table>
<thead><tr><th>Company</th><th>Platform</th><th>Slug</th><th>Active</th><th></th></tr></thead>
<tbody id="registry-rows"></tbody>
</table>
</div>

<!-- Resumes Tab -->
<div id="tab-resumes" style="display:none">
<h2>Resumes</h2>
<div class="panel">
  <div class="form-row">
    <input type="file" id="resume-file" style="font-size:0.8rem">
    <input type="text" id="resume-label" placeholder="Label (e.g. Fullstack v2)">
    <select id="resume-profile"></select>
    <button onclick="uploadResume()">Upload</button>
  </div>
</div>
<table>
<thead><tr><th>Label</th><th>File</th><th>Profile</th><th>Uploaded</th><th></th></tr></thead>
<tbody id="resume-rows"></tbody>
</table>

<h2 style="margin-top:1.5rem">Portfolio Links</h2>
<div class="form-row">
  <input type="text" id="port-label" placeholder="Label">
  <input type="text" id="port-url" placeholder="https://...">
  <select id="port-profile"></select>
  <button onclick="addPortfolio()">Add</button>
</div>
<table>
<thead><tr><th>Label</th><th>URL</th><th>Profile</th><th></th></tr></thead>
<tbody id="portfolio-rows"></tbody>
</table>
</div>

<!-- Sniffer Tab -->
<div id="tab-sniffer" style="display:none">
<h2>Detect ATS from Careers URL</h2>
<div class="panel">
  <div class="form-row">
    <input type="text" id="sniff-url" placeholder="https://company.com/careers" style="flex:1">
    <button onclick="runSniff()">Detect</button>
  </div>
  <div id="sniff-result" class="sniff-result"></div>
  <div id="sniff-confirm" style="display:none;margin-top:0.75rem">
    <div class="form-row">
      <input type="text" id="sniff-company" placeholder="Company name">
      <button onclick="confirmSniff()">Add to Registry</button>
    </div>
  </div>
</div>
</div>

</div>
<script>
const API = '';
function flash(msg) {
  const el = document.getElementById('msg');
  el.textContent = msg; el.style.display = 'block';
  setTimeout(() => el.style.display = 'none', 2000);
}
function showTab(name) {
  document.querySelectorAll('.tabs .tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('[id^=tab-]').forEach(t => t.style.display = 'none');
  document.getElementById('tab-' + name).style.display = 'block';
  event.target.classList.add('active');
  if (name === 'registry') loadRegistry();
  if (name === 'resumes') { loadResumes(); loadPortfolioLinks(); }
}

// Pipeline
async function loadPipeline() {
  const r = await fetch(API + '/desk/pipeline');
  const d = await r.json();
  const stages = d.stages;
  const order = ['new','interested','applied','responded','interview','closed'];
  document.getElementById('pipeline').innerHTML = order
    .filter(s => stages[s])
    .map(s => `<div class="stage"><div class="count">${stages[s]}</div><div class="label">${s}</div></div>`)
    .join('');
}

// Listings
async function loadListings() {
  const r = await fetch(API + '/listings?per_page=200');
  const d = await r.json();
  const rows = d.listings.filter(l => l.status !== 'new');
  const all = d.listings;
  document.getElementById('listing-rows').innerHTML = (rows.length === 0
    ? '<tr><td colspan="6" style="color:var(--text-dim);text-align:center;padding:2rem">No tracked listings yet. Use the showroom to find listings, then change their status here.</td></tr>'
    : rows.map(l => `<tr>
      <td class="score-cell">${l.score ? l.score.toFixed(0) : '--'}</td>
      <td>${l.company_display}</td>
      <td>${l.title_display}${l.is_remote ? ' <span class="tag remote">Remote</span>' : ''}</td>
      <td style="font-size:0.75rem;color:var(--text-dim)">${l.location_display || ''}</td>
      <td><select onchange="changeStatus(${l.id}, this.value)" style="font-size:0.75rem">
        ${['new','interested','applied','responded','interview','closed'].map(s =>
          `<option value="${s}"${s===l.status?' selected':''}>${s}</option>`).join('')}
      </select></td>
      <td><button class="secondary" onclick="showNoteForm(${l.id})" style="font-size:0.72rem">+ Note</button></td>
    </tr>
    <tr id="note-row-${l.id}" style="display:none"><td colspan="6">
      <div class="inline-form">
        <input type="text" id="note-input-${l.id}" placeholder="Add a note..." style="flex:1">
        <button onclick="addNote(${l.id})" style="font-size:0.72rem">Save</button>
      </div>
    </td></tr>`).join(''));
}

async function changeStatus(id, status) {
  let resume_id = null;
  if (status === 'applied') {
    // Prompt for resume selection
    const r = await fetch(API + '/desk/resumes');
    const d = await r.json();
    if (d.resumes.length > 0) {
      const opts = d.resumes.map(r => `${r.id}: ${r.label} (${r.profile_name})`).join('\\n');
      const pick = prompt('Which resume did you use? Enter ID or leave blank:\\n' + opts);
      if (pick && !isNaN(parseInt(pick))) resume_id = parseInt(pick);
    }
  }
  await fetch(API + `/desk/listings/${id}/status`, {
    method: 'PATCH', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({status, resume_id})
  });
  flash('Status updated');
  loadPipeline(); loadListings();
}

function showNoteForm(id) {
  const row = document.getElementById('note-row-' + id);
  row.style.display = row.style.display === 'none' ? '' : 'none';
}

async function addNote(id) {
  const input = document.getElementById('note-input-' + id);
  if (!input.value.trim()) return;
  await fetch(API + `/desk/listings/${id}/notes`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({content: input.value.trim()})
  });
  input.value = '';
  document.getElementById('note-row-' + id).style.display = 'none';
  flash('Note added');
}

// Registry
async function loadRegistry() {
  const r = await fetch(API + '/desk/registry');
  const d = await r.json();
  document.getElementById('registry-rows').innerHTML = d.companies.map(c => `<tr>
    <td>${c.company}</td><td>${c.platform}</td><td>${c.board_slug}</td>
    <td>${c.active ? '\\u2705' : '\\u274c'}</td>
    <td><button class="secondary" onclick="toggleRegistry(${c.id}, ${!c.active})" style="font-size:0.72rem">${c.active ? 'Deactivate' : 'Activate'}</button></td>
  </tr>`).join('');
}

async function addRegistry() {
  const company = document.getElementById('reg-company').value.trim();
  const platform = document.getElementById('reg-platform').value;
  const slug = document.getElementById('reg-slug').value.trim();
  if (!company || !slug) return;
  await fetch(API + '/desk/registry', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({company, platform, board_slug: slug})
  });
  document.getElementById('reg-company').value = '';
  document.getElementById('reg-slug').value = '';
  flash('Company added'); loadRegistry();
}

async function toggleRegistry(id, active) {
  await fetch(API + `/desk/registry/${id}?active=${active}`, {method: 'PATCH'});
  flash(active ? 'Activated' : 'Deactivated'); loadRegistry();
}

// Sniffer
let lastSniff = null;
async function runSniff() {
  const url = document.getElementById('sniff-url').value.trim();
  if (!url) return;
  document.getElementById('sniff-result').innerHTML = 'Detecting...';
  document.getElementById('sniff-confirm').style.display = 'none';
  const r = await fetch(API + '/desk/sniff', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({url})
  });
  const d = await r.json();
  lastSniff = d;
  if (d.platform && d.board_slug) {
    document.getElementById('sniff-result').innerHTML =
      `<span class="success">Detected: <strong>${d.platform}</strong> / <strong>${d.board_slug}</strong> (${d.confidence} confidence)</span><br>${d.reason}`;
    document.getElementById('sniff-confirm').style.display = 'block';
  } else if (d.platform) {
    document.getElementById('sniff-result').innerHTML =
      `<span class="success">Detected platform: <strong>${d.platform}</strong> but could not extract slug.</span><br>${d.reason}<br>Enter the slug manually below.`;
    document.getElementById('sniff-confirm').style.display = 'block';
  } else {
    document.getElementById('sniff-result').innerHTML =
      `<span class="fail">Could not identify ATS.</span><br>${d.reason}<br>Add manually via the Registry tab.`;
  }
}

async function confirmSniff() {
  if (!lastSniff || !lastSniff.platform) return;
  const company = document.getElementById('sniff-company').value.trim();
  if (!company) return;
  const slug = lastSniff.board_slug || prompt('Enter the board slug:');
  if (!slug) return;
  await fetch(API + '/desk/registry', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({company, platform: lastSniff.platform, board_slug: slug})
  });
  flash('Added to registry');
  document.getElementById('sniff-confirm').style.display = 'none';
  document.getElementById('sniff-url').value = '';
  document.getElementById('sniff-result').innerHTML = '';
  lastSniff = null;
}

// Profiles
let allProfiles = [];
async function loadProfiles() {
  const r = await fetch(API + '/desk/profiles');
  const d = await r.json();
  allProfiles = d.profiles;
  const sel = document.getElementById('profile-select');
  sel.innerHTML = d.profiles.map(p =>
    `<option value="${p.name}"${p.active ? ' selected' : ''}>${p.label}</option>`
  ).join('');
  // Also populate resume/portfolio profile selectors
  for (const id of ['resume-profile', 'port-profile']) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = d.profiles.map(p =>
      `<option value="${p.name}"${p.active ? ' selected' : ''}>${p.label}</option>`
    ).join('');
  }
}

async function switchProfile(name) {
  flash('Rescoring...');
  const r = await fetch(API + '/desk/profiles/switch', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({name})
  });
  const d = await r.json();
  flash(`Profile: ${name} (${d.scored} scored)`);
  loadPipeline(); loadListings();
}

// Resumes
async function loadResumes() {
  const r = await fetch(API + '/desk/resumes');
  const d = await r.json();
  document.getElementById('resume-rows').innerHTML = d.resumes.map(res =>
    `<tr>
      <td>${res.label}</td>
      <td><a href="${API}/desk/resumes/${res.id}/download" target="_blank">${res.filename}</a></td>
      <td>${res.profile_name}</td>
      <td style="font-size:0.72rem;color:var(--text-dim)">${(res.created_at||'').slice(0,10)}</td>
      <td><button class="secondary" onclick="deleteResume(${res.id})" style="font-size:0.72rem">Delete</button></td>
    </tr>`
  ).join('') || '<tr><td colspan="5" style="color:var(--text-dim);text-align:center">No resumes uploaded</td></tr>';
}

async function uploadResume() {
  const file = document.getElementById('resume-file').files[0];
  const label = document.getElementById('resume-label').value.trim();
  const profile = document.getElementById('resume-profile').value;
  if (!file || !label) { flash('Need file and label'); return; }
  const form = new FormData();
  form.append('file', file);
  form.append('label', label);
  form.append('profile_name', profile);
  await fetch(API + '/desk/resumes', { method: 'POST', body: form });
  document.getElementById('resume-label').value = '';
  flash('Resume uploaded'); loadResumes();
}

async function deleteResume(id) {
  await fetch(API + `/desk/resumes/${id}`, { method: 'DELETE' });
  flash('Deleted'); loadResumes();
}

// Portfolio links
async function loadPortfolioLinks() {
  const r = await fetch(API + '/desk/portfolio-links');
  const d = await r.json();
  document.getElementById('portfolio-rows').innerHTML = d.links.map(l =>
    `<tr>
      <td>${l.label}</td>
      <td><a href="${l.url}" target="_blank" style="color:var(--accent)">${l.url.slice(0,40)}...</a></td>
      <td>${l.profile_name}</td>
      <td><button class="secondary" onclick="deletePortfolio(${l.id})" style="font-size:0.72rem">Delete</button></td>
    </tr>`
  ).join('') || '<tr><td colspan="4" style="color:var(--text-dim);text-align:center">No links</td></tr>';
}

async function addPortfolio() {
  const label = document.getElementById('port-label').value.trim();
  const url = document.getElementById('port-url').value.trim();
  const profile = document.getElementById('port-profile').value;
  if (!label || !url) return;
  await fetch(API + '/desk/portfolio-links', {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({label, url, profile_name: profile})
  });
  document.getElementById('port-label').value = '';
  document.getElementById('port-url').value = '';
  flash('Link added'); loadPortfolioLinks();
}

async function deletePortfolio(id) {
  await fetch(API + `/desk/portfolio-links/${id}`, { method: 'DELETE' });
  flash('Deleted'); loadPortfolioLinks();
}

// Init
loadPipeline(); loadListings(); loadProfiles();
</script>
</body>
</html>
"""
