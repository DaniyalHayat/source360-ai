export function buildModel(input, params={}) {
  const a={capacity_factor:1,risk_penalty:100,max_share:.6,min_suppliers:2,max_suppliers:3,qualified_share:.3,...params};
  if(!Object.values(a).every(Number.isFinite)||a.capacity_factor<0||a.capacity_factor>2||a.risk_penalty<0||a.risk_penalty>500)throw new Error('Invalid scenario bounds');
  const rfqs=input.rfqs,pairs=[],groups=new Map(),budgets=new Map();
  if(!rfqs.length||rfqs.length>100||new Set(rfqs.map(r=>r.rfq_id)).size!==rfqs.length)throw new Error('Invalid event set');
  const dim=(sid,r)=>JSON.stringify([sid,String(r.capacity_period),r.unit]);
  for(const c of input.capacities){const key=dim(c.supplier_id,c);if(budgets.has(key)||!Number.isFinite(c.capacity)||c.capacity<0)throw new Error('Invalid shared capacity');budgets.set(key,c.capacity*a.capacity_factor);}
  for(const r of rfqs){
    if(!Number.isFinite(r.demand)||r.demand<=0||!Number.isFinite(r.baseline_unit_price))throw new Error('Invalid demand');
    const seen=new Set();
    for(const b of input.bids[r.rfq_id]||[]){
      if(seen.has(b.supplier_id)||!['capacity','unit_price_usd','logistics_unit_usd','fixed_cost','risk_score'].every(k=>Number.isFinite(b[k])&&b[k]>=0))throw new Error('Invalid bid');
      seen.add(b.supplier_id);
      const i=pairs.length,key=dim(b.supplier_id,r),p={r,b,x:'x'+i,y:'y'+i,key};pairs.push(p);
      if(!groups.has(key))groups.set(key,[]);groups.get(key).push(p);
    }
  }
  const term=(n,v)=>(n<0?' - ':' + ')+Math.abs(n).toPrecision(15)+' '+v;
  const sum=items=>items.length?items.map(([n,v])=>term(n,v)).join('').replace(/^ \+ /,''):'0 x0';
  const lines=['Minimize',' cost: '+sum(pairs.flatMap(p=>[[p.b.unit_price_usd+p.b.logistics_unit_usd+a.risk_penalty*p.b.risk_score/100,p.x],[p.b.fixed_cost,p.y]])),'Subject To'];
  let index=0;const constraint=(items,op,value)=>lines.push(' c'+index+++': '+sum(items)+' '+op+' '+Number(value).toPrecision(15));
  for(const r of rfqs){const ps=pairs.filter(p=>p.r===r);
    constraint(ps.map(p=>[1,p.x]),'=',r.demand);
    constraint(ps.map(p=>[1,p.y]),'>=',a.min_suppliers);constraint(ps.map(p=>[1,p.y]),'<=',a.max_suppliers);
    constraint(ps.filter(p=>p.b.qualified).map(p=>[1,p.x]),'>=',a.qualified_share*r.demand);
    for(const p of ps){constraint([[1,p.x],[-p.b.capacity,p.y]],'<=',0);constraint([[1,p.x]],'<=',a.max_share*r.demand);constraint([[1,p.x],[-.01*r.demand,p.y]],'>=',0);}
  }
  for(const [key,ps] of groups)constraint(ps.map(p=>[1,p.x]),'<=',budgets.get(key)||0);
  lines.push('Bounds',...pairs.map(p=>' 0 <= '+p.x),'Binary',...pairs.map(p=>' '+p.y),'End');
  return {lp:lines.join('\n'),pairs,groups,budgets,params:a};
}

export function solveJoint(highs,input,params={}) {
  const start=performance.now(),model=buildModel(input,params);
  const raw=highs.solve(model.lp,{output_flag:false,time_limit:12,mip_rel_gap:0});
  if(raw.Status!=='Optimal')return {status:'blocked',solver_status:raw.Status,modeled_savings:null,results:[],supplier_capacity:[]};
  const q=p=>raw.Columns[p.x]?.Primal??NaN,y=p=>raw.Columns[p.y]?.Primal??NaN,tol=.01;
  for(const p of model.pairs)if(!Number.isFinite(q(p))||!Number.isFinite(y(p))||Math.abs(y(p)-Math.round(y(p)))>1e-6||q(p)<-tol||q(p)>p.b.capacity*y(p)+tol||q(p)>p.r.demand*model.params.max_share+tol||q(p)+tol<.01*p.r.demand*y(p))throw new Error('Solver allocation failed independent validation');
  const results=input.rfqs.map(r=>{
    const ps=model.pairs.filter(p=>p.r===r),total=ps.reduce((s,p)=>s+q(p),0),selected=ps.reduce((s,p)=>s+y(p),0);
    if(Math.abs(total-r.demand)>tol||selected<model.params.min_suppliers-1e-6||selected>model.params.max_suppliers+1e-6||ps.filter(p=>p.b.qualified).reduce((s,p)=>s+q(p),0)+tol<r.demand*model.params.qualified_share)throw new Error('Solver event failed independent validation');
    const allocations=ps.filter(p=>q(p)>1e-5).map(p=>({supplier_id:p.b.supplier_id,name:p.b.canonical_name,quantity:q(p),cost:q(p)*(p.b.unit_price_usd+p.b.logistics_unit_usd)+p.b.fixed_cost,risk_score:p.b.risk_score}));
    return {rfq_id:r.rfq_id,title:r.title,unit:r.unit,demand:r.demand,baseline_cost:r.demand*r.baseline_unit_price,landed_cost:allocations.reduce((s,p)=>s+p.cost,0),allocations};
  });
  const supplier_capacity=[...model.groups].map(([key,ps])=>{const used=ps.reduce((s,p)=>s+q(p),0),capacity=model.budgets.get(key)||0;
    if(used>capacity+tol)throw new Error('Solver shared capacity failed independent validation');
    return {supplier_id:ps[0].b.supplier_id,name:ps[0].b.canonical_name,unit:ps[0].r.unit,capacity_period:ps[0].r.capacity_period,used,capacity,slack:capacity-used};});
  const baseline_cost=results.reduce((s,r)=>s+r.baseline_cost,0),landed_cost=results.reduce((s,r)=>s+r.landed_cost,0);
  return {status:'feasible',solver_status:raw.Status,solver:'HiGHS 1.15.4 WebAssembly',synthetic:true,realized_savings:false,
    baseline_cost,landed_cost,modeled_savings:baseline_cost-landed_cost,savings_pct:(baseline_cost-landed_cost)/baseline_cost,
    risk_adjusted_objective:raw.ObjectiveValue,solve_ms:performance.now()-start,input_snapshot_id:input.snapshot,params:model.params,results,supplier_capacity};
}
