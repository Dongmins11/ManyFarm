"""Bounded JSON metadata + raw byte messages over local nonblocking pipes."""
import json
import os
import select
import struct
import time

MAX_HEADER=1024*1024
MAX_PAYLOAD=64*1024*1024


class BinaryChannel:
    def __init__(self,reader,writer,timeout=90.):
        self.reader=reader;self.writer=writer;self.timeout=float(timeout)
        if self.timeout<=0:raise ValueError('Positive channel timeout required')
        os.set_blocking(reader,False);os.set_blocking(writer,False)

    def _wait(self,fd,writing,deadline):
        remaining=deadline-time.monotonic()
        if remaining<=0:raise TimeoutError('Detector pipe deadline exceeded')
        ready=select.select([] if writing else [fd],[fd] if writing else [],[],remaining)
        if not ready[0] and not ready[1]:raise TimeoutError('Detector pipe deadline exceeded')

    def _read(self,count,deadline):
        parts=[];left=count
        while left:
            self._wait(self.reader,False,deadline)
            try:part=os.read(self.reader,min(left,65536))
            except BlockingIOError:continue
            if not part:raise EOFError('Detector pipe closed')
            parts.append(part);left-=len(part)
        return b''.join(parts)

    def receive(self):
        deadline=time.monotonic()+self.timeout
        length=struct.unpack('!I',self._read(4,deadline))[0]
        if not 0<length<=MAX_HEADER:raise ValueError('Invalid detector header length')
        header=json.loads(self._read(length,deadline))
        if not isinstance(header,dict):raise ValueError('Detector header must be an object')
        count=header.pop('_payload_bytes',None)
        if type(count) is not int or not 0<=count<=MAX_PAYLOAD:raise ValueError('Invalid detector payload length')
        return header,self._read(count,deadline)

    def send(self,header,payload=b''):
        payload=memoryview(payload).cast('B')
        if len(payload)>MAX_PAYLOAD:raise ValueError('Detector payload too large')
        meta=json.dumps(dict(header,_payload_bytes=len(payload)),allow_nan=False).encode()
        if len(meta)>MAX_HEADER:raise ValueError('Detector header too large')
        deadline=time.monotonic()+self.timeout
        for value in [struct.pack('!I',len(meta)),meta,payload]:
            data=memoryview(value)
            while data:
                self._wait(self.writer,True,deadline)
                try:written=os.write(self.writer,data[:65536])
                except BlockingIOError:continue
                if written<=0:raise EOFError('Detector pipe closed')
                data=data[written:]
