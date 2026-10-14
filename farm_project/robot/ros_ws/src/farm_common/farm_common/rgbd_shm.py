"""Linux /dev/shm의 mmap + flock. Python 3.11/3.12 별도 프로세스 호환.

단일 writer / 다중 reader. 배열과 메타데이터를 같은 잠금에서 복사합니다.
추론 중 잠금을 유지하지 않고 Reader.read() 반환 배열을 사용하세요.
"""
import fcntl
import json
import mmap
import os
from pathlib import Path
import re
import struct
import time
import numpy as np

HEADER = struct.Struct('<8sIIIIQQ')
MAGIC = b'FARMRGBD'
META_BYTES = 8192
OFFSET = HEADER.size + META_BYTES


def location(name):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',name):
        raise ValueError('shared memory 이름이 잘못되었습니다.')
    return Path('/dev/shm') / (name+'.bin')


class RgbdWriter:
    def __init__(self, name, width, height):
        if not (1 <= width <= 4096 and 1 <= height <= 4096):
            raise ValueError('지원하지 않는 영상 크기')
        self.path=location(name)
        self.width,self.height=width,height
        self.rgb_bytes=width*height*3
        self.size=OFFSET+width*height*7
        self.sequence=0
        self._depth_unavailable=False
        self.owner=os.open(str(self.path)+'.owner',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        try:
            fcntl.flock(self.owner,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(self.owner)
            raise RuntimeError(f'카메라 writer가 이미 실행 중입니다: {name}')
        self.fd=os.open(self.path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        fcntl.flock(self.fd,fcntl.LOCK_EX)
        try:
            os.ftruncate(self.fd,self.size)
            self.mm=mmap.mmap(self.fd,self.size)
            self.mm[:HEADER.size]=HEADER.pack(MAGIC,1,width,height,0,0,0)
        finally:
            fcntl.flock(self.fd,fcntl.LOCK_UN)

    def write(self,rgb,depth,metadata):
        rgb=np.ascontiguousarray(rgb,dtype=np.uint8)
        # RGB 전용 센서는 기존 버퍼 규격의 NaN 영역을 재사용한다.
        if depth is None:
            if metadata.get('aligned_depth') is not False or metadata.get('depth_definition')!='unavailable':
                raise ValueError('깊이 생략은 unavailable RGB 센서만 허용합니다.')
        else:
            depth=np.ascontiguousarray(depth,dtype='<f4')
        if rgb.shape!=(self.height,self.width,3) or (depth is not None and depth.shape!=(self.height,self.width)):
            raise ValueError('RGB/Depth 크기 불일치')
        meta=dict(metadata,version=1,width=self.width,height=self.height,
                  rgb_encoding='rgb8',depth_encoding='32FC1',depth_unit='m',
                  rgb_stride=self.width*3,depth_stride=self.width*4,
                  written_monotonic=time.monotonic())
        encoded=json.dumps(meta,allow_nan=False,separators=(',',':')).encode()
        if len(encoded)>META_BYTES:
            raise ValueError('영상 metadata 크기 초과')
        try:
            fcntl.flock(self.fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            return False  # reader가 복사 중이면 이번 frame을 건너뜁니다.
        try:
            self.mm[HEADER.size:HEADER.size+len(encoded)]=encoded
            self.mm[OFFSET:OFFSET+self.rgb_bytes]=rgb.tobytes()
            if depth is not None:
                self.mm[OFFSET+self.rgb_bytes:]=depth.tobytes()
            elif not self._depth_unavailable:
                self.mm[OFFSET+self.rgb_bytes:]=np.full((self.height,self.width),np.nan,dtype='<f4').tobytes()
            self._depth_unavailable=depth is None
            self.sequence+=1
            self.mm[:HEADER.size]=HEADER.pack(MAGIC,1,self.width,self.height,
                                             len(encoded),self.sequence,int(meta['stamp_ns']))
        finally:
            fcntl.flock(self.fd,fcntl.LOCK_UN)
        return True

    def close(self):
        if getattr(self,'mm',None) is None:return
        fcntl.flock(self.fd,fcntl.LOCK_EX)
        try:
            self.mm[:HEADER.size]=HEADER.pack(MAGIC,1,self.width,self.height,0,0,0)
            self.mm.close();self.mm=None
        finally:
            fcntl.flock(self.fd,fcntl.LOCK_UN)
            os.close(self.fd);os.close(self.owner)


class RgbdReader:
    def __init__(self,name):
        self.path=location(name)
        self.last=None

    def read(self,max_age=2.0,*,include_depth=True):
        # 매번 열어 writer 재시작/크기 변경 시에도 이전 mmap을 재사용하지 않습니다.
        try:fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW)
        except FileNotFoundError:return None
        try:
            try:fcntl.flock(fd,fcntl.LOCK_SH|fcntl.LOCK_NB)
            except BlockingIOError:return None
            if os.fstat(fd).st_size<OFFSET:return None
            with mmap.mmap(fd,0,access=mmap.ACCESS_READ) as mm:
                magic,version,w,h,mlen,seq,stamp=HEADER.unpack(mm[:HEADER.size])
                if magic!=MAGIC or version!=1:raise ValueError('RGB-D 공유메모리 규격 불일치')
                if not seq or not mlen:return None
                if not (0<mlen<=META_BYTES and 0<w<=4096 and 0<h<=4096):
                    raise ValueError('RGB-D header 손상')
                if len(mm)!=OFFSET+w*h*7:raise ValueError('RGB-D 버퍼 크기 불일치')
                meta=json.loads(mm[HEADER.size:HEADER.size+mlen])
                key=(meta['session'],seq)
                if key==self.last or time.monotonic()-meta['written_monotonic']>max_age:return None
                rgb=np.frombuffer(mm,dtype=np.uint8,count=w*h*3,offset=OFFSET).reshape(h,w,3).copy()
                depth=(np.frombuffer(mm,dtype='<f4',count=w*h,offset=OFFSET+w*h*3).reshape(h,w).copy()
                       if include_depth else None)
                self.last=key
                return dict(rgb=rgb,depth=depth,metadata=dict(meta,sequence=seq,stamp_ns=stamp))
        finally:
            os.close(fd)
