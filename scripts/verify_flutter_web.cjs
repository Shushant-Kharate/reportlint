/* Real browser -> Flutter -> API smoke test. Requires Playwright.
   node scripts/verify_flutter_web.cjs http://127.0.0.1:8780 OUTPUT_DIRECTORY
   Use isolated REPORTLINT_STORAGE_DIR: this creates a fictional demo template. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const [base,output]=process.argv.slice(2);
if(!base||!output)throw Error('Provide server URL and evidence output directory.');
fs.mkdirSync(output,{recursive:true});
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.REPORTLINT_BROWSER_PATH||undefined});
 const page=await browser.newPage({viewport:{width:1280,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function visibleText(text){
  const locator=page.getByText(text,{exact:true});
  for(let i=0;i<35;i++){
   if(await locator.count()) {const b=await locator.first().boundingBox();if(b&&b.y>55&&b.y<page.viewportSize().height-25)return locator.first();}
   await page.mouse.move(page.viewportSize().width/2,page.viewportSize().height/2);
   await page.mouse.wheel(0,500);await page.waitForTimeout(120);
  }
  throw Error('Could not scroll to '+text+'\n'+await page.locator('body').innerText());
 }
 try{
  await page.goto(base+'/app/');
  await page.locator('flt-semantics-placeholder').waitFor({state:'attached'});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
  await page.getByText('Add format document',{exact:true}).waitFor();
  await page.screenshot({path:path.join(output,'flutter-home-desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(200);
  await page.screenshot({path:path.join(output,'flutter-home-mobile.png')});
  await page.getByText('Basic checker and demo files Simple templates and the original three-file demonstration',{exact:true}).click();
  await page.getByText('Try demo template',{exact:true}).click();
  await page.getByText('Basic format review',{exact:true}).waitFor();
  const publishResponse=page.waitForResponse(r=>r.url().endsWith('/publish'));
  await (await visibleText('Publish basic template')).click();
  assert.equal((await publishResponse).status(),200);

  const correctResponse=page.waitForResponse(r=>r.url().endsWith('/check'));correctResponse.catch(()=>{});
  await (await visibleText('Check correct demo')).click();
  const correct=await(await correctResponse).json();assert.equal(correct.overall_score,100);assert.equal(correct.violations.length,0);
  await page.getByText('Basic check result',{exact:true}).waitFor();await page.waitForTimeout(400);
  await page.screenshot({path:path.join(output,'flutter-correct-demo.png')});
  await page.getByRole('button',{name:'Back',exact:true}).click();
  const wrongResponse=page.waitForResponse(r=>r.url().endsWith('/check'));
  await (await visibleText('Check error demo')).click();
  const wrong=await(await wrongResponse).json();assert(wrong.violations.length>0);assert(wrong.overall_score<100);
  await page.getByText('Basic check result',{exact:true}).waitFor();await page.waitForTimeout(400);
  await page.screenshot({path:path.join(output,'flutter-error-demo.png')});
  const downloadPromise=page.waitForEvent('download');await(await visibleText('Export result and evidence')).click();
  const download=await downloadPromise;await download.saveAs(path.join(output,'exported-result.json'));
  const exported=JSON.parse(fs.readFileSync(path.join(output,'exported-result.json'),'utf8'));assert.equal(exported.result.overall_score,wrong.overall_score);
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(output,'flutter-smoke.json'),JSON.stringify({correct_score:correct.overall_score,wrong_score:wrong.overall_score,wrong_violations:wrong.violations.length,export_verified:true,page_errors:errors},null,2));
  console.log(JSON.stringify({correct:correct.overall_score,wrong:wrong.overall_score,pageErrors:errors}));
 }catch(e){await page.screenshot({path:path.join(output,'failure.png')});console.error(await page.locator('body').innerText());throw e;}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});


