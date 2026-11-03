'use strict';
const $ = id => document.getElementById(id);
let currentRun = null;
let busy = false;
const examples = {
  billing: 'I was charged twice for my subscription. Both payments have settled. What should I do about the duplicate charge?',
  account: 'I cannot log in to my account and my password reset link has expired. How can I get access again?',
  security: 'I think my account has been hacked and an API key was stolen. What should I do immediately?'
};
const show = (id, visible = true) => $(id).classList.toggle('hidden', !visible);
const element = (tag, text, className) => { const e = document.createElement(tag); if (text !== undefined) e.textContent = text; if (className) e.className = className; return e; };
function notify(message) { $('notification').textContent = message; show('notification'); clearTimeout(notify.timer); notify.timer = setTimeout(() => show('notification', false), 3500); }
async function api(path, options = {}) {
  const token = sessionStorage.getItem('supportforge-token');
  const response = await fetch('/api' + path, { ...options, headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: 'Bearer ' + token } : {}), ...options.headers } });
  const data = await response.json();
  if (!response.ok) {
    if (response.status === 401) show('settings');
    throw new Error(typeof data.detail === 'string' ? data.detail : 'Please check the request fields and try again.');
  }
  return data;
}
function showError(error) { $('error').textContent = error.message || 'Something went wrong. Please try again.'; show('error'); }
function setBusy(value) {
  busy = value;
  $('run-button').disabled = value;
  $('approve').disabled = value;
  $('reject').disabled = value;
  $('output-status').textContent = value ? 'WORKING' : (currentRun ? currentRun.status.toUpperCase() : 'READY');
}
function selectTab(name) {
  document.querySelectorAll('[data-tab]').forEach(button => {
    const selected = button.dataset.tab === name;
    button.setAttribute('aria-selected', String(selected));
    show('panel-' + button.dataset.tab, selected);
  });
}
function renderRun(run) {
  currentRun = run;
  show('output-empty', false); show('output-loading', false); show('error', false); show('output-result');
  $('output-status').textContent = run.status.toUpperCase();
  $('triage').replaceChildren(element('span', run.triage.category.toUpperCase(), 'pill'), element('span', run.triage.priority.toUpperCase(), 'pill ' + run.triage.priority), element('span', run.triage.queue, 'pill'));
  $('answer').textContent = run.answer;
  $('source-count').textContent = run.sources.length;
  $('review-reasons').textContent = run.review_reasons.join(' · ');
  $('panel-sources').replaceChildren(...run.sources.map(source => {
    const details = element('details', undefined, 'source');
    details.append(element('summary', source.title), element('small', source.document + ' · ' + source.id), element('p', source.excerpt)); return details;
  }));
  if (!run.sources.length) $('panel-sources').append(element('p', 'No matching policy. Escalate to a support specialist.', 'knowledge-note'));
  $('panel-trace').replaceChildren(...run.trace.map((event, index) => {
    const row = element('div', undefined, 'trace-item'); const text = element('div');
    text.append(element('strong', event.step), element('p', event.detail));
    row.append(element('span', String(index + 1).padStart(2, '0'), 'trace-number'), text); return row;
  }));
  show('review-controls', run.status === 'pending'); show('review-outcome', run.status !== 'pending');
  $('review-outcome').textContent = run.status === 'approved' ? 'Approved · Local ticket ' + run.ticket_id + ' created. No message was sent.' : 'Rejected · No ticket was created.';
  selectTab('draft');
}
async function refresh() {
  const [meta, runs, docs] = await Promise.all([api('/meta'), api('/runs'), api('/knowledge')]);
  $('stat-runs').textContent = meta.stats.runs; $('stat-chunks').textContent = meta.stats.knowledge_chunks; $('stat-tickets').textContent = meta.stats.tickets;
  $('stat-mode').textContent = meta.mode === 'demo' ? 'Demo' : 'Live AI';
  $('mode-badge').textContent = meta.mode === 'demo' ? 'DEMO MODE' : 'LIVE AI';
  $('health-label').textContent = meta.mode === 'demo' ? 'Local demo workspace' : 'Live model configured';
  $('mode-description').textContent = meta.mode === 'demo' ? 'No API key. No model charges.' : 'Model: ' + meta.model;
  $('connection-state').textContent = 'Workspace connected';
  $('history-count').textContent = runs.length; show('history-empty', !runs.length); show('history-table', runs.length > 0);
  $('history-body').replaceChildren(...runs.map(run => {
    const row = element('tr'); const nameCell = element('td'); const button = element('button', undefined, 'history-open');
    button.type = 'button'; button.append(element('strong', run.request.customer_name), element('p', run.request.message));
    button.addEventListener('click', () => { if (!busy) { renderRun(run); $('customer').value = run.request.customer_name; $('message').value = run.request.message; updateCount(); $('workbench').scrollIntoView({behavior: 'smooth'}); } });
    nameCell.append(button); const status = element('td'); status.append(element('span', run.status, 'pill ' + run.status));
    row.append(nameCell, element('td', run.triage.category), status, element('td', new Date(run.created_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}))); return row;
  }));
  $('documents').replaceChildren(...docs.map(doc => {
    const row = element('div', undefined, 'document'); const text = element('div');
    text.append(element('span', doc.title), element('small', doc.document));
    row.append(element('span', '▤'), text, element('span', doc.chunks + ' excerpts')); return row;
  }));
}
function updateCount() { $('character-count').textContent = $('message').value.length.toLocaleString() + ' / 6,000'; }
$('message').addEventListener('input', updateCount);
document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => { $('message').value = examples[button.dataset.example]; updateCount(); $('message').focus(); }));
document.querySelectorAll('[data-tab]').forEach(button => button.addEventListener('click', () => selectTab(button.dataset.tab)));
$('request-form').addEventListener('submit', async event => {
  event.preventDefault(); if (busy) return;
  setBusy(true); show('error', false); show('output-empty', false); show('output-result', false); show('output-loading');
  try {
    const run = await api('/runs', {method:'POST', headers:{'Idempotency-Key': crypto.randomUUID()}, body:JSON.stringify({customer_name:$('customer').value, message:$('message').value})});
    renderRun(run); await refresh();
  } catch (error) { show('output-loading', false); show('output-empty'); showError(error); }
  finally { setBusy(false); }
});
async function review(decision) {
  if (busy || !currentRun) return;
  if (!$('reviewer').value.trim()) { $('reviewer').focus(); notify('Enter a reviewer name before making a decision.'); return; }
  setBusy(true); show('error', false);
  try { renderRun(await api('/runs/' + currentRun.id + '/review', {method:'POST', body:JSON.stringify({decision, reviewer:$('reviewer').value, note:$('review-note').value})})); await refresh(); notify(decision === 'approve' ? 'Local ticket created. Nothing was sent.' : 'Request rejected.'); }
  catch (error) { showError(error); }
  finally { setBusy(false); }
}
$('approve').addEventListener('click', () => review('approve'));
$('reject').addEventListener('click', () => review('reject'));
$('copy-draft').addEventListener('click', async () => { try { await navigator.clipboard.writeText(currentRun.answer); notify('Draft copied. Review it before sending.'); } catch { notify('Clipboard unavailable. Select and copy the draft text.'); } });
$('refresh-history').addEventListener('click', () => refresh().catch(showError));
$('settings-toggle').addEventListener('click', () => show('settings', $('settings').classList.contains('hidden')));
$('save-token').addEventListener('click', async () => { sessionStorage.setItem('supportforge-token', $('api-token').value.trim()); $('api-token').value = ''; try { await refresh(); show('settings', false); show('error', false); notify('Workspace connected.'); } catch(error) { showError(error); } });
refresh().catch(error => { $('connection-state').textContent = 'Connection needs attention'; showError(error); });
