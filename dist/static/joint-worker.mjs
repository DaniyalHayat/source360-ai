import loadHighs from './vendor/highs.mjs';
import {solveJoint} from './joint-engine.mjs';
const solver=loadHighs();
self.onmessage=async event=>{
  try{self.postMessage({result:solveJoint(await solver,event.data.input,event.data.params)});}
  catch(error){self.postMessage({error:error.message});}
};
