// Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),crypto=require('node:crypto');
const transport=require('../private_sdk_transfer.cjs');
const {spawn}=require('node:child_process');
function fixture(t){const root=fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(),'bristlune-crypto-')));t.after(()=>fs.rmSync(root,{recursive:true}));const bytes=Buffer.alloc(1024*1024+37,0x49),input=path.join(root,'input');fs.writeFileSync(input,bytes);return {root,input,bytes,key:crypto.randomBytes(32),row:{assetId:12,name:'fixture',bytes:bytes.length,sha256:crypto.createHash('sha256').update(bytes).digest('hex')},context:{repository:'hashfunction/brushquay',sourceCommit:'c'.repeat(40),run:'42',attempt:'1'}};}
test('streamed authenticated roundtrip keeps ciphertext distinct and nonce random',async t=>{
 const f=fixture(t),a=path.join(f.root,'one.enc'),b=path.join(f.root,'two.enc'),out=path.join(f.root,'restored');
 await transport.sealFile(f.input,a,f.row,f.context,f.key);await transport.sealFile(f.input,b,f.row,f.context,f.key);
 assert.equal(fs.statSync(a).size,f.bytes.length+36);assert.notDeepEqual(fs.readFileSync(a),fs.readFileSync(b));assert.equal(fs.readFileSync(a).includes(f.bytes),false);
 await transport.openFile(a,out,f.row,f.context,f.key);assert.deepEqual(fs.readFileSync(out),f.bytes);
});
test('ciphertext, tag, nonce and key tampering never admits plaintext',async t=>{
 const f=fixture(t),sealed=path.join(f.root,'sealed');await transport.sealFile(f.input,sealed,f.row,f.context,f.key);
 for(const mode of ['ciphertext','tag','nonce','key','truncated']){
  const data=fs.readFileSync(sealed),input=path.join(f.root,mode+'.enc'),out=path.join(f.root,mode+'.out');
  if(mode==='ciphertext')data[77]^=1;if(mode==='tag')data[20]^=1;if(mode==='nonce')data[8]^=1;
  fs.writeFileSync(input,mode==='truncated'?data.subarray(0,data.length-1):data);
  await assert.rejects(transport.openFile(input,out,f.row,f.context,mode==='key'?crypto.randomBytes(32):f.key));assert.equal(fs.existsSync(out),false);
 }
 assert.equal(fs.readdirSync(f.root).some(n=>n.includes('.partial-')),false);
});
test('source, run, attempt and original file identity are authenticated',async t=>{
 const f=fixture(t),sealed=path.join(f.root,'sealed');await transport.sealFile(f.input,sealed,f.row,f.context,f.key);
 for(const field of ['sourceCommit','run','attempt'])await assert.rejects(transport.openFile(sealed,path.join(f.root,field),f.row,{...f.context,[field]:'foreign'},f.key));
 for(const row of [{...f.row,sha256:'f'.repeat(64)},{...f.row,bytes:f.row.bytes+1},{...f.row,assetId:13}])await assert.rejects(transport.openFile(sealed,path.join(f.root,'foreign'),row,f.context,f.key));
 assert.equal(fs.readdirSync(f.root).some(n=>n.includes('.partial-')),false);
});
test('wrong original input and foreign existing destination are preserved',async t=>{
 const f=fixture(t),sealed=path.join(f.root,'sealed'),out=path.join(f.root,'existing');
 await assert.rejects(transport.sealFile(f.input,sealed,{...f.row,sha256:'f'.repeat(64)},f.context,f.key));assert.equal(fs.existsSync(sealed),false);
 await transport.sealFile(f.input,sealed,f.row,f.context,f.key);fs.writeFileSync(out,'protected');
 await assert.rejects(transport.openFile(sealed,out,f.row,f.context,f.key));assert.equal(fs.readFileSync(out,'utf8'),'protected');
 assert.deepEqual(fs.readFileSync(f.input),f.bytes);
});
test('linked input and output directory are refused',async t=>{
 const f=fixture(t),linked=path.join(f.root,'linked'),dir=path.join(f.root,'dir');fs.symlinkSync(f.input,linked,'file');fs.symlinkSync(f.root,dir,'junction');
 await assert.rejects(transport.sealFile(linked,path.join(f.root,'enc'),f.row,f.context,f.key));
 await assert.rejects(transport.sealFile(f.input,path.join(dir,'enc'),f.row,f.context,f.key));
 assert.deepEqual(fs.readFileSync(f.input),f.bytes);
});
test('exact original lock and unpublished draft metadata are required',()=>{
 const pin=require('../private-sdk-inputs.json'),lock=require('../brushquay-dependency-lock.json');transport.validatePin(pin,lock);
 const good={id:pin.releaseId,tag_name:pin.tag,draft:true,published_at:null,assets:pin.files.map(f=>({id:f.assetId,name:f.name,size:f.bytes,digest:'sha256:'+f.sha256,state:'uploaded'}))};
 transport.validateRelease(good,pin);
 for(const mutate of [r=>r.draft=false,r=>r.published_at='now',r=>r.id++,r=>r.tag_name='foreign',r=>r.assets.pop(),r=>r.assets.push(r.assets[0]),r=>r.assets[0].digest='sha256:'+'f'.repeat(64),r=>r.assets[0].size++,r=>r.assets[0].state='starter']){const r=structuredClone(good);mutate(r);assert.throws(()=>transport.validateRelease(r,pin));}
 const changed=structuredClone(lock);changed.packages.find(p=>p.name==='ext_qt').sha256='f'.repeat(64);assert.throws(()=>transport.validatePin(pin,changed));
});
test('manifest cannot replay another source, run, attempt or extra input',()=>{
 const pin=require('../private-sdk-inputs.json'),context={repository:pin.repository,sourceCommit:'c'.repeat(40),run:'42',attempt:'1'},good={schema:1,context,files:pin.files};
 transport.validateTransfer(good,pin,context);
 for(const mutate of [m=>m.context.sourceCommit='d'.repeat(40),m=>m.context.run='43',m=>m.context.attempt='2',m=>m.files.pop(),m=>m.extra=true]){const m=structuredClone(good);mutate(m);assert.throws(()=>transport.validateTransfer(m,pin,context));}
 assert.throws(()=>transport.expectedContext(pin,{GITHUB_REPOSITORY:'foreign',GITHUB_SHA:'c'.repeat(40),GITHUB_RUN_ID:'42',GITHUB_RUN_ATTEMPT:'1'}));
});
test('actual fetch and seed callers transfer only ciphertext and exact originals',async t=>{
 const f=fixture(t),metadata=Buffer.alloc(878,0x65),meta={assetId:13,name:'metadata',bytes:878,sha256:crypto.createHash('sha256').update(metadata).digest('hex')};
 const pin={releaseId:1,tag:'fixture',repository:f.context.repository,files:[f.row,meta]},transfer=path.join(f.root,'transfer'),cache=path.join(f.root,'cache');let observations=0;
 const source={api(){observations++;return {id:pin.releaseId,tag_name:pin.tag,draft:true,published_at:null,assets:pin.files.map(r=>({id:r.assetId,name:r.name,size:r.bytes,digest:'sha256:'+r.sha256,state:'uploaded'}))};},async download(_,r,file){fs.writeFileSync(file,r.assetId===12?f.bytes:metadata,{flag:'wx'});}};
 await transport.fetchTransfer(pin,f.context,f.key,transfer,path.join(f.root,'fetch.json'),source);assert.equal(observations,2);
 assert.deepEqual(fs.readdirSync(transfer).sort(),['transfer.json',...pin.files.map(r=>r.sha256+'.aesgcm')].sort());
 assert.equal(fs.readdirSync(f.root).some(n=>n.startsWith('.private-sdk-')),false);
 await transport.seedTransfer(pin,f.context,f.key,transfer,cache,path.join(f.root,'seed.json'));
 assert.deepEqual(fs.readFileSync(path.join(cache,f.row.sha256)),f.bytes);assert.deepEqual(fs.readFileSync(path.join(cache,meta.sha256)),metadata);
 assert.equal(JSON.parse(fs.readFileSync(path.join(f.root,'seed.json'))).passed,true);
 await assert.rejects(transport.seedTransfer(pin,{...f.context,attempt:'2'},f.key,transfer,path.join(f.root,'foreign-cache'),path.join(f.root,'foreign.json')));assert.equal(fs.existsSync(path.join(f.root,'foreign-cache')),false);
});
test('real streaming child download refuses oversized, corrupt and failed responses',async t=>{
 const f=fixture(t),pin={repository:f.context.repository};
 const oldKey=process.env.BRISTLUNE_SDK_TRANSFER_KEY;process.env.BRISTLUNE_SDK_TRANSFER_KEY=crypto.randomBytes(32).toString('hex');t.after(()=>{if(oldKey===undefined)delete process.env.BRISTLUNE_SDK_TRANSFER_KEY;else process.env.BRISTLUNE_SDK_TRANSFER_KEY=oldKey;});
 for(const mode of ['valid','oversized','corrupt','http403']){
  const out=path.join(f.root,mode),start=(command,args,options)=>{
   assert.equal(command,'gh');assert.deepEqual(args,['api','repos/'+pin.repository+'/releases/assets/12','-H','Accept: application/octet-stream']);assert.equal(options.env.BRISTLUNE_SDK_TRANSFER_KEY,undefined);
   const code=mode==='http403'?"process.stderr.write('HTTP 403');process.exit(1)":'process.stdout.write(Buffer.alloc('+ (f.row.bytes+(mode==='oversized'?1:0))+','+(mode==='corrupt'?0x50:0x49)+'))';
   return spawn(process.execPath,['-e',code],options);
  };
  if(mode==='valid'){await transport.download(pin,f.row,out,start);assert.deepEqual(fs.readFileSync(out),f.bytes);}
  else{await assert.rejects(transport.download(pin,f.row,out,start),mode==='http403'?/HTTP 403/:/download\/hash failed/);assert.equal(fs.existsSync(out),false);}
 }
 assert.equal(fs.readdirSync(f.root).some(n=>n.includes('.partial-')),false);
});
