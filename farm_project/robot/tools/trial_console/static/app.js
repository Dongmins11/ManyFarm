let token='',state={snapshot:{},jobs:[]};
const $=id=>document.getElementById(id);
const names={robot_stop:'수확 시험 종료',robot_reconcile:'수동 복구 기록',dummy_recover:'더미 복구',dummy_prepare:'더미 준비',dummy_stop:'더미 정지',dummy_count:'수확 개수 설정',dummy_repeat:'1회 반복 허용'};
const statusNames={RUNNING:'처리 중',SUCCEEDED:'완료',FAILED:'실패 / 확인 필요'};
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Trial-Token':token},body:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw new Error(data.error||'접근 거절');return data;}
function render(){const s=state.snapshot||{},r=s.runtime?.status,d=s.dummy?.status,c=s.control;const busy=!!state.active||state.refreshing;
 document.querySelectorAll('button').forEach(b=>b.disabled=busy);
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
