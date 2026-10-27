/* Regression: a single-column report must fail the reviewed IEEE body layout.
   Usage: node scripts/verify_ieee_docx.cjs SERVER_URL REPORT.docx OUTPUT_DIRECTORY
   The report is supplied locally and is never bundled or committed. */
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const crypto=require('node:crypto');
const [base,report,out]=process.argv.slice(2);
if(!base||!report||!out)throw Error('Provide server URL, single-column DOCX and output directory.');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.REPORTLINT_BROWSER_PATH||undefined});
 const page=await browser.newPage({viewport:{width:1280,height:960}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 try{
  const catalog=await(await page.request.get(base+'/api/v2/templates')).json();
  const index=catalog.findIndex(t=>t.id==='builtin-ieee-conference-letter');assert(index>=0);
  await page.goto(base+'/app/');
  await page.locator('flt-semantics-placeholder').waitFor({state:'attached'});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
  await page.getByText('Open format',{exact:true}).nth(index).click();
  await page.getByText('Revision 1 PUBLISHED',{exact:true}).click();
  await page.getByText('Check a report',{exact:true}).click();
  const chooser=page.waitForEvent('filechooser');
  await page.getByRole('button',{name:'Choose report',exact:true}).click();
  await(await chooser).setFiles(report);
  await page.waitForTimeout(400);
  const checked=page.waitForResponse(r=>r.url().endsWith('/check')&&r.request().method()==='POST').then(r=>r.json());
  await page.getByRole('button',{name:'Check report',exact:true}).click();
  const result=await checked;
  assert.equal(result.report_sha256,crypto.createHash('sha256').update(fs.readFileSync(report)).digest('hex'));
  assert.equal(result.outcome,'FAIL');
  const mismatches=result.items.filter(i=>i.code==='DOCX_BODY_COLUMNS_MISMATCH');
  assert(mismatches.length>0&&mismatches.every(i=>i.status==='FAIL'&&i.actual.observed_columns===1&&i.expected.count===2));
  await page.getByText('Here’s what to fix',{exact:true}).waitFor();
  await page.waitForTimeout(400);await page.screenshot({path:path.join(out,'ieee-docx-desktop.png')});
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(400);
  await page.screenshot({path:path.join(out,'ieee-docx-mobile.png')});
  for(let i=0;i<40;i++){
   const button=page.getByText('Download results',{exact:true});
   if(await button.count()){const b=await button.boundingBox();if(b&&b.y>55&&b.y<790)break;}
   await page.mouse.move(200,500);await page.mouse.wheel(0,500);await page.waitForTimeout(120);
  }
  const download=page.waitForEvent('download');await page.getByText('Download results',{exact:true}).click();
  const filename=path.join(out,'result.json');await(await download).saveAs(filename);
  assert.deepEqual(JSON.parse(fs.readFileSync(filename,'utf8')).result,result);
  assert.deepEqual(errors,[]);
  const receipt={outcome:result.outcome,counts:result.counts,columnFailures:mismatches.length,
    sections:mismatches.map(i=>i.section_index+1),exportVerified:true,pageErrors:errors};
  fs.writeFileSync(path.join(out,'receipt.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }catch(e){await page.screenshot({path:path.join(out,'failure.png')});console.error(await page.locator('body').innerText());throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
