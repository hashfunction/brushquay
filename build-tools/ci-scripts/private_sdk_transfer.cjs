// Copyright 2026 Trieflow LLC. SPDX-License-Identifier: GPL-3.0-or-later
// Private build-input transport only. No downloaded input is executed.
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {Transform}=require('node:stream'),{pipeline}=require('node:stream/promises');
const {spawn,execFileSync}=require('node:child_process');
const MAGIC=Buffer.from('BRSTSDK1'),HEADER=36;
function requireThat(ok,message){if(!ok)throw new Error(message);}
function canonical(value){return JSON.stringify(value&&typeof value==='object'&&!Array.isArray(value)?Object.fromEntries(Object.keys(value).sort().map(k=>[k,JSON.parse(canonical(value[k]))])):Array.isArray(value)?value.map(v=>JSON.parse(canonical(v))):value);}
function noLinks(file){let p=path.resolve(file);for(;;){if(linkExists(p))requireThat(!fs.lstatSync(p).isSymbolicLink(),'Link/reparse input refused');const parent=path.dirname(p);if(parent===p)break;p=parent;}}
function linkExists(p){try{fs.lstatSync(p);return true;}catch(e){if(e.code==='ENOENT')return false;throw e;}}
function regular(file){noLinks(file);const s=fs.lstatSync(file);requireThat(s.isFile(),'Regular file required');return s;}
function json(file){requireThat(regular(file).size<=1024*1024,'Unbounded metadata');return JSON.parse(fs.readFileSync(file,'utf8'));}
async function measure(file){regular(file);let bytes=0;const hash=crypto.createHash('sha256');for await(const chunk of fs.createReadStream(file)){bytes+=chunk.length;hash.update(chunk);}return {bytes,sha256:hash.digest('hex')};}
async function verify(file,row){const m=await measure(file);requireThat(m.bytes===row.bytes&&m.sha256===row.sha256,'Original file hash/size differs');}
function meter(row){let bytes=0;const hash=crypto.createHash('sha256');return new Transform({transform(chunk,_,next){bytes+=chunk.length;if(bytes>row.bytes)return next(new Error('Input exceeds exact locked size'));hash.update(chunk);next(null,chunk);},flush(next){next(bytes===row.bytes&&hash.digest('hex')===row.sha256?null:new Error('Original file hash/size differs'));}});}
function keyFromEnv(){const text=process.env.BRISTLUNE_SDK_TRANSFER_KEY;requireThat(typeof text==='string'&&/^[0-9a-f]{64}$/.test(text),'Dedicated 32-byte transfer key is required');return Buffer.from(text,'hex');}
function aad(row,context){return Buffer.from(canonical({schema:1,context,file:row}));}
function temporary(output){noLinks(path.dirname(output));requireThat(!linkExists(output),'Existing destination is preserved');return output+'.partial-'+crypto.randomBytes(12).toString('hex');}
function publish(temp,output){fs.linkSync(temp,output);fs.unlinkSync(temp);}
async function sealFile(input,output,row,context,key){
 regular(input);const temp=temporary(output),nonce=crypto.randomBytes(12),header=Buffer.concat([MAGIC,nonce,Buffer.alloc(16)]);
 try{
  fs.writeFileSync(temp,header,{flag:'wx'});
  const cipher=crypto.createCipheriv('aes-256-gcm',key,nonce);cipher.setAAD(aad(row,context));
  await pipeline(fs.createReadStream(input),meter(row),cipher,fs.createWriteStream(temp,{flags:'r+',start:HEADER}));
  const fd=fs.openSync(temp,'r+');try{fs.writeSync(fd,cipher.getAuthTag(),0,16,20);fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  publish(temp,output);
 }finally{if(linkExists(temp))fs.unlinkSync(temp);}
}
async function openFile(input,output,row,context,key){
 requireThat(regular(input).size===row.bytes+HEADER,'Encrypted file size differs');
 const fd=fs.openSync(input,'r'),header=Buffer.alloc(HEADER);try{requireThat(fs.readSync(fd,header,0,HEADER,0)===HEADER,'Truncated encrypted header');}finally{fs.closeSync(fd);}
 requireThat(header.subarray(0,8).equals(MAGIC),'Unknown encrypted envelope');
 const temp=temporary(output);
 try{
  const decipher=crypto.createDecipheriv('aes-256-gcm',key,header.subarray(8,20));decipher.setAAD(aad(row,context));decipher.setAuthTag(header.subarray(20,36));
  await pipeline(fs.createReadStream(input,{start:HEADER}),decipher,meter(row),fs.createWriteStream(temp,{flags:'wx'}));
  const fd=fs.openSync(temp,'r+');try{fs.fsyncSync(fd);}finally{fs.closeSync(fd);}
  publish(temp,output);
 }finally{if(linkExists(temp))fs.unlinkSync(temp);}
}
function expectedContext(pin,env=process.env){
 const c={repository:env.GITHUB_REPOSITORY,sourceCommit:env.GITHUB_SHA,run:env.GITHUB_RUN_ID,attempt:env.GITHUB_RUN_ATTEMPT};
 requireThat(c.repository===pin.repository&&/^[0-9a-f]{40}$/.test(c.sourceCommit||'')&&/^\d+$/.test(c.run||'')&&/^\d+$/.test(c.attempt||''),'Exact source/run/attempt required');return c;
}
function validatePin(pin,lock){
 requireThat(pin.schema===1&&pin.repository==='hashfunction/brushquay'&&pin.releaseId===393572515&&pin.tag==='bristlune-locked-build-inputs-20260922'&&pin.files.length===2,'Exact private input binding required');
 const qt=lock.packages.filter(p=>p.name==='ext_qt');requireThat(qt.length===1,'Exact locked Qt owner required');
 requireThat(pin.files[0].sha256===qt[0].sha256&&pin.files[0].bytes===qt[0].bytes&&pin.files[1].sha256===qt[0].metadata.sha256&&pin.files[1].bytes===878,'Mirror differs from original dependency lock');
 requireThat(new Set(pin.files.map(f=>f.assetId)).size===2&&new Set(pin.files.map(f=>f.sha256)).size===2&&pin.files.every(f=>Number.isSafeInteger(f.assetId)&&f.assetId>0&&Number.isSafeInteger(f.bytes)&&f.bytes>0&&/^[0-9a-f]{64}$/.test(f.sha256)&&typeof f.name==='string'),'Invalid private asset binding');
}
function validateRelease(release,pin){
 requireThat(release.id===pin.releaseId&&release.tag_name===pin.tag&&release.draft===true&&release.published_at===null,'Exact unpublished draft required');
 for(const row of pin.files){const matches=release.assets.filter(a=>a.id===row.assetId);requireThat(matches.length===1,'Exact draft asset required');const a=matches[0];requireThat(a.name===row.name&&a.size===row.bytes&&a.digest==='sha256:'+row.sha256&&a.state==='uploaded','Original draft asset hash/size differs');}
}
function validateTransfer(value,pin,context){requireThat(canonical(value)===canonical({schema:1,context,files:pin.files}),'Foreign source/run/attempt or input transfer refused');}
function githubEnv(){return Object.fromEntries(Object.entries(process.env).filter(([k])=>k!=='BRISTLUNE_SDK_TRANSFER_KEY'));}
function api(pin,endpoint){return JSON.parse(execFileSync('gh',['api','repos/'+pin.repository+'/'+endpoint],{encoding:'utf8',maxBuffer:1024*1024,timeout:60000,env:githubEnv()}));}
async function download(pin,row,target,start=spawn){
 const temp=temporary(target);let child;
 try{
  child=start('gh',['api','repos/'+pin.repository+'/releases/assets/'+row.assetId,'-H','Accept: application/octet-stream'],{stdio:['ignore','pipe','pipe'],windowsHide:true,env:githubEnv()});
  // Never emit response bodies or credentials. A nonzero API result is retained
  // as a bounded status; the exact source asset ID is in the surrounding receipt.
  let diagnostic=Buffer.alloc(0);child.stderr.on('data',b=>{if(diagnostic.length<4096)diagnostic=Buffer.concat([diagnostic,b.subarray(0,4096-diagnostic.length)]);});
  const exit=new Promise((resolve,reject)=>{child.on('error',reject);child.on('close',code=>resolve(code));});
  const timer=setTimeout(()=>child.kill(),600000);
  try{const stream=pipeline(child.stdout,meter(row),fs.createWriteStream(temp,{flags:'wx'})).catch(e=>{child.kill();throw e;});const [flow,code]=await Promise.allSettled([stream,exit]);const http=(diagnostic.toString().match(/HTTP (\d{3})/)||[])[1]||'unreported';requireThat(flow.status==='fulfilled'&&code.status==='fulfilled'&&code.value===0,'Private asset download/hash failed (asset '+row.assetId+', HTTP '+http+', exit '+(code.status==='fulfilled'?code.value:'unavailable')+')');}finally{clearTimeout(timer);}
  publish(temp,target);
 }finally{if(child&&child.exitCode===null)child.kill();if(linkExists(temp))fs.unlinkSync(temp);}
}
async function fetchTransfer(pin,context,key,transfer,receipt,source={api,download}){
 noLinks(path.dirname(transfer));fs.mkdirSync(transfer);const work=fs.mkdtempSync(path.join(path.dirname(transfer),'.private-sdk-'));
 const result={schema:1,context,scope:'private SDK fetch/encryption only; no input execution',passed:false,files:pin.files};
 try{
  validateRelease(source.api(pin,'releases/'+pin.releaseId),pin);
  for(const row of pin.files){const raw=path.join(work,row.sha256);await source.download(pin,row,raw);await sealFile(raw,path.join(transfer,row.sha256+'.aesgcm'),row,context,key);fs.unlinkSync(raw);}
  validateRelease(source.api(pin,'releases/'+pin.releaseId),pin);
  fs.writeFileSync(path.join(transfer,'transfer.json'),canonical({schema:1,context,files:pin.files}),{flag:'wx'});
  result.passed=true;result.draftVerifiedBeforeAndAfter=true;
 }catch(e){result.error=e.message;throw e;}finally{
  fs.writeFileSync(receipt,JSON.stringify(result,null,2)+'\n',{flag:'wx'});
  // Only delete the two task-owned raw filenames; preserve any unexpected entry.
  for(const row of pin.files){const file=path.join(work,row.sha256);if(linkExists(file)){regular(file);fs.unlinkSync(file);}}
  if(fs.readdirSync(work).length===0)fs.rmdirSync(work);
 }
}
async function seedTransfer(pin,context,key,transfer,cache,receipt){
 noLinks(transfer);validateTransfer(json(path.join(transfer,'transfer.json')),pin,context);
 const expected=['transfer.json',...pin.files.map(r=>r.sha256+'.aesgcm')].sort();requireThat(canonical(fs.readdirSync(transfer).sort())===canonical(expected),'Unexpected transfer file');
 noLinks(cache);if(!fs.existsSync(cache))fs.mkdirSync(cache);
 const result={schema:1,context,scope:'authenticated private SDK cache preseed only',passed:false,files:pin.files};
 try{for(const row of pin.files)await openFile(path.join(transfer,row.sha256+'.aesgcm'),path.join(cache,row.sha256),row,context,key);result.passed=true;}
 catch(e){result.error=e.message;throw e;}finally{fs.writeFileSync(receipt,JSON.stringify(result,null,2)+'\n',{flag:'wx'});}
}
async function main(){
 const action=process.argv[2];requireThat(action==='fetch'||action==='seed','Expected fetch or seed');
 const pin=json(path.join(__dirname,'private-sdk-inputs.json')),lock=json(path.join(__dirname,'brushquay-dependency-lock.json'));validatePin(pin,lock);
 const context=expectedContext(pin);requireThat(execFileSync('git',['rev-parse','HEAD'],{encoding:'utf8'}).trim()===context.sourceCommit,'Current checkout differs from workflow source');
 const base=path.resolve('.brushquay');noLinks(base);fs.mkdirSync(base,{recursive:true});const evidence=path.join(base,'evidence');noLinks(evidence);fs.mkdirSync(evidence,{recursive:true});
 const transfer=path.join(base,'encrypted-sdk-transfer'),receipt=path.join(evidence,'private-sdk-'+action+'.json'),key=keyFromEnv();
 try{if(action==='fetch')await fetchTransfer(pin,context,key,transfer,receipt);else await seedTransfer(pin,context,key,transfer,path.join(base,'cache'),receipt);}finally{key.fill(0);}
}
module.exports={sealFile,openFile,validatePin,validateRelease,validateTransfer,expectedContext,measure,fetchTransfer,seedTransfer,download};
if(require.main===module)main().catch(e=>{console.error('Private SDK transfer refused: '+e.message);process.exitCode=1;});
