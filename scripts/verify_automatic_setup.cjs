/* Real Flutter upload -> automatic rules -> clarification -> changed report result.
   Uses fictional fixtures and the packaged official format; receipts stay outside Git. */
const {chromium}=require('playwright');
const fs=require('node:fs');const path=require('node:path');const assert=require('node:assert/strict');
const [base,fixtures,out]=process.argv.slice(2);
if(!base||!fixtures||!out)throw Error('Usage: SERVER_URL FIXTURES_DIRECTORY OUTPUT_DIRECTORY');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch();const page=await browser.newPage({viewport:{width:1280,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 // Chromium can evict XHR response bodies when Flutter changes screens. Buffer
 // real POST responses before forwarding them unchanged; no API is mocked.
 const captured=new Map();
 await page.route('**/api/v2/**',async route=>{
  if(route.request().method()!=='POST'){await route.continue();return;}
  const response=await route.fetch();const body=await response.body();
  const key=route.request().url();const queue=captured.get(key)||[];
  queue.push(body);captured.set(key,queue);
  await route.fulfill({response,body});
 });
 async function read(response){
  const queue=captured.get(response.url());
  if(queue?.length)return JSON.parse(queue.shift().toString('utf8'));
  return response.json();
 }
 const receipt={};
 async function home(){
  // Exercise the app's Back navigation instead of repeatedly destroying the
  // Flutter renderer and its in-flight network resources with full reloads.
  if(page.url().startsWith(base)){
   for(let i=0;i<6;i++){
    const add=page.getByRole('button',{name:'Add format document',exact:true});
    if(await add.count()){await page.waitForLoadState('networkidle');return;}
    const back=page.getByRole('button',{name:'Back',exact:true});
    if(!await back.count())break;
    await back.click();await page.waitForTimeout(300);
   }
  }
  const loaded=page.waitForResponse(r=>r.url()===base+'/api/v2/templates'&&r.request().method()==='GET');
  await page.goto(base+'/app/');await loaded;
  const semantics=page.locator('flt-semantics-placeholder');
  if(await semantics.count())await semantics.evaluate(e=>e.click());
  await page.getByRole('button',{name:'Add format document',exact:true}).waitFor();
 }
 async function upload(file){
  const ready=page.waitForResponse(r=>r.url().endsWith('/api/v2/templates/prepare')&&r.request().method()==='POST');
  const chooser=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Add format document',exact:true}).click();
  await(await chooser).setFiles(file);const response=await ready;if(!response.ok())throw Error(await response.text());
  const data=await read(response);await page.getByText('Your format is ready',{exact:true}).waitFor();
  assert.equal(await page.getByRole('textbox',{name:'Reason',exact:true}).count(),0);
  assert.equal(await page.getByText('Save and publish',{exact:true}).count(),0);
  return data;
 }
 async function reveal(locator){
  for(let i=0;i<35;i++){
   if(await locator.count()){const b=await locator.first().boundingBox();if(b&&b.y>65&&b.y<700)return;}
   await page.mouse.move(400,500);await page.mouse.wheel(0,350);await page.waitForTimeout(90);
  }
  throw Error('Could not reveal '+locator);
 }
 async function check(file){
  await page.getByRole('button',{name:'Check a report',exact:true}).click();
  const chooser=page.waitForEvent('filechooser');await page.getByRole('button',{name:'Choose report',exact:true}).click();
  await(await chooser).setFiles(file);await page.waitForTimeout(350);
  const checked=page.waitForResponse(r=>r.url().endsWith('/check')&&r.request().method()==='POST').then(async response=>{
    const data=await read(response);if(!response.ok())throw Error(JSON.stringify(data));return data;
  });
  await page.getByRole('button',{name:'Check report',exact:true}).click();return checked;
 }
 try{
  await home();const known=await upload(path.join(__dirname,'..','app','builtins','ieee-conference-letter.docx'));
  assert(known.reused&&known.rule_count===19);receipt.knownFormat={reused:true,rules:known.rule_count};
  await page.screenshot({path:path.join(out,'automatic-known-desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(300);
  await page.screenshot({path:path.join(out,'automatic-known-mobile.png')});
  await page.setViewportSize({width:1280,height:960});
  await home();const prepared=await upload(path.join(fixtures,'unseen-format.docx'));
  assert(!prepared.reused&&prepared.ready&&prepared.questions.length===1);
  const old=prepared.revision;const oldPath=base+`/api/v2/templates/${old.template_id}/revisions/${old.revision_id}`;
  await page.screenshot({path:path.join(out,'automatic-new-format.png')});
  const before=await check(path.join(fixtures,'report.docx'));assert.equal(before.counts.FAIL,0);
  await home();const reused=await upload(path.join(fixtures,'unseen-format.docx'));assert(reused.reused);
  const title=page.getByText(reused.questions[0].instruction,{exact:false}).first();await reveal(title);await title.click();
  const input=page.getByRole('textbox',{name:'Explain this instruction',exact:true});await reveal(input);
  async function explain(text){
   await input.click();await page.keyboard.press('ControlOrMeta+A');await input.pressSequentially(text,{delay:4});await page.keyboard.press('Tab');
   const response=page.waitForResponse(r=>r.url().endsWith('/clarify')&&r.request().method()==='POST');
   const apply=page.getByRole('button',{name:'Apply explanation',exact:true}).first();await reveal(apply);await apply.click();
   const r=await response;return {status:r.status(),data:await read(r)};
  }
  const rejected=await explain('Make it look professional.');assert.equal(rejected.status,422);
  assert.equal(await input.inputValue(),'Make it look professional.');
  const answer=await explain('Use Arial at 12 pt.');assert.equal(answer.status,200);
  const updated=answer.data;assert(updated.ready&&updated.questions.length===0);
  assert.notEqual(updated.revision.revision_id,old.revision_id);
  const saved=await(await page.request.get(oldPath)).json();assert.deepEqual(saved,old);
  await page.mouse.wheel(0,-20000);await page.waitForTimeout(350);
  await page.screenshot({path:path.join(out,'automatic-clarified-desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(250);
  await page.screenshot({path:path.join(out,'automatic-clarified-mobile.png')});
  const after=await check(path.join(fixtures,'report.docx'));
  assert(after.items.some(i=>i.status==='FAIL'&&i.expected?.kind==='font_family'&&i.expected.font==='Arial'));
  assert.equal(after.revision_id,updated.revision.revision_id);
  await home();const remembered=await upload(path.join(fixtures,'unseen-format.docx'));
  assert(remembered.reused&&remembered.revision.revision_id===updated.revision.revision_id);
  receipt.newFormat={initialRules:prepared.rule_count,initialQuestions:prepared.questions.length,
   rulesAfterExplanation:updated.rule_count,questionsAfterExplanation:0,invalidExplanationStatus:rejected.status,
   before:before.counts,after:after.counts,originalSnapshotPreserved:true,explanationRemembered:true};
  assert.deepEqual(errors,[]);receipt.pageErrors=errors;
  fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }catch(e){await page.screenshot({path:path.join(out,'failure.png')});console.error(await page.locator('body').innerText());throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
