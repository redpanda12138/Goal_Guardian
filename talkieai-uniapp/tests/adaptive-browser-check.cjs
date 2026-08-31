// Run against a fresh H5 build. All API traffic is fulfilled locally.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(process.argv[2]);
const screenshots = path.resolve(process.argv[3]);
const server = http.createServer((req, res) => {
  const file = path.resolve(root, '.' + decodeURIComponent(req.url.split('?')[0] === '/' ? '/index.html' : req.url.split('?')[0]));
  if (!file.startsWith(root + path.sep)) { res.writeHead(403).end(); return; }
  fs.readFile(file, (error, data) => {
    if (error) { res.writeHead(404).end(); return; }
    res.setHeader('Content-Type', file.endsWith('.js') ? 'application/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
    res.end(data);
  });
});
(async () => {
  await new Promise(resolve => server.listen(8137, '127.0.0.1', resolve));
  const browser = await chromium.launch({ headless: true, channel: 'chrome' });
  try {
    const context = await browser.newContext();
    let state = { workflow_mode: 'adaptive_v1', workflow_version: 'oa_adaptive_v1', session_generation: 1,
      session_status: 'active', recovery_requested: true, stage_count: 7, turn_index: 7 };
    const commands = [], errors = [];
    await context.route('**/*', async route => {
      const url = new URL(route.request().url());
      if (url.origin === 'http://127.0.0.1:8137') return route.continue();
      if (!url.pathname.startsWith('/api/v1/')) return route.abort();
      let data = {};
      if (url.pathname.endsWith('/sessions/demo')) data = { id: 'demo', type: 'MAS', messages: { total: 1, list: [{ id: 'm1', role: 'ASSISTANT', content: 'There are still review items to discuss.', style: '' }] } };
      else if (url.pathname.endsWith('/mas/sessions/current')) data = state;
      else if (url.pathname.endsWith('/mas/sessions/control')) {
        const body = route.request().postDataJSON();
        commands.push(body.command);
        assert.equal(body.session_id, 'demo');
        assert.equal(body.session_generation, 1);
        state = { ...state, status: 'ok', recovery_requested: false,
          session_status: body.command === 'pause' ? 'paused' : 'active' };
        data = state;
      } else if (url.pathname.includes('settings')) data = { auto_playing_voice: 0, auto_text_shadow: 0, auto_pronunciation: 0 };
      await route.fulfill({ status: 200, contentType: 'application/json', headers: { 'Access-Control-Allow-Origin': '*' }, body: JSON.stringify({ code: '200', status: 'SUCCESS', data }) });
    });
    const page = await context.newPage();
    page.on('pageerror', error => errors.push(error.message));
    page.on('console', event => { if (event.type() === 'error') console.error('Browser:', event.text()); });
    for (const width of [320, 768, 1024, 1440]) {
      state = { ...state, session_status: 'active', recovery_requested: true };
      await page.setViewportSize({ width, height: 900 });
      await page.goto('http://127.0.0.1:8137/#/pages/chat/index?sessionId=demo');
      await page.reload();
      try {
        await page.getByRole('button', { name: 'Two more replies', exact: true }).waitFor({ timeout: 10000 });
      } catch (error) {
        console.error('Observed UI:', await page.locator('body').innerText(), errors);
        await page.screenshot({ path: path.join(screenshots, 'failed.png'), fullPage: true });
        throw error;
      }
      await page.screenshot({ path: path.join(screenshots, `adaptive-${width}.png`), fullPage: true });
      await page.getByRole('button', { name: 'Two more replies', exact: true }).click();
      await page.getByRole('button', { name: 'Pause', exact: true }).click();
      await page.getByRole('button', { name: 'Resume', exact: true }).waitFor();
      assert.equal(await page.locator('.chat-bottom-container').count(), 0);
      await page.getByRole('button', { name: 'Resume', exact: true }).click();
      await page.getByRole('button', { name: 'Pause', exact: true }).waitFor();
    }
    assert.deepEqual(commands, Array(4).fill(['extend', 'pause', 'resume']).flat());
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ result: 'passed', widths: [320, 768, 1024, 1440], commands, pageErrors: errors }));
  } finally { await browser.close(); server.close(); }
})().catch(error => { console.error(error); server.close(); process.exitCode = 1; });
