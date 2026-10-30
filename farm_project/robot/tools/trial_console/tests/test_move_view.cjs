// 브라우저 명령을 보내지 않고 실제 화면 스크립트의 목표·서버·종료 표시를 검사한다.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const elements=new Map();const el=id=>{if(!elements.has(id))elements.set(id,{value:'',textContent:'',checked:false});return elements.get(id)};
const ctx={document:{getElementById:el,querySelectorAll:()=>[]},fetch:()=>new Promise(()=>{}),crypto:{randomUUID:()=> 'offline'},setInterval:()=>{},console};vm.createContext(ctx);
vm.runInContext(fs.readFileSync('robot/tools/trial_console/static/app.js','utf8'),ctx);
vm.runInContext("state.arm={navigation:{node_id:14},connected:true,stale:false,snapshot:{servers:{move_trial:true}},events:[]};renderMove()",ctx);
assert(el('moveTrial').textContent.includes('14번'));assert(!el('moveTrial').disabled);
vm.runInContext("state.arm.events=[{id:'a',action:'move_trial',kind:'requested'},{id:'a',kind:'goal_response',accepted:true}];renderMove()",ctx);
assert(el('moveStatus').textContent.includes('수락'));
vm.runInContext("state.arm.events.push({id:'a',kind:'result',success:true,payload:{error_code:0}});renderMove()",ctx);
assert(el('moveStatus').textContent.includes('완료'));
vm.runInContext("state.arm.snapshot.servers.move_trial=false;renderMove()",ctx);assert(el('moveTrial').disabled);
const html=fs.readFileSync('robot/tools/trial_console/static/index.html','utf8'),ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length);
console.log('move view: configured target, server discovery, acceptance, terminal result, unique IDs passed');
