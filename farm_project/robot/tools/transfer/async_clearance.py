"""격리 시험의 충돌 계산 프로세스. ROS 수신/속도 콜백에서는 결과만 조회한다."""
import hashlib
import math
import multiprocessing as mp
import queue
import threading
import time


def grid_key(metadata: dict, data: bytes, region=None) -> str:
    """Fingerprint exactly check_grid's blocked-cell semantics.

    region=(fixed origin x,y, body circumscribed radius + allowed translation).
    Include every grid cell touching its closed square, with one extra cell at
    either edge for rounding. The square encloses the padded body at every yaw
    and every permitted translation. Unknown (255) remains blocked.
    Geometry changes always invalidate; time/layer/inflation values do not.
    """
    import json
    if region is None:
        # Test/helper fallback: full map comparison, using the same binary mask.
        geometry=metadata
        cells=data
    else:
        geometry={k:metadata[k] for k in ('frame','resolution','size_x','size_y','origin')}
        res=geometry['resolution'];nx=geometry['size_x'];ny=geometry['size_y']
        pos=geometry['origin']['position'];q=geometry['origin']['orientation']
        cx,cy,extent=region
        if (not all(math.isfinite(v) for v in (res,pos['x'],pos['y'],cx,cy,extent,*q.values()))
                or res<=0 or extent<=0 or nx<=0 or ny<=0 or len(data)!=nx*ny):
            raise RuntimeError('costmap 비교 입력 오류')
        if abs(q['x'])+abs(q['y'])+abs(q['z'])>1e-6 or abs(abs(q['w'])-1)>1e-6:
            raise RuntimeError('회전된 costmap은 지원하지 않습니다.')
        x0=max(0,math.floor((cx-extent-pos['x'])/res)-1)
        y0=max(0,math.floor((cy-extent-pos['y'])/res)-1)
        x1=min(nx,math.floor((cx+extent-pos['x'])/res)+2)
        y1=min(ny,math.floor((cy+extent-pos['y'])/res)+2)
        if x0>=x1 or y0>=y1:raise RuntimeError('회전 검사 영역이 지도 밖입니다.')
        geometry={**geometry,'region':list(region),'indices':[x0,y0,x1,y1]}
        cells=b''.join(data[y*nx+x0:y*nx+x1] for y in range(y0,y1))
    blocked=cells.translate(bytes([0]*254+[1,1]))
    return hashlib.sha256(json.dumps(geometry,sort_keys=True).encode()+blocked).hexdigest()


def solve(job: dict) -> float:
    from harvest_robot.transfer_retreat import alignment_clearance
    return alignment_clearance(job['pose'],job['target_yaw'],job['footprint'],job['grid'],
                               body_footprint=job['body_footprint'])


def _process(requests, responses, solver) -> None:
    while True:
        job=requests.get()
        if job is None:return
        start=time.monotonic()
        try:
            distance=solver(job)
            if not math.isfinite(distance) or distance<=0:raise ValueError('유효한 충돌 여유 없음')
            result={'job':job['certificate'],'clearance':distance,'elapsed_s':time.monotonic()-start}
        except BaseException as error:
            result={'error':str(error) or type(error).__name__,'elapsed_s':time.monotonic()-start}
        responses.put(result)


def usable(result: dict | None, current: tuple, key: str, now_ns: int, now: float,
           radius: float) -> tuple[bool,str]:
    if result is None:return False,'검사 결과 대기'
    if result.get('error'):raise RuntimeError(result['error'])
    job=result['job']
    if not all(math.isfinite(v) for v in (*current,*job['pose'],radius,result['clearance'])):raise RuntimeError('비유한 검사 결과/자세')
    if key!=job['grid_key']:return False,'costmap 변경: 재검사 대기'
    # Snapshot age does not expire a geometric proof. The caller MUST validate
    # current sensor freshness, footprint shape, frame, translation and map key
    # on every use. Drift below consumes the original clearance conservatively.
    old=job['pose']
    drift=math.dist(current[:2],old[:2])+radius*abs(math.atan2(math.sin(current[2]-old[2]),math.cos(current[2]-old[2])))
    # 기존 경로 전체의 여유에서 자세 변화의 최대 footprint 이동량을 뺀다.
    if result['clearance']-drift<=1e-9:return False,'자세 변화에 따른 충돌 여유 부족'
    return True,''


class AsyncClearance:
    def __init__(self, snapshot, *, solver=solve):
        self._snapshot=snapshot
        context=mp.get_context('spawn')
        self._requests=context.Queue(maxsize=1);self._responses=context.Queue(maxsize=1)
        self._process=context.Process(target=_process,args=(self._requests,self._responses,solver),daemon=True)
        self._lock=threading.Lock();self._stop=threading.Event()
        self._result=None;self._error='';self._statistics=[]
        self._process.start()
        self._thread=threading.Thread(target=self._feed,name='alignment_clearance_feed',daemon=True)
        self._thread.start()

    def _feed(self) -> None:
        pending=False;sent=0.
        try:
            while not self._stop.is_set():
                if not self._process.is_alive():raise RuntimeError('충돌 계산 프로세스 종료')
                if not pending:
                    job=self._snapshot()
                    self._requests.put_nowait(job);pending=True;sent=time.monotonic()
                try:result=self._responses.get(timeout=.01)
                except queue.Empty:
                    if time.monotonic()-sent>3.:raise RuntimeError('충돌 계산 응답 시간 초과')
                    continue
                with self._lock:
                    self._result=result;self._statistics.append(result['elapsed_s'])
                if result.get('error'):raise RuntimeError(result['error'])
                pending=False
        except BaseException as error:
            with self._lock:self._error=str(error) or type(error).__name__

    def check(self, current: tuple, key: str, now_ns: int, now: float, radius: float) -> tuple[bool,str]:
        with self._lock:result=self._result;error=self._error
        if error:raise RuntimeError(error)
        if not self._process.is_alive():raise RuntimeError('충돌 계산 프로세스 종료')
        return usable(result,current,key,now_ns,now,radius)

    def close(self) -> dict:
        self._stop.set();self._thread.join(timeout=1.)
        if self._process.is_alive():self._process.terminate()
        self._process.join(timeout=1.)
        if self._process.is_alive():self._process.kill();self._process.join(timeout=1.)
        for channel in (self._requests,self._responses):
            channel.cancel_join_thread();channel.close()
        if self._thread.is_alive() or self._process.is_alive():raise RuntimeError('충돌 계산 작업 종료 미확인')
        with self._lock:times=list(self._statistics)
        return {'calculations':len(times),'max_s':max(times,default=0.),
                'mean_s':sum(times)/len(times) if times else 0.,'closed':True}
