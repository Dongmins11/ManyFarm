// 복귀 상태 요약만 검사하며 HTTP/ROS 명령은 보내지 않는다.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8'),ctx={};vm.createContext(ctx);
vm.runInContext(src.slice(src.indexOf('function stationView('),src.indexOf('function renderStation(')),ctx);
const a={connected:true,stale:false,station:{node_id:18},snapshot:{servers:{station_return:true}},events:[]};
assert.equal(ctx.stationView(a).label,'복귀 서버 발견');
a.events=[{kind:'requested',action:'station_return',id:'a'}];assert(ctx.stationView(a).label.includes('수락 대기'));
a.events.push({kind:'goal_response',id:'a',accepted:true});assert.equal(ctx.stationView(a).label,'복귀 진행 중');
a.events.push({kind:'result',id:'a',success:true,payload:{result_code:'SUCCESS',docked:false}});assert(ctx.stationView(a).label.includes('완료'));assert(ctx.stationView(a).label.includes('false'));
a.events.push({kind:'requested',action:'station_return',id:'b'},{kind:'goal_response',id:'b',accepted:false});assert.equal(ctx.stationView(a).label,'복귀 거절 / 미전송');
a.events.push({kind:'unknown',id:'b'});assert(ctx.stationView(a).label.includes('미확인'));
a.connected=false;assert(ctx.stationView(a).label.includes('연결 상태 미확인'));
console.log('station view: discovery, pending, accepted, success/docked=false, rejection, unknown, disconnect passed');
