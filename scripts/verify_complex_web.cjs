/* Optional browser verification. Requires Playwright and its Chromium browser.
   node scripts/verify_complex_web.cjs BASE_URL FIXTURE_DIRECTORY OUTPUT_DIRECTORY
   Fixtures: python -m scripts.create_web_qa_fixtures FIXTURE_DIRECTORY
   Use an isolated server storage directory: this creates a template and revisions. */
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const [base, fixtures, output] = process.argv.slice(2);
if (!base || !fixtures || !output) throw new Error('Provide base URL, fixture directory, and output directory.');
fs.mkdirSync(output, {recursive:true});
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:process.env.REPORTLINT_BROWSER_PATH || undefined});
  const context = await browser.newContext({viewport:{width:390,height:844}, reducedMotion:'reduce'});
  const page = await context.newPage(); const errors = []; const requests = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('response', r => {if(r.url().includes('/api/')) requests.push({path:new URL(r.url()).pathname,status:r.status()});});
  page.on('dialog', d => d.accept());
  const settled = () => page.locator('main:not([aria-busy])').waitFor();
  const shot = name => page.screenshot({path:path.join(output,name+'.png'),fullPage:false});
  const noOverflow = async () => assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth > window.innerWidth),false,'horizontal overflow');
  try {
    await page.goto(base+'/app/complex.html'); await settled(); await shot('home-390'); await noOverflow();
    await page.locator('#templatesPanel h1').focus();await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.tagName),'SUMMARY');
    await page.getByText('Add a format document',{exact:true}).click();
    await page.locator('#formatName').fill('Mini Project · browser verification');
    await page.locator('#formatFile').setInputFiles(path.join(fixtures,'format.docx'));
    const upload = page.waitForResponse(r=>new URL(r.url()).pathname==='/api/v2/templates'&&r.request().method()==='POST');
    await page.getByRole('button',{name:'Upload and review',exact:true}).click();
    const draft = await (await upload).json(); await settled();
    assert.equal(draft.status,'DRAFT');
    await page.locator('#publish').click(); await settled();
    assert.match(await page.locator('#blockers').innerText(),/decisions needed/);
    for(const [i,c] of draft.analysis.candidates.entries()) {
      let action = c.origin==='EXPLICIT_PROSE' ? 'APPROVE' : 'REJECT';
      if(c.condition==='HEADER_ABSENT') action='DEFER';
      await page.locator('#candidate-'+i).selectOption(action);
      await page.locator('#candidate-reason-'+i).fill('Reviewed synthetic requirement for this test.');
    }
    await page.locator('#ledgerSummary').click();
    for(const [i] of draft.analysis.requirement_ledger.entries()) {
      await page.locator('#ledger-'+i).selectOption('DEFERRED');
      await page.locator('#ledger-reason-'+i).fill('Other instructions remain outside automated coverage.');
    }
    await page.locator('#profilePicker').selectOption(draft.analysis.profiles[0].profile_id);
    await page.locator('#profileReason').fill('Use the report chapters, not the synopsis.');
    for(const [i] of draft.analysis.profiles[0].chapters.entries()) await page.locator('#chapter-required-'+i).selectOption('true');
    const conflicting = draft.analysis.candidates.findIndex(c=>c.origin==='OBSERVED_APPEARANCE'&&c.value.kind==='font_size');
    await page.locator('#candidate-'+conflicting).selectOption('APPROVE');
    await page.locator('#publish').click(); await settled();
    assert.match(await page.locator('#blockers').innerText(),/11.5 pt/);
    await page.locator('#candidate-'+conflicting).selectOption('REJECT');
    await page.locator('#saveReview').click(); await settled();
    assert.equal(await page.locator('#blockers').isVisible(),false);
    // A second writer advances the version. The UI must preserve local edits and show a conflict.
    let current = await (await context.request.get(base+`/api/v2/templates/${draft.template_id}/revisions/${draft.revision_id}`)).json();
    await context.request.patch(base+`/api/v2/templates/${draft.template_id}/revisions/${draft.revision_id}`,{data:{expected_version:current.version}});
    await page.locator('#saveReview').click(); await settled();
    assert.match(await page.locator('#message').innerText(),/changed elsewhere/);
    assert.equal(await page.locator('#candidate-0').inputValue(),'APPROVE');
    await page.locator('#reloadRevision').click(); await settled();
    for(const width of [320,390,768,1280]) {await page.setViewportSize({width,height:900});await page.evaluate(()=>window.scrollTo(0,0));await noOverflow();await shot('review-'+width);}
    await page.locator('#publish').click(); await settled();
    assert.match(await page.locator('#revisionStatus').innerText(),/Published/);
    assert.equal(await page.locator('#candidate-0').isDisabled(),true);
    // Forking never modifies the original published revision.
    await page.locator('#fork').click(); await settled(); assert.match(await page.locator('#revisionStatus').innerText(),/Revision 2.*Draft/);
    await page.locator('#revisionPicker').selectOption(draft.revision_id); await settled();
    await page.locator('#useRevision').click();
    await page.setViewportSize({width:390,height:844});
    await page.locator('#reportInput').setInputFiles(path.join(fixtures,'report.docx'));
    const roleResponse = page.waitForResponse(r=>r.url().endsWith('/role-preview'));
    await page.locator('#previewRoles').click(); const preview = await (await roleResponse).json(); await settled();
    assert.equal(preview.paragraphs.length,7);
    for(const p of preview.paragraphs) {
      assert.equal(await page.locator('#role-'+p.paragraph_index).inputValue(),'','suggestion must not be accepted automatically');
      const role = p.paragraph_index===0 ? 'EXCLUDE' : p.suggested_role;
      await page.locator('#role-'+p.paragraph_index).selectOption(role);
      if(role==='CHAPTER') await page.locator('#role-chapter-'+p.paragraph_index).selectOption(String(p.suggested_chapter_index));
      await page.locator('#role-reason-'+p.paragraph_index).fill('Confirmed against the synthetic report for browser verification.');
    }
    assert.match(await page.locator('#roleCount').innerText(),/7 decisions started/);
    await page.locator('#roleFilter').selectOption('all'); // Re-render must preserve all choices.
    assert.equal(await page.locator('#role-2').inputValue(),'BODY');
    await page.evaluate(()=>window.scrollTo(0,600));await shot('roles-390');await noOverflow();
    const checkResponse = page.waitForResponse(r=>r.url().endsWith('/check'));
    await page.locator('#reviewedCheck').click(); const result = await (await checkResponse).json(); await settled();
    assert.equal(result.revision_id,draft.revision_id); assert.equal(result.role_decisions.length,7);
    assert(result.items.some(i=>i.code==='BODY_RUN_FAIL'&&i.paragraph_index===2));
    assert.match(await page.locator('#resultTitle').innerText(),/issues found/);
    assert(result.counts.NOT_CHECKED>0);
    for(const width of [320,390,768,1280]) {await page.setViewportSize({width,height:900}); await page.evaluate(()=>window.scrollTo(0,0)); await noOverflow(); await shot('results-'+width);}
    await page.locator('#resultFilter').selectOption('NOT_CHECKED');
    assert.equal(await page.locator('#findings .FAIL').count(),0);
    const downloadEvent=page.waitForEvent('download'); await page.locator('#downloadResult').click(); const download=await downloadEvent;
    await download.saveAs(path.join(output,'result.json'));
    assert.equal(JSON.parse(fs.readFileSync(path.join(output,'result.json'),'utf8')).role_review_sha256,result.role_review_sha256);
    await page.getByRole('button',{name:'← Back to report',exact:true}).click();
    await page.locator('#reportInput').setInputFiles(path.join(fixtures,'partial-report.docx'));
    assert.equal(await page.locator('#rolePanel').isVisible(),false);
    await page.locator('#checkReport').click();await settled();
    assert.match(await page.locator('#resultTitle').innerText(),/remain unchecked/);
    assert.match(await page.locator('#resultMeaning').innerText(),/cannot be confirmed fully compliant/);
    await page.setViewportSize({width:390,height:844});await shot('partial-390');
    // Network failures keep the report screen usable; new file selection clears stale decisions.
    await page.getByRole('button',{name:'← Back to report',exact:true}).click();
    await page.locator('#reportInput').setInputFiles(path.join(fixtures,'format.docx'));
    assert.equal(await page.locator('#rolePanel').isVisible(),false);
    await page.route('**/api/v2/templates/**',route=>route.abort());
    await page.locator('#checkReport').click();await settled();assert.match(await page.locator('#message').innerText(),/Cannot reach the server/);
    await page.unroute('**/api/v2/templates/**');
    await page.reload();await settled();assert.equal(await page.locator('#rolePanel').isVisible(),false);
    assert.equal(await page.evaluate(()=>localStorage.length),0);
    const cacheUrls = await page.evaluate(async()=>{const urls=[];for(const key of await caches.keys()){const cache=await caches.open(key);urls.push(...(await cache.keys()).map(r=>r.url));}return urls;});
    assert(cacheUrls.every(url=>!url.includes('/api/')&&!url.includes('.docx')),'private API/report data must not be cached');
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'browser-report.json'),JSON.stringify({passed:true,browser:browser.version(),viewports:[320,390,768,1280],pageErrors:errors,requests,resultCounts:result.counts,cacheUrls},null,2));
    console.log(JSON.stringify({passed:true,resultCounts:result.counts,screenshots:output}));
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
