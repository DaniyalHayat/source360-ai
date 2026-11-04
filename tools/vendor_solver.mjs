import {mkdir,copyFile} from 'node:fs/promises';
await mkdir('web/vendor',{recursive:true});
for(const file of ['highs.mjs','highs.wasm'])await copyFile('node_modules/highs/build/'+file,'web/vendor/'+file);
await copyFile('node_modules/highs/LICENSE','web/vendor/HiGHS-LICENSE.txt');
console.log('Pinned HiGHS browser runtime copied with its license');
