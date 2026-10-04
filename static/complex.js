'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const state = {templates: [], revisions: new Map(), revision: null, preview: null, reportRevision: null,
    roleDrafts: new Map(), result: null, roleLimit: 20, findingLimit: 30, busy: false, dirty: false, roleDirty: false};
  const el = (tag, text, className) => {const n = document.createElement(tag); if (text != null) n.textContent = text; if (className) n.className = className; return n;};
  const option = (value, text) => {const n = el('option', text); n.value = value; return n;};
  const labels = {PASS: 'Passed', FAIL: 'Issues', NOT_CHECKED: 'Not checked', OUT_OF_SCOPE: 'Excluded'};
  function message(text, error = false) {const n = $('message'); n.textContent = text; n.hidden = !text; n.classList.toggle('error', error); if (error) {n.focus(); n.scrollIntoView({block: 'start'});}}
  async function run(task) {
    if (state.busy) return;
    state.busy = true;
    const controls = [...document.querySelectorAll('button,input,select,textarea')].map(n => [n, n.disabled]);
    controls.forEach(([n]) => n.disabled = true); document.querySelector('main').setAttribute('aria-busy', 'true');
    message('Working… Please keep this page open.');
    try {await task();} catch (error) {message(error.message || 'Something went wrong. Please try again.', true);}
    finally {controls.forEach(([n, disabled]) => {if (n.isConnected) n.disabled = disabled;}); state.busy = false; document.querySelector('main').removeAttribute('aria-busy');}
  }
  async function api(path, options = {}) {
    let response;
    try {response = await fetch('/api/v2/templates' + path, {...options, cache: 'no-store'});} catch (_) {throw new Error('Cannot reach the server. Check your connection, then try again. Your unsaved choices are still on this page.');}
    const data = await response.json().catch(() => null);
    if (!response.ok) {
      const detail = data?.detail;
      if (detail?.code === 'REVISION_CONFLICT') throw new Error('This draft changed elsewhere. Your edits have not been saved. Reload the saved revision and review it again.');
      if (detail?.code === 'STALE_ROLE_REVIEW') throw new Error('The report or template changed. Preview the paragraphs again before using these decisions.');
      const error = new Error(typeof detail === 'string' ? detail : detail?.message || `Request could not be completed (${response.status}). Check the selected file and review fields.`);
      error.blockers = detail?.blockers; throw error;
    }
    return data;
  }
  const json = (method, data) => ({method, headers: {'Content-Type': 'application/json'}, body: JSON.stringify(data)});
  const revisionPath = r => `/${r.template_id}/revisions/${r.revision_id}`;
  function show(view) {
    ['templatesPanel','reviewPanel','checkPanel','resultsPanel'].forEach(id => $(id).hidden = id !== view);
    $('formatsNav').setAttribute('aria-current', ['templatesPanel','reviewPanel'].includes(view) ? 'page' : 'false');
    $('reportNav').setAttribute('aria-current', ['checkPanel','resultsPanel'].includes(view) ? 'page' : 'false');
    const heading = $(view).querySelector('h1'); heading.tabIndex = -1; heading.focus(); window.scrollTo(0, 0);
  }
  function fileInput(id) {
    const file = $(id).files[0];
    if (!file || !file.name.toLowerCase().endsWith('.docx')) throw new Error('Choose a Word .docx file.');
    if (!file.size || file.size > 20 * 1024 * 1024) throw new Error('Choose a nonempty file no larger than 20 MB.');
    return file;
  }
  function formFile(file) {const body = new FormData(); body.append('file', file); return body;}
  function valueText(v) {
    if (!v) return 'Unavailable';
    if (v.kind === 'font_family') return `Font: ${v.font}`;
    if (v.kind === 'font_size') return `Font size: ${v.expected_pt} pt`;
    if (v.kind === 'line_spacing_multiple') return `Line spacing: ${v.multiplier}×`;
    if (v.kind === 'page_size') return `Page: ${(v.width_pt * 25.4 / 72).toFixed(1)} × ${(v.height_pt * 25.4 / 72).toFixed(1)} mm`;
    if (v.kind === 'margin') return `${v.side[0].toUpperCase() + v.side.slice(1)} margin: ${(v.expected_pt * 25.4 / 72).toFixed(1)} mm (${v.expected_pt.toFixed(2)} pt)`;
    return Object.entries(v).map(([k,x]) => `${k.replaceAll('_',' ')}: ${Array.isArray(x) ? x.join(', ') : x ?? 'unresolved'}`).join(' · ');
  }
  function field(parent, title, kind, id, value = '') {
    const label = el('label', title); label.htmlFor = id;
    const input = el(kind); input.id = id; if (kind !== 'select') input.value = value;
    parent.append(label, input); return input;
  }
  function reason(parent, id, value = '') {const n = field(parent, 'Reason', 'textarea', id, value); n.maxLength = 2000; n.minLength = 5; return n;}
  function select(parent, title, id, choices, selected = '') {const n = field(parent,title,'select',id); choices.forEach(([v,t]) => n.append(option(v,t))); n.value = selected; return n;}
  function evidence(parent, ids) {
    const details = el('details'); details.append(el('summary','Source evidence'));
    const byId = new Map(state.revision.analysis.evidence.map(e => [e.source_id,e]));
    ids.forEach(id => {const source = byId.get(id); if (source) {details.append(el('p',source.excerpt.slice(0,1500),'excerpt'),el('p',source.path,'hint pad'));}});
    parent.append(details);
  }
  async function loadTemplates() {
    state.templates = await api('');
    const pairs = await Promise.all(state.templates.map(async t => [t.id, await api(`/${t.id}/revisions`)]));
    state.revisions = new Map(pairs); renderTemplates(); renderCheckOptions();
  }
  function renderTemplates() {
    $('formats').replaceChildren();
    if (!state.templates.length) $('formats').append(el('p','No formats yet. Add your format document above to start.','empty'));
    state.templates.forEach(t => {
      const card = el('div',null,'format-card'); card.append(el('strong',t.name),el('p',`Revision ${t.latest_revision_number} · ${t.published_revision_id ? 'Published version available' : 'Needs review'}`,'hint'));
      const button = el('button','Open review','secondary'); button.addEventListener('click',() => run(async () => {
        if (state.dirty && !window.confirm('Open another revision and discard unsaved template edits?')) {message('Your current edits are unchanged.'); return;}
        const revisions = state.revisions.get(t.id); await openRevision(t.id, revisions[0].id); message('Review the requirements and their source evidence.');
      })); card.append(button); $('formats').append(card);
    });
  }
  function renderCheckOptions() {
    const old = $('checkTemplate').value;
    $('checkTemplate').replaceChildren(option('','Choose a published revision'));
    state.templates.forEach(t => (state.revisions.get(t.id) || []).filter(r => r.status === 'PUBLISHED').forEach(r => $('checkTemplate').append(option(`${t.id}/${r.id}`,`${t.name} · revision ${r.number}`))));
    if ([...$('checkTemplate').options].some(o => o.value === old)) $('checkTemplate').value = old;
  }
  async function openRevision(templateId, revisionId) {
    state.revision = await api(`/${templateId}/revisions/${revisionId}`); state.dirty = false;
    renderReview(); show('reviewPanel');
  }
  function renderReview() {
    const r = state.revision; const published = r.status === 'PUBLISHED';
    $('reviewTitle').textContent = r.name; $('revisionStatus').textContent = `Revision ${r.revision_number} · ${published ? 'Published · read only' : 'Draft · changes need saving'}`;
    $('revisionPicker').replaceChildren(...(state.revisions.get(r.template_id) || [{id:r.revision_id, number:r.revision_number,status:r.status}]).map(x => option(x.id,`Revision ${x.number} · ${x.status === 'PUBLISHED' ? 'Published' : 'Draft'}`)));
    $('revisionPicker').value = r.revision_id; $('reviewFields').disabled = published;
    $('saveReview').hidden = published; $('publish').hidden = published; $('fork').hidden = !published; $('useRevision').hidden = !published; $('blockers').hidden = true;
    const decisions = new Map(r.candidate_decisions.map(d => [d.candidate_id,d]));
    $('candidates').replaceChildren();
    const group = el('details'); group.open = true; group.append(el('summary',`Formatting requirements · ${r.analysis.candidates.length}`));
    r.analysis.candidates.forEach((c,i) => {
      const card = el('div',null,'card'); card.append(el('h3',valueText(c.value)),el('p',`${c.origin === 'EXPLICIT_PROSE' ? 'Written instruction' : 'Observed in the template'} · ${c.scope === 'body' ? 'Body text' : 'Document'}${c.condition === 'HEADER_ABSENT' ? ' · Only when no header is used' : ''}`,'chips'));
      evidence(card,c.evidence_ids); const d = decisions.get(c.candidate_id);
      select(card,'Decision',`candidate-${i}`,[['','Choose a decision'],['APPROVE','Approve requirement'],['REJECT','Reject this interpretation'],['DEFER','Defer for later']],d?.action || ''); reason(card,`candidate-reason-${i}`,d?.reason); group.append(card);
    }); $('candidates').append(group);
    $('conflicts').replaceChildren();
    if (r.analysis.conflicts.length) {const note = el('details'); note.append(el('summary',`${r.analysis.conflicts.length} competing interpretations to review`)); r.analysis.conflicts.forEach(c => {const box = el('div',null,'pad'); box.append(el('p',c.explanation)); c.candidate_ids.forEach(id => {const v = r.analysis.candidates.find(c => c.candidate_id === id); if(v) box.append(el('p',`${v.origin === 'EXPLICIT_PROSE' ? 'Written' : 'Observed'}: ${valueText(v.value)}`,'hint'));}); note.append(box);}); $('conflicts').append(note);}
    $('ledger').replaceChildren(); $('ledgerSummary').textContent = `Other instructions · ${r.analysis.requirement_ledger.length}`;
    const ledger = new Map(r.ledger_decisions.map(d => [d.evidence_id,d]));
    r.analysis.requirement_ledger.forEach((entry,i) => {
      const card = el('div',null,'card'); card.append(el('h3',`Instruction ${i+1}`)); evidence(card,[entry.evidence_id]); const d = ledger.get(entry.evidence_id);
      select(card,'How should this instruction be handled?',`ledger-${i}`,[['','Choose a disposition'],['ACKNOWLEDGED_PARTIAL','Partly represented by extracted rules'],['DEFERRED','Defer for later'],['MANUAL','Needs a manual check'],['OUT_OF_SCOPE','Outside this check']],d?.action || ''); reason(card,`ledger-reason-${i}`,d?.reason); $('ledger').append(card);
    });
    $('profilePicker').replaceChildren(option('','Choose a profile'),option('__none','Do not select a chapter profile'),...r.analysis.profiles.map(p => option(p.profile_id,`${p.label === 'report' ? 'Report' : 'Synopsis'} · ${p.chapters.length} chapters`)));
    $('profilePicker').value = r.profile_review ? r.profile_review.profile_id ?? '__none' : '';
    $('profileReason').value = r.profile_review?.reason || ''; renderChapters(r.profile_review);
  }
  function renderChapters(saved = null) {
    $('chapters').replaceChildren();
    const profile = state.revision.analysis.profiles.find(p => p.profile_id === $('profilePicker').value);
    if (!profile) return;
    profile.chapters.forEach((chapter,i) => {
      const old = saved?.chapters.find(c => c.index === i); const card = el('div',null,'card');
      const name = field(card,`Chapter ${i+1} name`,'input',`chapter-name-${i}`,old?.name || chapter.title); name.maxLength = 200;
      select(card,'Required in this report?',`chapter-required-${i}`,[['','Choose requiredness'],['true','Required'],['false','Optional']],old ? String(old.required) : '');
      const aliases = field(card,'Alternative titles (one per line)','textarea',`chapter-aliases-${i}`,old?.aliases.join('\n') || ''); aliases.maxLength = 4020;
      $('chapters').append(card);
    });
  }
  function requiredReason(id) {const value = $(id).value.trim(); if(value.length < 5) {$(id).focus(); throw new Error('Add a reason of at least 5 characters for each selected decision.');} return value;}
  function reviewPatch() {
    const r = state.revision; const patch = {expected_version:r.version,candidates:[],ledger:[]};
    r.analysis.candidates.forEach((c,i) => {const action = $(`candidate-${i}`).value; if(action) patch.candidates.push({candidate_id:c.candidate_id,action,reason:requiredReason(`candidate-reason-${i}`)});});
    r.analysis.requirement_ledger.forEach((c,i) => {const action = $(`ledger-${i}`).value; if(action) patch.ledger.push({evidence_id:c.evidence_id,action,reason:requiredReason(`ledger-reason-${i}`)});});
    const id = $('profilePicker').value;
    if(id) {
      const profile = r.analysis.profiles.find(p => p.profile_id === id);
      patch.profile = {profile_id:id === '__none' ? null : id,reason:requiredReason('profileReason'),chapters:[]};
      profile?.chapters.forEach((c,i) => {
        const name = $(`chapter-name-${i}`).value.trim(); const required = $(`chapter-required-${i}`).value;
        if(!name || !required) throw new Error('Give every chapter a name and choose whether it is required or optional.');
        const aliases = $(`chapter-aliases-${i}`).value.split('\n').map(s=>s.trim()).filter(Boolean);
        if(aliases.length > 20 || aliases.some(s=>s.length > 200)) throw new Error('Use at most 20 alternative titles per chapter, each up to 200 characters.');
        patch.profile.chapters.push({index:i,name,aliases,required:required === 'true'});
      });
    }
    return patch;
  }
  function showBlockers(blockers) {
    const box = $('blockers'); box.replaceChildren(); box.hidden = !blockers.length;
    if(!blockers.length) return;
    box.append(el('strong',`${blockers.length} things need attention before publishing`));
    const counts = {}; blockers.forEach(b => counts[b.code] = (counts[b.code] || 0) + 1);
    const names = {UNREVIEWED_CANDIDATE:'formatting decisions needed',UNREVIEWED_REQUIREMENT:'instruction dispositions needed',PROFILE_REVIEW_REQUIRED:'chapter profile decision needed',CONFLICTING_APPROVALS:'pairs of incompatible values approved',EMPTY_SPECIFICATION:'select at least one requirement or chapter'};
    Object.entries(counts).forEach(([k,v]) => box.append(el('p',`${v} · ${names[k] || k}`)));
    blockers.filter(b=>b.code === 'CONFLICTING_APPROVALS').forEach(b=>{
      const values = b.candidate_ids.map(id=>state.revision.analysis.candidates.find(c=>c.candidate_id===id)).filter(Boolean);
      box.append(el('p','Choose one interpretation or defer it: '+values.map(c=>`${valueText(c.value)} (${c.origin === 'EXPLICIT_PROSE' ? 'written' : 'observed'})`).join(' versus ')));
    });
  }
  async function saveReview() {
    const patch = reviewPatch(); state.revision = await api(revisionPath(state.revision),json('PATCH',patch)); state.dirty = false; renderReview();
    const blockers = await api(revisionPath(state.revision)+'/blockers'); showBlockers(blockers.blockers); return blockers;
  }
  function clearReport() {state.preview = null; state.reportRevision = null; state.roleDrafts.clear(); state.roleDirty = false; state.result = null; $('roles').replaceChildren(); $('findings').replaceChildren(); $('rolePanel').hidden = true;}
  async function selectedReport() {
    const choice = $('checkTemplate').value; if(!choice) throw new Error('Choose a published format revision first.');
    const [template, revision] = choice.split('/'); const file = fileInput('reportInput');
    const r = await api(`/${template}/revisions/${revision}`); return {file,r};
  }
  async function previewRoles() {
    const {file,r} = await selectedReport();
    if(state.roleDirty && !window.confirm('Preview again and discard unsaved paragraph decisions?')) {message('Your paragraph decisions are unchanged.'); return;}
    const preview = await api(revisionPath(r)+'/role-preview',{method:'POST',body:formFile(file)});
    state.preview = preview; state.reportRevision = r; state.roleDrafts.clear(); state.roleDirty = false; state.roleLimit = 20;
    $('rolePanel').hidden = false; renderRoles(); message('Paragraph suggestions are ready. Only your explicit decisions will be used.');
  }
  function renderRoles() {
    const preview = state.preview; if(!preview) return;
    const all = preview.paragraphs.filter(p => $('roleFilter').value === 'all' || p.reviewable);
    $('roles').replaceChildren(); $('roleCount').textContent = `${all.length} paragraphs in this view · ${state.roleDrafts.size} decisions started${preview.structural_uncertainty ? ' · Some document structure remains uncertain' : ''}`;
    all.slice(0,state.roleLimit).forEach(p => {
      const card = el('article',null,'card'); card.append(el('h3',`Paragraph ${p.paragraph_index+1}`),el('p',p.excerpt || '(No text)','excerpt'));
      if(p.excerpt_truncated) card.append(el('p','Excerpt shortened. Read the full paragraph in your document.','hint'));
      card.append(el('p',p.proposal_reason,'hint'));
      if(p.suggested_role) card.append(el('p',`Suggestion only: ${p.suggested_role === 'BODY' ? 'Body prose' : 'Chapter '+(p.suggested_chapter_index+1)}`,'chips'));
      if(!p.reviewable) {card.append(el('p',`Detected: ${p.detected_role.replaceAll('_',' ').toLowerCase()} · no override available`,'hint')); $('roles').append(card); return;}
      const draft = state.roleDrafts.get(p.paragraph_index) || {role:'',chapter:'',reason:''};
      const choice = select(card,'Confirmed role',`role-${p.paragraph_index}`,[['','Leave unresolved'],['BODY','Body prose'],['CHAPTER','Chapter heading'],['EXCLUDE','Exclude from body/chapter checks']],draft.role);
      const chapter = select(card,'Which chapter?',`role-chapter-${p.paragraph_index}`,[['','Choose a chapter'],...(state.reportRevision.publication.profile?.chapters || []).map(c => [String(c.index),`${c.index+1}. ${c.name}`])],draft.chapter);
      const why = reason(card,`role-reason-${p.paragraph_index}`,draft.reason);
      const visibility = () => {chapter.hidden = choice.value !== 'CHAPTER'; chapter.previousElementSibling.hidden = chapter.hidden; why.hidden = !choice.value; why.previousElementSibling.hidden = why.hidden;}; visibility();
      const store = () => {state.roleDirty = true; if(choice.value) state.roleDrafts.set(p.paragraph_index,{role:choice.value,chapter:chapter.value,reason:why.value}); else state.roleDrafts.delete(p.paragraph_index); visibility(); $('roleCount').textContent = `${all.length} paragraphs in this view · ${state.roleDrafts.size} decisions started${preview.structural_uncertainty ? ' · Some document structure remains uncertain' : ''}`;};
      choice.addEventListener('change',store); chapter.addEventListener('change',store); why.addEventListener('input',store); $('roles').append(card);
    });
    if(!all.length) $('roles').append(el('p','No unresolved paragraphs are eligible for manual assignment. You can check the supported styles directly.','hint'));
    $('moreRoles').hidden = all.length <= state.roleLimit;
  }
  function roleReview() {
    if(!state.preview || !state.roleDrafts.size) return null;
    const decisions = [...state.roleDrafts].map(([index,d]) => {
      const p = state.preview.paragraphs.find(p => p.paragraph_index === index);
      if(d.reason.trim().length < 5) throw new Error(`Add a reason for paragraph ${index+1}.`);
      if(d.role === 'CHAPTER' && d.chapter === '') throw new Error(`Choose a chapter for paragraph ${index+1}.`);
      return {paragraph_index:index,source_path:p.source_path,role:d.role,chapter_index:d.role === 'CHAPTER' ? Number(d.chapter) : null,reason:d.reason.trim()};
    });
    return {report_sha256:state.preview.report_sha256,snapshot_sha256:state.preview.snapshot_sha256,decisions};
  }
  async function checkReport() {
    const {file,r} = await selectedReport(); const review = roleReview(); const body = formFile(file); if(review) body.append('role_review',JSON.stringify(review));
    const result = await api(revisionPath(r)+'/check',{method:'POST',body});
    state.result = result; state.reportRevision = r; state.findingLimit = 30; state.roleDirty = false; $('resultFilter').value = 'ALL'; renderResults(); show('resultsPanel'); message('Check complete. Review both issues and items that could not be checked.');
  }
  function renderResults() {
    const r = state.result;
    const titles = {FAIL:'Formatting issues found',INDETERMINATE:'Some requirements remain unchecked',PASS_SUPPORTED_CHECKS:'Supported checks passed'};
    $('resultTitle').textContent = titles[r.outcome] || 'Review this result';
    $('resultMeaning').textContent = r.outcome === 'FAIL' ? 'Fix the identified issues. Unchecked requirements still need review.' : r.outcome === 'INDETERMINATE' ? 'No supported violation was found, but this report cannot be confirmed fully compliant.' : 'The evaluated requirements matched. This is not a guarantee of full template compliance.';
    $('resultCounts').replaceChildren(); Object.entries(labels).forEach(([key,label]) => {const box = el('div',label,key === 'FAIL' ? 'issue' : ''); box.prepend(el('strong',String(r.counts[key] || 0))); $('resultCounts').append(box);});
    $('resultIdentity').textContent = `${state.reportRevision.name} · revision ${state.reportRevision.revision_number} · checker ${r.checker_version} · ${r.role_decisions.length} manual role decisions`;
    $('limitations').replaceChildren(...r.limitations.map(t=>el('li',t))); renderFindings();
  }
  function renderFindings() {
    const filter = $('resultFilter').value; const items = state.result.items.filter(i => filter === 'ALL' || i.status === filter);
    $('findings').replaceChildren();
    items.slice(0,state.findingLimit).forEach(item => {
      const box = el('article',null,`finding ${item.status}`); const loc = item.paragraph_index != null ? ` · Paragraph ${item.paragraph_index+1}${item.run_index != null ? ', run '+(item.run_index+1) : ''}` : item.section_index != null ? ` · Section ${item.section_index+1}` : '';
      box.append(el('h3',(labels[item.status] || 'Unknown state')+loc),el('p',item.message));
      if(item.expected || item.actual) {const details = el('details'); details.append(el('summary','Expected and actual')); if(item.expected) details.append(el('p','Expected: '+valueText(item.expected),'value-pair')); if(item.actual) details.append(el('p','Actual: '+valueText(item.actual),'value-pair')); box.append(details);}
      const proof = el('details'); proof.append(el('summary','Evidence and location'));
      if(item.source_path) proof.append(el('p',item.source_path,'hint pad wordbreak'));
      item.evidence_ids.forEach(id => {const e = state.reportRevision.analysis.evidence.find(e => e.source_id === id); if(e) proof.append(el('p',e.excerpt,'excerpt'));});
      if(!item.source_path && !item.evidence_ids.length) proof.append(el('p','Document-wide requirement or review disposition.','hint pad'));
      box.append(proof); $('findings').append(box);
    });
    if(!items.length) $('findings').append(el('p','No findings in this category.','empty'));
    $('moreFindings').hidden = items.length <= state.findingLimit;
  }
  document.querySelectorAll('[data-view]').forEach(button => button.addEventListener('click',() => {if(!state.busy) {show(button.dataset.view); message('');}}));
  $('refresh').addEventListener('click',() => run(async()=>{await loadTemplates(); message('Formats refreshed.');}));
  $('uploadFormat').addEventListener('submit',event=>{event.preventDefault(); run(async()=>{const body=formFile(fileInput('formatFile')); body.append('name',$('formatName').value.trim()); const r=await api('',{method:'POST',body}); await loadTemplates(); state.revision=r; state.dirty=false; renderReview(); show('reviewPanel'); $('uploadFormat').reset(); message('Format uploaded. Review every proposed requirement before publishing.');});});
  $('reviewForm').addEventListener('input',()=>state.dirty=true);
  $('reviewForm').addEventListener('change',()=>state.dirty=true);
  $('profilePicker').addEventListener('change',()=>renderChapters());
  $('reviewForm').addEventListener('submit',event=>{event.preventDefault();run(async()=>{await saveReview();message('Review saved. Any remaining publication blockers are shown below.');});});
  $('publish').addEventListener('click',()=>run(async()=>{const blockers=await saveReview();if(!blockers.can_publish){message('Review saved, but publication needs more decisions. See the blockers below.',true);return;}state.revision=await api(revisionPath(state.revision)+'/publish',json('POST',{expected_version:state.revision.version}));await loadTemplates();renderReview();message('Revision published. It is ready for supported report checks.');}));
  $('fork').addEventListener('click',()=>run(async()=>{state.revision=await api(revisionPath(state.revision)+'/fork',{method:'POST'});await loadTemplates();renderReview();message('New draft created. The previous published revision is unchanged.');}));
  $('revisionPicker').addEventListener('change',()=>run(async()=>{const id=$('revisionPicker').value;if(state.dirty&&!window.confirm('Discard unsaved edits and open this revision?')){$('revisionPicker').value=state.revision.revision_id;message('Your edits are unchanged.');return;}await openRevision(state.revision.template_id,id);message('Saved revision loaded.');}));
  $('reloadRevision').addEventListener('click',()=>run(async()=>{if(state.dirty&&!window.confirm('Discard local edits and reload the saved revision?')){message('Your edits are unchanged.');return;}await openRevision(state.revision.template_id,state.revision.revision_id);message('Saved revision loaded.');}));
  $('useRevision').addEventListener('click',()=>{clearReport();$('checkTemplate').value=`${state.revision.template_id}/${state.revision.revision_id}`;show('checkPanel');message('Choose a report for this published revision.');});
  $('checkTemplate').addEventListener('change',clearReport);$('reportInput').addEventListener('change',clearReport);
  $('reportForm').addEventListener('submit',event=>{event.preventDefault();run(previewRoles);});
  $('checkReport').addEventListener('click',()=>run(checkReport));$('reviewedCheck').addEventListener('click',()=>run(checkReport));
  $('roleFilter').addEventListener('change',()=>{state.roleLimit=20;renderRoles();});$('moreRoles').addEventListener('click',()=>{state.roleLimit+=20;renderRoles();});
  $('resultFilter').addEventListener('change',()=>{state.findingLimit=30;renderFindings();});$('moreFindings').addEventListener('click',()=>{state.findingLimit+=30;renderFindings();});
  $('downloadResult').addEventListener('click',()=>{const blob=new Blob([JSON.stringify(state.result,null,2)],{type:'application/json'});const url=URL.createObjectURL(blob);const a=el('a');a.href=url;a.download='reportlint-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
  window.addEventListener('beforeunload',event=>{if(state.dirty||state.roleDirty){event.preventDefault();event.returnValue='';}});
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(()=>{});
  show('templatesPanel');run(async()=>{await loadTemplates();message('Ready. Choose a saved format or add a new one.');});
})();
