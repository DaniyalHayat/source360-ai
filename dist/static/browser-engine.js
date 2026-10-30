(function(root){
  'use strict';
  function combinations(items,k){if(k===0)return [[]];if(items.length<k)return [];return items.flatMap((item,i)=>combinations(items.slice(i+1),k-1).map(rest=>[item,...rest]));}
  function solveLinear(matrix,rhs){const n=rhs.length,a=matrix.map((r,i)=>[...r,rhs[i]]);for(let c=0;c<n;c++){let p=c;for(let r=c+1;r<n;r++)if(Math.abs(a[r][c])>Math.abs(a[p][c]))p=r;if(Math.abs(a[p][c])<1e-9)return null;[a[c],a[p]]=[a[p],a[c]];const divisor=a[c][c];for(let j=c;j<=n;j++)a[c][j]/=divisor;for(let r=0;r<n;r++)if(r!==c){const f=a[r][c];for(let j=c;j<=n;j++)a[r][j]-=f*a[c][j];}}return a.map(r=>r[n]);}
  function random(seed){let a=seed>>>0;return ()=>{a+=0x6D2B79F5;let t=a;t=Math.imul(t^t>>>15,t|1);t^=t+Math.imul(t^t>>>7,t|61);return ((t^t>>>14)>>>0)/4294967296;};}
  function triangular(rng,low,mode,high){const u=rng(),p=(mode-low)/(high-low);return u<p?low+Math.sqrt(u*(high-low)*(mode-low)):high-Math.sqrt((1-u)*(high-low)*(high-mode));}
  function quantile(sorted,p){const i=(sorted.length-1)*p,l=Math.floor(i);return sorted[l]+(sorted[Math.ceil(i)]-sorted[l])*(i-l);}
  function optimize(rfq,bids,params={}){
    const a={demand:rfq.demand,risk_penalty:100,max_share:.6,min_suppliers:2,max_suppliers:3,qualified_share:.3,capacity_factor:1,logistics_factor:1,draws:5000,seed:360,...params};
    if(!Number.isFinite(a.demand)||a.demand<1||a.demand>1e7||a.max_share<.1||a.max_share>1||a.qualified_share<0||a.qualified_share>1||a.min_suppliers<1||a.max_suppliers>4||a.min_suppliers>a.max_suppliers||a.risk_penalty<0||a.risk_penalty>1e4||a.capacity_factor<.1||a.capacity_factor>2||a.logistics_factor<0||a.logistics_factor>5||a.draws<1000||a.draws>10000)throw new Error('Review the scenario inputs; values are outside supported bounds.');
    const D=a.demand;let best=null;
    for(let mask=1;mask<(1<<bids.length);mask++){
      const chosen=bids.filter((_,i)=>mask&(1<<i)),n=chosen.length;if(n<a.min_suppliers||n>a.max_suppliers)continue;
      const low=Array(n).fill(.01*D),high=chosen.map(b=>Math.min(b.capacity*a.capacity_factor,a.max_share*D));
      if(high.some((v,i)=>v<low[i])||high.reduce((s,v)=>s+v,0)<D-1e-6)continue;
      const boundaries=[];
      for(let i=0;i<n;i++){const row=Array(n).fill(0);row[i]=1;boundaries.push({row,value:low[i]},{row,value:high[i]});}
      boundaries.push({row:chosen.map(b=>b.qualified?1:0),value:a.qualified_share*D});
      for(const active of combinations(boundaries,n-1)){
        const q=solveLinear([Array(n).fill(1),...active.map(c=>c.row)],[D,...active.map(c=>c.value)]);
        if(!q||q.some((v,i)=>v<low[i]-1e-5||v>high[i]+1e-5)||q.reduce((s,v,i)=>s+(chosen[i].qualified?v:0),0)<a.qualified_share*D-1e-5)continue;
        const objective=q.reduce((s,v,i)=>s+v*(chosen[i].unit_price_usd+chosen[i].logistics_unit_usd*a.logistics_factor+a.risk_penalty*chosen[i].risk_score/100)+chosen[i].fixed_cost,0);
        if(!best||objective<best.objective-1e-6)best={chosen,q,objective};
      }
    }
    const result={rfq_id:rfq.rfq_id,status:best?'Optimal':'Infeasible',allocations:[],synthetic:true,approval_status:'human_review_required',solver:'Exact subset and LP vertex enumeration (browser)',assumptions:a,timestamp:new Date().toISOString()};
    if(!best){result.message='No optimal award. Review demand, capacity, concentration and qualified-source requirements.';return result;}
    const allocations=best.chosen.map((b,i)=>({supplier_id:b.supplier_id,name:b.canonical_name,quantity:best.q[i],share:best.q[i]/D,unit_landed_cost:b.unit_price_usd+b.logistics_unit_usd*a.logistics_factor,cost:best.q[i]*(b.unit_price_usd+b.logistics_unit_usd*a.logistics_factor)+b.fixed_cost,risk_score:b.risk_score,capacity:b.capacity*a.capacity_factor,qualified:!!b.qualified,source_ref:b.source_ref}));
    const purchase=best.q.reduce((s,v,i)=>s+v*best.chosen[i].unit_price_usd,0),logistics=best.q.reduce((s,v,i)=>s+v*best.chosen[i].logistics_unit_usd*a.logistics_factor,0),fixed=best.chosen.reduce((s,b)=>s+b.fixed_cost,0),risk=best.q.reduce((s,v,i)=>s+v*best.chosen[i].risk_score/100*a.risk_penalty,0),landed=purchase+logistics+fixed,baseline=D*rfq.baseline_unit_price;
    const rng=random(a.seed),costs=[],savings=[];
    for(let i=0;i<a.draws;i++){const ds=triangular(rng,.9,1,1.15),common=triangular(rng,.94,1,1.12);let variable=0;for(const award of allocations)variable+=award.quantity*award.unit_landed_cost*common*triangular(rng,.97,1,1.04);const cost=variable*ds+fixed;costs.push(cost);savings.push(baseline*ds-cost);}
    costs.sort((x,y)=>x-y);savings.sort((x,y)=>x-y);const min=costs[0],width=(costs.at(-1)-min)/28,hist=Array(28).fill(0);for(const v of costs)hist[Math.min(27,Math.floor((v-min)/width))]++;
    Object.assign(result,{allocations,baseline_cost:baseline,landed_cost:landed,objective_value:landed+risk,objective_components:{purchase,logistics,fixed,risk_penalty:risk},savings:baseline-landed,savings_pct:(baseline-landed)/baseline,weighted_risk:allocations.reduce((s,v)=>s+v.share*v.risk_score,0),constraint_checks:{demand_met:Math.abs(allocations.reduce((s,v)=>s+v.quantity,0)-D)<.01,capacity_respected:allocations.every(v=>v.quantity<=v.capacity+.01),concentration_respected:allocations.every(v=>v.share<=a.max_share+1e-6),source_count_respected:allocations.length>=a.min_suppliers&&allocations.length<=a.max_suppliers,qualified_share_respected:allocations.filter(v=>v.qualified).reduce((s,v)=>s+v.share,0)>=a.qualified_share-1e-6},uncertainty:{draws:a.draws,seed:a.seed,cost_p10:quantile(costs,.1),cost_p50:quantile(costs,.5),cost_p90:quantile(costs,.9),savings_p10:quantile(savings,.1),savings_p90:quantile(savings,.9),histogram:hist.map((count,i)=>({cost:min+(i+.5)*width,count})),method:'Fixed award mix; correlated triangular prices and demand. Stress costs only; does not assert stressed capacity feasibility. Seeded browser generator; draws differ from the NumPy service.'}});
    return result;
  }
  root.Source360Engine={optimize};
  if(typeof module!=='undefined')module.exports={optimize};
})(typeof globalThis!=='undefined'?globalThis:this);
