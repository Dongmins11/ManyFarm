import base64,json,os,selectors,subprocess
from pathlib import Path
import numpy as np

class Detector:
    def __init__(self,python,model,device='cpu',timeout=90):
        self.timeout=timeout
        env=os.environ.copy();env['YOLO_CONFIG_DIR']=str(Path(__file__).resolve().parents[3]/'outputs/harvest_rl/yolo_config')
        self.process=subprocess.Popen([str(python),'-u',str(Path(__file__).with_name('worker.py')),'--model',str(model),'--device',device],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=None,env=env)
        self.buffer=b''
        self.selector=selectors.DefaultSelector();self.selector.register(self.process.stdout,selectors.EVENT_READ)
        try:
            if not self.read().get('ready'):raise RuntimeError('Detector not ready')
        except Exception:self.close();raise
    def read(self):
        import time
        deadline=time.monotonic()+self.timeout
        while b'\n' not in self.buffer:
            remaining=deadline-time.monotonic()
            if remaining<=0 or not self.selector.select(remaining):raise TimeoutError('Detector response timeout')
            chunk=os.read(self.process.stdout.fileno(),65536)
            if not chunk:raise RuntimeError('Detector exited; inspect stderr')
            self.buffer+=chunk
        line,self.buffer=self.buffer.split(b'\n',1);data=json.loads(line)
        if 'error' in data:raise RuntimeError(data['error'])
        return data
    def predict(self,rgb):
        request=dict(shape=list(rgb.shape),rgb=base64.b64encode(np.ascontiguousarray(rgb).tobytes()).decode())
        self.process.stdin.write((json.dumps(request)+'\n').encode());self.process.stdin.flush()
        result=self.read()['detections'];h,w=rgb.shape[:2]
        for d in result:d['mask']=np.unpackbits(np.frombuffer(base64.b64decode(d['mask']),np.uint8),count=h*w).reshape(h,w).astype(bool)
        return result
    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait()
        for pipe in (self.process.stdin,self.process.stdout):
            if pipe:pipe.close()
        self.selector.close()
