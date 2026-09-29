"""동일 PC의 Isaac/ROS 프로세스 연결. 영상은 이 경로로 전송하지 않습니다."""
import json
import math
import socket
import time


class LocalDatagrams:
    def __init__(self,bind_port,peer_port):
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.bind(('127.0.0.1',int(bind_port)))
        self.socket.setblocking(False)
        self.peer=('127.0.0.1',int(peer_port))

    def send(self,payload):
        raw=json.dumps(dict(payload,version=1),allow_nan=False,separators=(',',':')).encode()
        if len(raw)>60000:raise ValueError('내부 메시지 크기 초과')
        try:self.socket.sendto(raw,self.peer)
        except BlockingIOError:pass

    def receive(self):
        result=[]
        for _ in range(100):
            try:raw,peer=self.socket.recvfrom(65535)
            except BlockingIOError:break
            if peer!=self.peer:continue
            try:obj=json.loads(raw)
            except (ValueError,UnicodeError):continue
            if isinstance(obj,dict) and obj.get('version')==1:result.append(obj)
        return result

    def close(self):self.socket.close()


class CommandGate:
    def __init__(self,session,timeout):
        self.session,self.timeout=session,float(timeout)
        self.sequence=-1
        self.received=-math.inf
        self.command=(0.0,0.0)

    def accept(self,message,now=None):
        now=time.monotonic() if now is None else now
        try:
            if message.get('kind')!='cmd' or message['session']!=self.session:return False
            seq=message['seq'];sent=float(message['sent'])
            command=(float(message['linear']),float(message['angular']))
            if type(seq) is not int or seq<=self.sequence:return False
            if not all(math.isfinite(v) for v in (*command,sent)):return False
            if not 0<=now-sent<=self.timeout:return False
        except (KeyError,ValueError,TypeError):return False
        self.sequence,self.received,self.command=seq,now,command
        return True

    def value(self,now=None):
        now=time.monotonic() if now is None else now
        return self.command if now-self.received<=self.timeout else (0.0,0.0)

    def stop(self):
        self.received=-math.inf
        self.command=(0.0,0.0)
