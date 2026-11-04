import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import loadHighs from 'highs';
import {solveJoint} from '../web/joint-engine.mjs';
const highs=await loadHighs();
const input=JSON.parse(readFileSync('web/portfolio-input.json','utf8'));
const reference=JSON.parse(readFileSync('docs/portfolio-evaluation.json','utf8'));
test('all 25 browser joint awards match an independent CBC portfolio optimum',()=>{
  const actual=solveJoint(highs,input);
  assert.equal(actual.status,'feasible');assert.equal(actual.results.length,25);
  assert.ok(Math.abs(actual.risk_adjusted_objective-reference.risk_adjusted_objective)<.02);
  assert.ok(Math.abs(actual.landed_cost-reference.landed_cost)<.02);
  assert.ok(actual.supplier_capacity.every(c=>c.used<=c.capacity+.01));
});
test('insufficient shared capacity cannot expose invented savings',()=>{
  const result=solveJoint(highs,input,{capacity_factor:.1});
  assert.equal(result.status,'blocked');assert.equal(result.modeled_savings,null);
});
test('browser rejects duplicate capacity dimensions and nonfinite scenarios',()=>{
  assert.throws(()=>solveJoint(highs,{...input,capacities:[...input.capacities,input.capacities[0]]}),/capacity/);
  assert.throws(()=>solveJoint(highs,input,{capacity_factor:NaN}),/bounds/);
});
