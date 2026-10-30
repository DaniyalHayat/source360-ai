const modelReceiptURL=new URL('ai-evidence-data.json',document.currentScript.src).href;
const modelObserver=new MutationObserver(async()=>{
  if(!document.querySelector('#evidence-search')||document.querySelector('#model-evidence-panel'))return;
  const section=document.createElement('section');section.id='model-evidence-panel';section.className='panel';section.innerHTML='<h2>Evidence assistant</h2><p>Loading model evidence…</p>';
  document.querySelector('#evidence-search').before(section);
  try{
    const r=await fetch(modelReceiptURL);if(!r.ok)throw new Error('Model evaluation unavailable');const data=await r.json();
    section.innerHTML='<div class="panel-heading"><div><h2>Evidence assistant · local AI with source citations</h2><p class="sub">MiniLM semantic retrieval + FLAN-T5 generation · human review required</p></div><span class="pill">'+data.answer_hits+' / '+data.cases+' benchmark answers</span></div><label for="model-question">Inspect a tested question</label><select id="model-question" style="display:block;margin:12px 0;width:100%;max-width:none;border:1px solid #d7e3dc;padding:10px">'+data.results.map((c,i)=>'<option value="'+i+'">'+esc(c.question)+'</option>').join('')+'</select><div id="model-answer"></div><div class="notes">Public demo: replay of actual local model runs, not live inference. The downloadable API supports new questions through POST /api/v1/assistant/answer. This five-case synthetic benchmark is too small to establish production accuracy. Similarity is not calibrated confidence.</div>';
    const show=()=>{const c=data.results[Number(document.querySelector('#model-question').value)],v=c.response;document.querySelector('#model-answer').innerHTML='<p style="font-size:20px">'+esc(v.answer)+'</p><div class="receipt">Source: '+esc(v.cited_source.source_id)+'<br>Exact evidence: '+esc(v.cited_source.text)+'<br>Offsets: '+v.cited_source.start+'–'+v.cited_source.end+'<br>Validation: '+esc(v.validation_status)+'<br>Model: '+esc(v.model)+'</div>';};document.querySelector('#model-question').onchange=show;show();
  }catch(e){section.textContent=e.message;}
});
modelObserver.observe(document.querySelector('#content'),{childList:true});
