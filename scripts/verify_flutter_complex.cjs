/* Fictional complex-format browser test. Run create_web_qa_fixtures first.
   node scripts/verify_flutter_complex.cjs SERVER_URL FIXTURES_DIRECTORY OUTPUT_DIRECTORY
   Use isolated backend storage. Review/publication is seeded through the API;
   actual file selection, role editing, report check and export use Flutter UI. */
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
const [base,fixtures,out]=process.argv.slice(2);
if(!base||!fixtures||!out)throw Error('Provide server URL, fixtures directory, output directory.');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.REPORTLINT_BROWSER_PATH||undefined});
 const page=await browser.newPage({viewport:{width:390,height:844}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 async function json(response){assert(response.ok(),await response.text());return response.json();}
 try{
  const draft=await json(await page.request.post(base+'/api/v2/templates',{multipart:{name:'Flutter complex QA',file:{name:'format.docx',mimeType:'application/vnd.openxmlformats-officedocument.wordprocessingml.document',buffer:fs.readFileSync(path.join(fixtures,'format.docx'))}}}));
  const revisionPath=base+`/api/v2/templates/${draft.template_id}/revisions/${draft.revision_id}`;
  const profile=draft.analysis.profiles[0];
  const edited=await json(await page.request.patch(revisionPath,{data:{expected_version:draft.version,
   candidates:draft.analysis.candidates.map(c=>({candidate_id:c.candidate_id,action:c.origin==='EXPLICIT_PROSE'?(c.condition==='HEADER_ABSENT'?'DEFER':'APPROVE'):'REJECT',reason:'Synthetic reviewer decision for browser verification.'})),
   ledger:draft.analysis.requirement_ledger.map(e=>({evidence_id:e.evidence_id,action:e.status==='MANUAL_REVIEW'?'MANUAL':'DEFERRED',reason:'Uncovered instructions remain explicit for this partial test.'})),
   profile:{profile_id:profile.profile_id,reason:'Use fictional report chapters for this test.',chapters:profile.chapters.map((c,i)=>({index:i,name:c.title,required:true}))}
  }}));
  await json(await page.request.post(revisionPath+'/publish',{data:{expected_version:edited.version}}));
  await page.goto(base+'/app/');
  await page.locator('flt-semantics-placeholder').waitFor({state:'attached'});
  await page.locator('flt-semantics-placeholder').evaluate(e=>e.click());
  // The newly created template is first in the backend's descending creation order.
  await page.getByText('Open format',{exact:true}).first().click();
  await page.getByText('Revision 1 PUBLISHED',{exact:true}).click();
  await page.getByText('Check a report',{exact:true}).click();
  await page.waitForTimeout(400);
  const chooser=page.waitForEvent('filechooser');
  await page.getByText('Choose report',{exact:true}).click();
  await(await chooser).setFiles(path.join(fixtures,'report.docx'));
  await page.waitForTimeout(400);
  const previewResponse=page.waitForResponse(r=>r.url().endsWith('/role-preview'));
  await page.getByText('Review paragraph roles',{exact:true}).click();
  const preview=await json(await previewResponse);assert.equal(preview.paragraphs.length,7);
  await page.getByText('Paragraph roles',{exact:true}).waitFor();await page.waitForTimeout(400);
  await page.screenshot({path:path.join(out,'flutter-roles-mobile.png')});
  await page.getByText('Confirmed role Keep detected role',{exact:true}).first().click();
  await page.getByRole('menuitem',{name:'Exclude',exact:true}).click();
  await page.getByRole('textbox',{name:'Reason',exact:true}).fill('Verified fictional cover, excluded from body rules.');
  await page.getByText('Apply 1 decisions',{exact:true}).click();await page.waitForTimeout(400);
  const response=page.waitForResponse(r=>r.url().endsWith('/check'));
  await page.getByRole('button',{name:'Check report',exact:true}).click();
  const result=await json(await response);
  assert.equal(result.role_decisions.length,1);assert.equal(result.role_decisions[0].role,'EXCLUDE');
  assert.equal(result.outcome,'FAIL');assert(result.counts.FAIL>0);assert(result.counts.NOT_CHECKED>0);
  assert.equal(result.overall_score,undefined);
  await page.waitForTimeout(600);await page.screenshot({path:path.join(out,'flutter-complex-result-mobile.png')});
  const downloadPromise=page.waitForEvent('download');
  await page.getByText('Export result and evidence',{exact:true}).click();
  await(await downloadPromise).saveAs(path.join(out,'complex-export.json'));
  const exported=JSON.parse(fs.readFileSync(path.join(out,'complex-export.json'),'utf8'));
  assert.deepEqual(exported.result,result);assert.equal(exported.revision.revision_id,draft.revision_id);
  assert.deepEqual(errors,[]);
  const receipt={outcome:result.outcome,counts:result.counts,roleDecisions:result.role_decisions.length,exportVerified:true,pageErrors:errors};
  fs.writeFileSync(path.join(out,'complex-smoke.json'),JSON.stringify(receipt,null,2));console.log(JSON.stringify(receipt));
 }catch(e){await page.screenshot({path:path.join(out,'complex-failure.png')});throw e;}
 finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
