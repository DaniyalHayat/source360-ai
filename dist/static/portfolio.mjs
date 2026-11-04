const $=id=>document.getElementById(id),money=n=>Number.isFinite(n)?n.toLocaleString('en-US',{style:'currency',currency:'USD',maximumFractionDigits:0}):'—',number=n=>n.toLocaleString('en-US',{maximumFractionDigits:1});
let input,result;
const worker=new Worker(new URL('joint-worker.mjs',import.meta.url),{type:'module'});
function table(id,headers,rows){const table=document.createElement('table'),head=table.createTHead().insertRow();for(const label of headers){const th=document.createElement('th');th.textContent=label;head.append(th);}const body=table.createTBody();for(const values of rows){const row=body.insertRow();for(const value of values)row.insertCell().textContent=value;}$(id).replaceChildren(table);}
function render(r){
  result=r;$('export').disabled=false;$('metrics').replaceChildren();
  for(const [label,value] of [['Reference baseline',money(r.baseline_cost)],['Landed cash cost',money(r.landed_cost)],['Modeled savings',money(r.modeled_savings)],['Proven optimal events',r.status==='feasible'?'25 / 25':'0 / 25']]){const card=document.createElement('div');card.className='metric';const title=document.createElement('div');title.className='metric-label';title.textContent=label;const strong=document.createElement('div');strong.className='metric-value';strong.textContent=value;card.append(title,strong);$('metrics').append(card);}
  $('status').textContent=r.status==='feasible'?`Optimal under supplied constraints · ${(r.savings_pct*100).toFixed(2)}% modeled savings · ${r.solve_ms.toFixed(0)} ms on this device`:`${r.solver_status}. No portfolio benefit is claimed for this scenario.`;
  table('events',['Renewal lot','Demand','Baseline','Cash cost','Modeled savings','Selected suppliers'],r.results.map(x=>[x.title,number(x.demand)+' '+x.unit,money(x.baseline_cost),money(x.landed_cost),money(x.baseline_cost-x.landed_cost),x.allocations.map(a=>a.name+': '+number(a.quantity)).join('; ')]));
  table('capacities',['Supplier','Period / unit','Used','Budget','Remaining'],r.supplier_capacity.sort((a,b)=>a.slack/a.capacity-b.slack/b.capacity).map(c=>[c.name,c.capacity_period+' / '+c.unit,number(c.used),number(c.capacity),number(Math.max(0,c.slack))]));
}
function solve(){if(!input)return;$('solve').disabled=true;$('export').disabled=true;$('status').textContent='Solving the joint mixed-integer model in a background worker…';worker.postMessage({input,params:{capacity_factor:Number($('capacity').value)/100,risk_penalty:Number($('risk').value)}});}
worker.onmessage=event=>{$('solve').disabled=false;if(event.data.error){$('status').textContent=event.data.error;return;}render(event.data.result);};
worker.onerror=()=>{$('status').textContent='The solver could not start. Serve the complete browser build over HTTP, including the WebAssembly file.';$('solve').disabled=false;};
$('scenario').addEventListener('submit',event=>{event.preventDefault();solve();});
$('export').addEventListener('click',()=>{const blob=new Blob([JSON.stringify(result,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='source360-joint-scenario.json';a.click();URL.revokeObjectURL(url);});
try{
  const endpoint=document.body.dataset.delivery==='snapshot'?'portfolio-input.json':'/api/v1/portfolio/inputs';
  const response=await fetch(endpoint,{cache:'no-store'});if(!response.ok)throw new Error('The published input snapshot is unavailable; run the documented pipeline/export');input=await response.json();
  const w=input.warehouse.receipt;$('warehouse').textContent=`${number(w.rows)} normalized purchase-order facts · ${w.storage} · ${w.lake_partitions} verified monthly Parquet partitions · ${(w.lake_bytes/1048576).toFixed(1)} MiB compressed. Publication ${w.batch_id.slice(0,16)}.`;
  table('insights',['Category','Purchase lines','Spend','Off-contract review','Share off contract'],input.warehouse.categories.map(c=>[c.name,number(c.po_lines),money(c.spend_usd),money(c.off_contract_usd),(100*c.off_contract_usd/c.spend_usd).toFixed(1)+'%']));
  $('lineage').textContent=JSON.stringify({snapshot:input.snapshot,warehouse:w,capacity_basis:input.capacities[0].basis,demand_basis:input.rfqs[0].demand_basis},null,2);solve();
}catch(error){$('status').textContent=error.message;}
