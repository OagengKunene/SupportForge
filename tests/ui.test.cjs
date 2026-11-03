const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve } = require('node:path');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');
const { parseHTML } = require('linkedom');

const root = resolve(__dirname, '..');
const html = readFileSync(resolve(root, 'src/supportforge/static/index.html'), 'utf8');
const script = readFileSync(resolve(root, 'src/supportforge/static/app.js'), 'utf8');
const malicious = '<img src=x onerror="globalThis.compromised=true">';

async function tick() { for (let i = 0; i < 8; i++) await new Promise(setImmediate); }
function setup({ locked = false, failDraft = false } = {}) {
  const { window, document } = parseHTML(html);
  const requests = [];
  const memory = new Map();
  let runs = [];
  const mockFetch = async (path, options = {}) => {
    requests.push({ path, options });
    if (locked && options.headers.Authorization !== 'Bearer test-operator-token') {
      return { ok: false, status: 401, json: async () => ({ detail: 'Valid API token required' }) };
    }
    let data;
    if (path === '/api/meta') data = { mode: 'demo', stats: { runs: runs.length, knowledge_chunks: 10, tickets: runs.filter(r => r.status === 'approved').length } };
    else if (path === '/api/knowledge') data = [{ document: 'billing.md', title: 'Billing policy', chunks: 2 }];
    else if (path === '/api/runs' && options.method === 'POST') {
      if (failDraft) return { ok: false, status: 502, json: async () => ({ detail: 'Model draft failed' }) };
      const request = JSON.parse(options.body);
      data = { id: randomUUID(), created_at: '2026-11-03T10:00:00+00:00', mode: 'demo', request,
        triage: { category: 'billing', priority: 'normal', queue: 'Billing operations' },
        answer: 'Review this draft ' + malicious,
        sources: [{ id: 'kb-demo', title: 'Billing policy', document: 'billing.md', excerpt: 'Approved policy ' + malicious }],
        citation_ids: ['kb-demo'], review_reasons: ['Human review required'],
        trace: [{ step: 'retrieve', detail: 'Knowledge.search → 1 policy excerpt' }],
        status: 'pending', ticket_id: null };
      runs = [data, ...runs];
    } else if (path.endsWith('/review')) {
      const decision = JSON.parse(options.body).decision;
      data = { ...runs[0], status: decision === 'approve' ? 'approved' : 'rejected', ticket_id: decision === 'approve' ? 'SF-TEST' : null };
      runs[0] = data;
    } else if (path === '/api/runs') data = runs;
    else throw new Error('Unexpected API path: ' + path);
    return { ok: true, status: 200, json: async () => structuredClone(data) };
  };
  const context = vm.createContext({
    document, fetch: mockFetch, crypto: { randomUUID },
    sessionStorage: { getItem: key => memory.get(key), setItem: (key, value) => memory.set(key, value) },
    navigator: { clipboard: { writeText: async text => { memory.set('clipboard', text); } } },
    setTimeout: () => 1, clearTimeout: () => {}, console
  });
  vm.runInContext('globalThis.HTMLElement = undefined', context);
  window.HTMLElement.prototype.focus = function () {};
  window.HTMLElement.prototype.scrollIntoView = function () {};
  vm.runInContext(script, context);
  const $ = id => document.getElementById(id);
  const click = id => $(id).dispatchEvent(new window.Event('click'));
  const submit = async () => {
    $('customer').value = malicious;
    $('message').value = 'I was charged twice for an invoice';
    $('request-form').dispatchEvent(new window.Event('submit', { cancelable: true }));
    await tick();
  };
  return { $, document, requests, click, submit, memory };
}

test('loads workspace metrics and knowledge documents', async () => {
  const ui = setup(); await tick();
  assert.equal(ui.$('stat-chunks').textContent, '10');
  assert.equal(ui.$('stat-mode').textContent, 'Demo');
  assert.match(ui.$('documents').textContent, /Billing policy/);
  assert.equal(ui.$('output-empty').classList.contains('hidden'), false);
});

test('sample questions populate the request without submitting it', async () => {
  const ui = setup(); await tick();
  ui.document.querySelector('[data-example="billing"]').dispatchEvent(new (parseHTML('').window.Event)('click'));
  assert.match(ui.$('message').value, /Both payments have settled/);
  assert.equal(ui.requests.some(r => r.options.method === 'POST'), false);
});

test('draft rendering treats model and customer strings as text', async () => {
  const ui = setup(); await tick(); await ui.submit();
  assert.equal(ui.$('output-result').classList.contains('hidden'), false);
  assert.match(ui.$('answer').textContent, /<img/);
  assert.equal(ui.$('answer').querySelector('img'), null);
  assert.equal(ui.$('history-body').querySelector('img'), null);
  assert.equal(ui.$('panel-sources').querySelector('img'), null);
  const post = ui.requests.find(r => r.options.method === 'POST');
  assert.ok(post.options.headers['Idempotency-Key']);
  ui.click('tab-sources');
  assert.equal(ui.$('panel-sources').classList.contains('hidden'), false);
  assert.equal(ui.$('tab-sources').getAttribute('aria-selected'), 'true');
});

test('review requires a name and approval updates local ticket state', async () => {
  const ui = setup(); await tick(); await ui.submit();
  ui.click('approve'); await tick();
  assert.equal(ui.requests.filter(r => r.path.endsWith('/review')).length, 0);
  assert.match(ui.$('notification').textContent, /reviewer name/);
  ui.$('reviewer').value = 'Test Operator';
  ui.click('approve'); await tick();
  assert.match(ui.$('review-outcome').textContent, /SF-TEST/);
  assert.equal(ui.$('review-controls').classList.contains('hidden'), true);
  assert.equal(ui.$('stat-tickets').textContent, '1');
});

test('token gate can be resolved without embedding a token in the page', async () => {
  const ui = setup({ locked: true }); await tick();
  assert.equal(ui.$('settings').classList.contains('hidden'), false);
  ui.$('api-token').value = 'test-operator-token';
  ui.click('save-token'); await tick();
  assert.equal(ui.$('api-token').value, '');
  assert.equal(ui.$('settings').classList.contains('hidden'), true);
  assert.equal(ui.memory.get('supportforge-token'), 'test-operator-token');
  assert.equal(ui.$('connection-state').textContent, 'Workspace connected');
});

test('a failed model draft displays an error and re-enables the submit button', async () => {
  const ui = setup({ failDraft: true }); await tick(); await ui.submit();
  assert.equal(ui.$('error').classList.contains('hidden'), false);
  assert.match(ui.$('error').textContent, /Model draft failed/);
  assert.equal(ui.$('run-button').disabled, false);
  assert.equal(ui.$('output-loading').classList.contains('hidden'), true);
});
