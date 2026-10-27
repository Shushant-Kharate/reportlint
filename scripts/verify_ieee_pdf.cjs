/* Original PDF -> Flutter file picker -> reviewed IEEE baseline -> JSON export.
   Usage: node scripts/verify_ieee_pdf.cjs SERVER_URL PAPER_PDF OUTPUT_DIRECTORY
   Download the real paper separately; copyrighted papers are not bundled. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const [base,paper,out]=process.argv.slice(2);
if(!base||!paper||!out)throw Error('Provide server URL, original paper PDF and output directory.');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.REPORTLINT_BROWSER_PATH||undefined});
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try {
  await page.goto(base+'/app/');
  await page.locator('flt-semantics-placeholder').waitFor({state:'attached'});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
  const catalog=await(await page.request.get(base+'/api/v2/templates')).json();
  const index=catalog.findIndex(t=>t.id==='builtin-ieee-conference-letter');assert(index>=0);
  await page.getByText('Open format',{exact:true}).nth(index).click();
  await page.getByText(`Revision ${catalog[index].latest_revision_number} PUBLISHED`,{exact:true}).click();
  await page.getByText('Check a report',{exact:true}).click();
  const chooser=page.waitForEvent('filechooser');
  await page.getByRole('button',{name:'Choose report',exact:true}).click();
  await(await chooser).setFiles(paper);
  await page.getByText('Review paragraph roles',{exact:true}).waitFor({state:'hidden'});
  assert.equal(await page.getByText('Review paragraph roles',{exact:true}).count(),0);
  const response=page.waitForResponse(r=>r.url().endsWith('/check')&&r.request().method()==='POST').then(async r=>{
   assert(r.ok());return r.json();
  });
  await page.getByRole('button',{name:'Check report',exact:true}).click();
  const result=await response;
  assert.equal(result.report_format,'pdf');assert.equal(result.outcome,'INDETERMINATE');
  assert.equal(result.counts.PASS,14);assert.equal(result.counts.FAIL,0);
  assert(result.counts.NOT_CHECKED>=28);assert.equal(result.counts.OUT_OF_SCOPE,0);
  const crypto=require('node:crypto');
  assert.equal(result.report_sha256,crypto.createHash('sha256').update(fs.readFileSync(paper)).digest('hex'));
  await page.getByText('Some requirements remain unchecked',{exact:true}).waitFor();
  await page.waitForTimeout(400);await page.screenshot({path:path.join(out,'ieee-pdf-mobile.png')});
  const exportPath=path.join(out,'ieee-pdf-export.json');
  for(let i=0;i<60;i++){
   const button=page.getByText('Download results',{exact:true});
   if(await button.count()){const b=await button.boundingBox();if(b&&b.y>55&&b.y<790)break;}
   await page.mouse.move(200,500);await page.mouse.wheel(0,550);await page.waitForTimeout(100);
  }
  const download=page.waitForEvent('download');
  await page.getByText('Download results',{exact:true}).click();
  await(await download).saveAs(exportPath);
  const exported=JSON.parse(fs.readFileSync(exportPath,'utf8'));
  assert.deepEqual(exported.result,result);
  assert.equal(exported.revision.template_id,'builtin-ieee-conference-letter');
  await page.mouse.wheel(0,-30000);await page.setViewportSize({width:1280,height:960});
  await page.waitForTimeout(400);await page.screenshot({path:path.join(out,'ieee-pdf-desktop.png')});
  assert.deepEqual(errors,[]);
  fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify({counts:result.counts,originalPdfHashVerified:true,exportVerified:true,pageErrors:errors},null,2));
  console.log(JSON.stringify({counts:result.counts,originalPdfHashVerified:true,exportVerified:true,pageErrors:errors}));
 } catch(e){await page.screenshot({path:path.join(out,'failure.png')});console.error(await page.locator('body').innerText());throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
