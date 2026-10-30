(function(){
  const realFetch=window.fetch.bind(window);let snapshot;
  const load=()=>snapshot||(snapshot=realFetch('./static/demo-data.json').then(r=>{if(!r.ok)throw new Error('Demo dataset unavailable');return r.json();}));
  window.fetch=async function(url,options={}){
    if(!String(url).startsWith('/api/v1/'))return realFetch(url,options);
    const data=await load(),path=String(url).slice(8),clean=path.split('?')[0],category=new URLSearchParams(String(url).split('?')[1]||'').get('category_id');
    let body,status=200;
    try{
      if(clean==='categories')body=data.categories;
      else if(clean==='rfqs')body=data.rfqs;
      else if(clean==='suppliers')body=data.suppliers;
      else if(clean==='overview')body=data.overviews[category||'all'];
      else if(/^categories\/\d+\/forecast$/.test(clean))body=data.forecasts[clean.split('/')[1]];
      else if(/^suppliers\/\d+\/scorecard$/.test(clean))body=data.suppliers.find(s=>s.supplier_id===Number(clean.split('/')[1]));
      else if(/^rfqs\/[^/]+\/bids$/.test(clean))body=data.bids[clean.split('/')[1]];
      else if(/^rfqs\/[^/]+\/scenarios$/.test(clean)&&options.method==='POST'){
        const rfq=data.rfqs.find(r=>r.rfq_id===clean.split('/')[1]);const params=JSON.parse(options.body||'{}');
        body=Source360Engine.optimize(rfq,data.bids[rfq.rfq_id],params);
        body.input_snapshot_id=data.quality.run.input_snapshot_id;
        const bytes=new TextEncoder().encode(JSON.stringify({rfq,bids:data.bids[rfq.rfq_id],assumptions:body.assumptions,snapshot:body.input_snapshot_id}));
        body.input_hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes))).map(b=>b.toString(16).padStart(2,'0')).join('');body.scenario_id=body.input_hash.slice(0,24);
        try{sessionStorage.setItem('source360-scenario-'+body.scenario_id,JSON.stringify(body));}catch{}
      }else if(clean==='data-quality/status')body=data.quality;
      else if(clean==='documents'){const q=new URLSearchParams(String(url).split('?')[1]||'').get('q')||'';body=data.documents.filter(d=>d.text.toLowerCase().includes(q.toLowerCase()));}
      else if(/^documents\/[^/]+\/evidence$/.test(clean))body=data.evidence[clean.split('/')[1]];
      else if(/^rfqs\/[^/]+\/scenarios\//.test(clean)){body=JSON.parse(sessionStorage.getItem('source360-scenario-'+clean.split('/').at(-1))||'null');if(body&&body.rfq_id!==clean.split('/')[1])body=null;}
      if(body===undefined||body===null){body={detail:'Record unavailable in this synthetic snapshot'};status=404;}
    }catch(e){body={detail:e.message};status=422;}
    return new Response(JSON.stringify(body),{status,headers:{'Content-Type':'application/json'}});
  };
})();
