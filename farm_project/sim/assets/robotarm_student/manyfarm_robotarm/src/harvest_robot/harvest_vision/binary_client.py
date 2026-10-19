"""Opt-in detector transport; same RGB/model/segmentation settings as client.py."""
import os
from pathlib import Path
import subprocess
import numpy as np
from .binary_protocol import BinaryChannel


class BinaryDetector:
    def __init__(self,python,model,device='cpu',timeout=90.):
        env=os.environ.copy()
        env['YOLO_CONFIG_DIR']=str(Path(__file__).resolve().parents[3]/'outputs/harvest_rl/yolo_config')
        worker=Path(__file__).with_name('binary_worker.py')
        self.process=subprocess.Popen([str(python),'-u',str(worker),'--model',str(model),'--device',device],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=None,env=env)
        self.sequence=0;self.last_timing={};self.closed=False
        self.channel=BinaryChannel(self.process.stdout.fileno(),self.process.stdin.fileno(),timeout)
        try:
            ready,payload=self.channel.receive()
            if not ready.get('ready') or payload:raise RuntimeError('Detector not ready')
        except BaseException:self.close();raise

    def predict(self,rgb):
        if self.closed:raise RuntimeError('Detector is closed')
        rgb=np.asarray(rgb)
        if rgb.dtype!=np.uint8 or rgb.ndim!=3 or rgb.shape[2]!=3:raise ValueError('Expected HWC RGB uint8')
        rgb=np.ascontiguousarray(rgb);h,w=rgb.shape[:2];sequence=self.sequence;self.sequence+=1
        try:
            self.channel.send(dict(sequence=sequence,shape=list(rgb.shape)),rgb.data)
            result,payload=self.channel.receive()
            if 'error' in result:raise RuntimeError(result['error'])
            if result.get('sequence')!=sequence:raise ValueError('Detector sequence mismatch')
            detections=result['detections'];size=(h*w+7)//8
            if len(payload)!=size*len(detections):raise ValueError('Detector mask payload mismatch')
            for i,d in enumerate(detections):
                packed=np.frombuffer(payload,np.uint8,count=size,offset=i*size)
                d['mask']=np.unpackbits(packed,count=h*w).reshape(h,w).astype(bool)
            self.last_timing=result.get('timing',{})
            return detections
        except BaseException:self.close();raise

    def close(self):
        if self.closed:return
        self.closed=True
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        for pipe in (self.process.stdin,self.process.stdout):
            if pipe:pipe.close()
