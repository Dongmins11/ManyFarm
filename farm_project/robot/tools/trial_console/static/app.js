let token='',state={snapshot:{},jobs:[]};
const $=id=>document.getElementById(id);
const names={robot_stop:'수확 시험 종료',robot_reconcile:'수동 복구 기록',dummy_recover:'더미 복구',dummy_prepare:'더미 준비',dummy_stop:'더미 정지',dummy_count:'수확 개수 설정',dummy_repeat:'1회 반복 허용'};
const statusNames={RUNNING:'처리 중',SUCCEEDED:'완료',FAILED:'실패 / 확인 필요'};
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Trial-Token':token},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.error||'접근 거절');return data;}
function render(){const s=state.snapshot||{},r=s.runtime?.status,d=s.dummy?.status,c=s.control;const busy=!!state.active||state.refreshing;
 document.querySelectorAll('[data-action],#refresh,#processList,#processStop').forEach(b=>b.disabled=busy);
 $('robot').textContent=r?`${r.state} · ${r.ready?'준비':'대기'}`:(s.runtime?.error?'조회 실패':'미확인');
 $('motion').textContent=s.runtime?.stopped?`정지 표본 ${s.runtime.odom_samples}개 · 적재 ${r?.loaded_count??'?'}`:'정지 확인 안 됨';
 $('dummy').textContent=d?`${d.state} · ${d.ready?'준비':'대기'}`:(s.dummy?.error?'조회 실패':'미확인');
 $('dummyDetail').textContent=d?`복구 ${d.recovery_required?'필요':'없음'} · ${d.error_code||'오류 없음'}`:'실제 팔 검증 아님';
 $('control').textContent=c?.ready?`Action ${c.ready.harvest?'연결':'대기'}`:'조회 실패/미조회';
 $('queue').textContent=c?.paused?`대기열 ${c.paused.harvest?'일시정지':'재개'} · ${c.blocked_reasons?.harvest||'차단 없음'}`:'';
 const remain=s.permit?Math.floor(s.permit.expires_at-Date.now()/1000):0;
 $('permit').textContent=s.permit?(remain>0?`${remain}초 남음`:'만료'):'미확인';
 $('repeatTarget').textContent=s.permit?.message||'허용 대상 ID는 성공 결과에서 확인합니다.';
 $('observed').textContent=s.observed_at?`최근 조회 ${new Date(s.observed_at*1000).toLocaleString()} · ${busy?'처리 중':'자동 이동 없음'} · 허용권은 서버 재시작/소비 후 달라질 수 있습니다.`:'상태를 새로 조회하세요.';
 renderArm();renderProcesses();
 $('raw').textContent=JSON.stringify(s,null,2);$('jobs').replaceChildren();
 for(const j of [...state.jobs].reverse()){const el=document.createElement('div');el.className='job';const b=document.createElement('b');b.textContent=names[j.action]||j.action;const span=document.createElement('span');span.textContent=statusNames[j.state]||j.state;el.append(b,span);if(j.result){const pre=document.createElement('pre');pre.textContent=JSON.stringify(j.result,null,2);el.append(pre)}$('jobs').append(el)}
}
async function poll(){try{const r=await fetch('/api/state');state=await r.json();render()}catch(e){$('notice').textContent='웹 서버 연결 끊김. 마지막 표시를 현재 상태로 판단하지 마세요.'}}
$('refresh').onclick=async()=>{try{await post('/api/refresh',{});await poll()}catch(e){$('notice').textContent=e.message}};
document.querySelectorAll('[data-action]').forEach(b=>b.onclick=async()=>{const action=b.dataset.action,body={action};
 if(action==='robot_stop'){if(!$('stopConfirm').checked)return $('notice').textContent='수확 시험 종료 확인란을 체크하세요.';body.confirmed=true;}
 if(action==='robot_reconcile'){if(!$('stationConfirm').checked)return $('notice').textContent='실제 스테이션 재배치 확인란을 체크하세요.';body.station_confirmed=true;body.snapshot=state.snapshot.robot?.journal_sha256;if(!body.snapshot)return $('notice').textContent='먼저 상태를 새로 조회하세요.';}
 if(action==='dummy_count'){body.count=Number($('count').value);if(!Number.isInteger(body.count)||body.count<0||body.count>1000)return $('notice').textContent='0~1000 정수를 입력하세요.';}
 try{await post('/api/action',body);$('notice').textContent=`${names[action]} 요청 접수. 아래 최종 결과를 확인하세요.`;await poll()}catch(e){$('notice').textContent=e.message}
});
(async()=>{token=(await(await fetch('/api/session')).json()).token;await poll();setInterval(poll,1500)})();

let lastEventsKey='';
const eventNames={requested:'웹 요청',queued:'준비 대기',sent:'ROS 요청 송신',goal_response:'Jetson Goal 수락 응답',feedback:'Jetson Feedback 수신',result:'Jetson 최종 Result',service_response:'Jetson 서비스 응답',cancel_ack:'Jetson 취소 접수 응답',not_sent:'미전송',unknown:'결과 미확인',service_timeout:'서비스 응답 미확인',reply:'시험 클라이언트 접수 응답',connected:'시험 연결됨',disconnected:'시험 연결 끊김'};
// 화면 요약만 계산한다. 명령 전송이나 작업 상태 변경은 하지 않는다.
function armOverview(a){
 const s=a.snapshot||{},r=s.runtime?.status||s.observations?.runtime?.payload,events=a.events||[];
 const request=[...events].reverse().find(e=>e.action==='harvest'&&['requested','queued','sent','result'].includes(e.kind));
 const own=request?events.filter(e=>e.id===request.id):[];
 const result=[...own].reverse().find(e=>e.kind==='result');
 const feedback=[...own].reverse().find(e=>e.kind==='feedback');
 const rejected=own.some(e=>(e.kind==='goal_response'&&e.accepted===false)||e.kind==='not_sent'||(e.kind==='reply'&&e.ok===false));
 const accepted=own.some(e=>(e.kind==='goal_response'&&e.accepted===true)||e.kind==='feedback');
 const uncertain=own.some(e=>e.kind==='unknown');
 const active=s.operation?.action==='harvest';
 const live=!!a.connected&&!a.stale&&!!r&&!s.runtime?.stale;
 let label='대기',tone='neutral',detail='수확 요청을 기다립니다.';
 const error=r&&(r.recovery_required||r.state==='ERROR'||(r.error_code&&r.error_code!=='NONE'));
 if(!live){label='상태 확인 필요';detail=a.connected?'Jetson 상태가 없거나 수신이 만료됐습니다.':'시험 연결이 끊겨 있습니다. 아래 결과는 마지막 기록입니다.';}
 else if(error){label='오류';tone='error';detail=[r.error_code,r.error_message,r.recovery_required?'복구 필요':''].filter(Boolean).join(' · ');}
 else if(active||request&&!result&&!rejected){label=uncertain?'결과 확인 필요':accepted?'수확 중':'요청 대기';tone=uncertain?'error':'working';detail=uncertain?'최종 결과를 확인하지 못했습니다.':accepted?'Jetson이 수락했습니다. 최종 결과를 기다립니다.':'준비 상태 또는 Goal 수락 응답을 기다립니다.';}
 else if(result){label=result.success?'수확 완료':result.payload?.result_code==='CANCELED'?'수확 취소':'오류';tone=result.success?'success':'error';detail=result.success?'최종 성공 결과를 수신했습니다.':[result.payload?.error_code,result.payload?.error_message,result.payload?.result_code].filter(Boolean).join(' · ');}
 else if(rejected){label='요청 거절 / 미전송';tone='error';detail='아래 송수신 기록에서 거절 사유를 확인하세요.';}
 else if(r.ready){label='준비됨';tone='success';detail='Jetson ready=true';}
 else{detail=[r.state,r.phase,'ready=false'].filter(Boolean).join(' · ');}
 const rp=result?.payload;
 const countPayload=rp||feedback?.payload;
 const count=countPayload?(rp?rp.harvested_count:countPayload.success_count):null;
 const failed=countPayload?.failed_count;
 const task=(request?.body?.goal||request?.payload)?.harvest_task?.task_id||rp?.task_id||feedback?.payload?.task_id;
 return {label,tone,detail,ready:live?(r.ready?'준비됨 · ready=true':'대기 · ready=false'):'준비 상태 미확인',
  count:Number.isInteger(count)?`${count}개`:'—',failed:Number.isInteger(failed)?`${failed}개`:'—',
  countLabel:result?'마지막 수확 결과':feedback?'진행 중 수확 개수':'수확 개수',
  last:result?`${result.success?'수확 완료':rp?.result_code==='CANCELED'?'수확 취소':'수확 실패'} · ${new Date(result.at*1000).toLocaleTimeString()}`:'최종 결과 없음',task:task||'수확 요청 없음'};
}
function renderArmOverview(a){
 const v=armOverview(a);$('armOverview').dataset.tone=v.tone;
 for(const [id,value] of Object.entries({armStatusLabel:v.label,armStatusDetail:v.detail,armReadyLabel:v.ready,armCount:v.count,armFailedCount:v.failed,armCountLabel:v.countLabel,armLastResult:v.last,armTaskLabel:v.task}))$(id).textContent=value;
}

function renderArm(){const a=state.arm||{},s=a.snapshot||{},r=s.observations?.runtime,c=s.observations?.control;
 renderArmOverview(a);
 const tm=s.observations?.transfer_test;
 const tmFresh=a.connected&&!a.stale&&tm&&Date.now()/1000-tm.at<=2.5;
 $('transferTestState').textContent=tmFresh?`배출 시험 모드: ${tm.payload.data?'켜짐 · transfer_active 시험값 사용':'꺼짐 · 운영 인계 상태 사용'}`:s.services?.transfer_test?'배출 시험 모드: 상태 수신 대기':'배출 시험 모드: 미연결 · Pinky 새 버전 적용 필요';
 $('armConnection').textContent=a.connected?`시험 연결됨 · ${a.stale?'상태 갱신 지연':'상태 갱신 중'}`:'시험 연결 안 됨 · 마지막 표시는 과거 기록';
 $('armRuntime').textContent=r?`${r.payload.state} · ${r.payload.ready?'준비':'대기'}`:'미수신';
 $('armRuntimeDetail').textContent=r?`${r.payload.mode} / ${r.payload.phase} / seq ${r.payload.sequence} / ${s.runtime?.stale?'수신 만료':'수신 유효'} / ${r.payload.error_code}`:'';
 $('armControl').textContent=c?`정지 ${c.payload.base_stopped} · 인계 ${c.payload.transfer_active}`:'미수신';
 $('armControlDetail').textContent=c?`seq ${c.payload.sequence} · 수신 ${new Date(c.at*1000).toLocaleTimeString()}`:'';
 $('armServers').textContent=s.servers?`수확 ${s.servers.harvest?'발견':'미발견'} / 배출 ${s.servers.discharge?'발견':'미발견'}`:'미확인';
 $('armOperation').textContent=s.operation?`${s.operation.action} / ${s.operation.phase}`:'활성 Goal 없음';
 $('armRaw').textContent=JSON.stringify(s,null,2);
 const filter=$('eventFilter').value;
 const events=(a.events||[]).filter(e=>e.kind!=='snapshot').filter(e=>filter==='all'||(filter==='sent'?['requested','queued','sent'].includes(e.kind):['goal_response','feedback','result','service_response','cancel_ack'].includes(e.kind)));
 const eventsKey=JSON.stringify([filter,events]);if(eventsKey===lastEventsKey)return;lastEventsKey=eventsKey;
 const opened=new Set([...$('armEvents').querySelectorAll('details[open]')].map(d=>d.dataset.key)),scroll=$('armEvents').scrollTop;
 $('armEvents').replaceChildren();for(const e of events.slice(-100).reverse()){const d=document.createElement('details'),t=document.createElement('summary'),p=document.createElement('pre');t.textContent=`${new Date(e.at*1000).toLocaleTimeString()} · ${e.action==='transfer_test'&&e.kind==='service_response'?'Pinky 시험 모드 응답':eventNames[e.kind]||e.kind} · ${e.action||''} ${e.id?.slice(0,8)||''}${e.accepted!==undefined?' · '+(e.accepted?'수락':'거절'):''}${e.success!==undefined?' · '+(e.success?'성공':'실패/취소'):''}${e.payload?.success!==undefined?' · '+(e.payload.success?'성공 응답':'실패 응답'):''}${e.ok===false?' · 접수 거절':''}${e.error?' · '+e.error:''}`;p.textContent=JSON.stringify(e,null,2);d.dataset.key=[e.kind,e.id,e.at].join(':');d.open=opened.has(d.dataset.key);d.append(t,p);$('armEvents').append(d)}$('armEvents').scrollTop=scroll;
}
function armNotice(message){$('notice').textContent=message;$('armNotice').textContent=message;}
function goal(){if(!$('armGoal').value.trim())throw new Error('수확 요청 내용이 비어 있습니다. 먼저 관측 자세로 초안을 만들거나 Goal JSON을 입력하세요.');const value=JSON.parse($('armGoal').value);if(!value.harvest_task)throw new Error('HarvestTask Goal JSON이 필요합니다.');return value;}
async function armCommand(action,extra={}){try{const body={action,...extra};if(['harvest','discharge','prepare','stop','cancel','recover','transfer_test','close_connection'].includes(action)){if(!$('armConfirm').checked)throw new Error('실제 팔 명령/시험 연결 정리 확인란을 체크하세요.');body.confirmed=true;}
 if(action==='harvest')body.goal=goal();
 if(action==='discharge')body.goal={transfer_id:$('transferId').value.trim()};
 if(action==='recover'){body.reconciled=$('armReconciled').checked;body.acknowledgement='DEVICE_AND_LOAD_RECONCILED';}
 const response=await post('/api/arm',body);armNotice(response.note||'시험 연결 요청 접수. 송수신 기록을 확인하세요.');await poll();}catch(e){armNotice(e.message)}}
document.querySelectorAll('[data-transfer-test]').forEach(b=>b.onclick=()=>armCommand('transfer_test',{enabled:b.dataset.transferTest==='true'}));
document.querySelectorAll('[data-arm]').forEach(b=>b.onclick=()=>armCommand(b.dataset.arm));
$('eventFilter').onchange=renderArm;
$('lookupHarvest').onclick=()=>{try{const g=goal();armCommand('get_operation',{kind:'harvest',key:JSON.stringify([g.robot_id,g.map_id,g.harvest_task.task_id,g.harvest_task.window_id])})}catch(e){$('notice').textContent=e.message}};
$('lookupDischarge').onclick=()=>armCommand('get_operation',{kind:'discharge',key:$('transferId').value.trim()});
$('draftGoal').onclick=()=>{try{const a=state.arm||{},s=a.snapshot||{},p=s.observations?.pose,r=s.observations?.robot?.payload;if(!a.connected||a.stale||!p||!r)return armNotice('초안 작성 불가: AMCL 자세 또는 로봇 상태가 아직 수신되지 않았습니다. 시험 연결을 확인하세요.');
 const n=Number($('expectedCount').value);if(!Number.isInteger(n)||n<0)return armNotice('expected_count는 0 이상 정수입니다.');
 const q=p.payload.pose.pose.orientation,position=p.payload.pose.pose.position,yaw=Math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z)),id=crypto.randomUUID();
 $('armGoal').value=JSON.stringify({robot_id:r.robot_id,map_id:r.map_id,harvest_task:{task_id:'manual-'+id,window_id:'manual-window-'+id,goal_pose:{frame_id:p.payload.header.frame_id,position,yaw},expected_count:n},timestamp:new Date().toISOString()},null,2);
 armNotice(`초안만 작성했습니다. 자세 측정 ${new Date((p.payload.header.stamp.sec+p.payload.header.stamp.nanosec/1e9)*1000).toLocaleString()}. 보존된 과거 표본일 수 있으므로 실제 현재 자세·map_id·요청 내용을 확인하세요. 전송하지 않았습니다.`);}catch(e){armNotice('초안 작성 실패: '+e.message)}};
let processResult=null;
function renderProcesses(){const g=$('processGroup').value;const job=[...state.jobs].reverse().find(j=>j.result?.group===g);if(job?.result){processResult=job.result;$('processView').textContent=JSON.stringify(job.result,null,2)}}
$('processGroup').onchange=()=>{processResult=null;$('processView').textContent='선택 그룹을 새로 조회하세요.'};
$('processList').onclick=async()=>{try{await post('/api/action',{action:'process_list',group:$('processGroup').value});await poll()}catch(e){$('notice').textContent=e.message}};
$('processStop').onclick=async()=>{try{if(!$('processConfirm').checked||!processResult?.snapshot||processResult.group!==$('processGroup').value)throw new Error('그룹을 조회하고 종료 확인란을 체크하세요.');await post('/api/action',{action:'process_stop',group:processResult.group,snapshot:processResult.snapshot,confirmed:true});await poll()}catch(e){$('notice').textContent=e.message}};
