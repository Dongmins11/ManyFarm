"""순서가 고정된 실물 시험 안내 도구. 각 단계 plan/execute를 따로 요청한다."""
import argparse
import fcntl
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import uuid
from sequence_support import STAGES, completed, digest, next_stage, require_wall_start

TOOLS=Path(__file__).resolve().parent


def save(path: Path, value: dict) -> None:
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    os.replace(temporary,path)


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['init','plan','execute'])
    parser.add_argument('--state',type=Path)
    parser.add_argument('--reference',type=Path)
    parser.add_argument('--exclusive',action='store_true')
    args=parser.parse_args()
    downloads=Path.home()/'Downloads'
    if args.mode=='init':
        folder=downloads/'harvest_restore_sequence'/str(time.time_ns());folder.mkdir(parents=True)
        path=folder/'state.json'
        save(path,dict(schema_version=1,cycle_id=uuid.uuid4().hex,completed=[],records={}))
        print('상태 파일:',path);print('다음 단계: departure plan (이동 없음)');return
    if args.state is None:parser.error('--state 필요')
    path=args.state.resolve()
    if not path.is_relative_to(downloads.resolve()):parser.error('상태 파일은 Downloads 아래여야 합니다.')
    with path.with_suffix('.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        state=json.loads(path.read_text());stage=next_stage(state)
        cycle=state['cycle_id'];records=state['records']
        if args.mode=='execute':
            if not args.exclusive or args.reference is None:parser.error('실행에는 --exclusive --reference 계획파일 필요')
            pending=state.get('pending',{})
            if (pending.get('stage')!=stage or pending.get('file')!=str(args.reference.resolve())
                    or pending.get('sha256')!=digest(args.reference)):
                raise RuntimeError('현재 단계의 검토한 계획 파일이 아닙니다.')
        elif state.get('executing'):raise RuntimeError('이전 실행 종료 미확인')
        for name,item in records.items():
            if digest(Path(item['result_file']))!=item['result_sha256']:
                raise RuntimeError('성공 기록 변경: '+name)
        departure=Path(records['departure']['result_file']) if records else None
        source=json.loads(departure.read_text()) if departure else None
        if stage=='wall':
            command=['bash',str(TOOLS/'wall_alignment_trial.bash'),args.mode,
                '--expected-session',source['odom_session'],'--cycle-id',cycle,
                '--output',str(path.parent/'wall')]
        else:
            command=['bash',str(TOOLS/'arc_isolated.bash'),args.mode,'--cycle-id',cycle]
            if stage!='departure':
                flag={'retreat':'--retreat-from','align':'--align-from','return':'--return-from'}[stage]
                previous=STAGES[STAGES.index(stage)-1]
                command += [flag,str(departure),'--after',records[previous]['proof_file']]
        if args.mode=='execute':command += ['--exclusive','--reference',str(args.reference.resolve())]
        log=path.parent/(str(time.time_ns())+'_'+stage+'_'+args.mode+'.log')
        if args.mode=='execute':
            state['executing']=stage;save(path,state)
        print('요청 단계:',stage,'/',args.mode,flush=True)
        process=None
        try:
            with log.open('w') as stream:
                process=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
                rc=process.wait()
            text=log.read_text(errors='replace')
            print(text,flush=True)
            if rc:raise RuntimeError('하위 단계 실패, 종료 코드 '+str(rc))
            if any(marker in text for marker in ('cannot use Destroyable','Traceback (most recent call last)','terminate called','SEVERE WARNING!!!')):
                raise RuntimeError('종료/콜백 예외 포함')
            candidates=[]
            for line in text.splitlines():
                if line.startswith('기록: '):
                    candidate=Path(line[4:].strip())
                    if candidate.suffix=='.json' and candidate.is_file():candidates.append(candidate)
            if len(candidates)!=1:raise RuntimeError('단계 결과 파일 식별 실패')
            result_file=candidates[0].resolve();result=json.loads(result_file.read_text())
            if result.get('cycle_id')!=cycle:raise RuntimeError('단계 cycle ID 불일치')
            if args.mode=='plan':
                if not result.get('ok') or result.get('phase')!='PLAN_ONLY':raise RuntimeError('계획 실패')
                if stage=='wall':require_wall_start(result,source)
                state['pending']=dict(stage=stage,file=str(result_file),sha256=digest(result_file))
                print('검토할 계획:',result_file)
            else:
                if not completed(result):raise RuntimeError('단계 성공·정지·종료 확인 실패')
                if stage=='departure' and not all(k in result for k in ('start_map_pose','start_odom_pose','final_pose','odom_session')):
                    raise RuntimeError('출발 기준 저장 누락')
                proof=dict(stage=stage,cycle_id=cycle,odom_session=result['odom_session'],
                    departure_sha256=digest(result_file) if stage=='departure' else digest(departure),
                    result_file=str(result_file),result_sha256=digest(result_file))
                proof_file=path.parent/(stage+'_proof.json');save(proof_file,proof)
                records[stage]=dict(proof,proof_file=str(proof_file))
                state['completed'].append(stage);state.pop('pending',None);state.pop('executing',None)
                print('단계 완료:',stage,'/ 다음:',STAGES[len(state['completed'])] if len(state['completed'])<len(STAGES) else '전체 완료')
            save(path,state)
        except BaseException as error:
            if process is not None and process.poll() is None:
                os.killpg(process.pid,signal.SIGINT)
                try:process.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    raise RuntimeError('하위 실행 종료 미확인: 상태 잠금 유지') from error
            if args.mode=='execute':
                state['failed']=str(error) or type(error).__name__;save(path,state)
            raise
        finally:print('단계 로그:',log)


if __name__=='__main__':main()
