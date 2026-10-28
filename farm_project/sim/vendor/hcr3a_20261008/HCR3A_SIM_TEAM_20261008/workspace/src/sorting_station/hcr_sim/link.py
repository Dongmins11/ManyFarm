"""Wall-clock Modbus heartbeat, independent of GPU rendering and physics speed."""

import sys
import threading
import time
from .model import ROOT


class SimHCRLink:
    def __init__(self, port=1502):
        sys.path.insert(0, str(ROOT / "src/sorting_station/hcr_sorting"))
        from hcr_sorting.mock_hcr import Client

        self.client = Client("127.0.0.1", port)
        self.latest = None
        self.error = ""
        self.output = (0, 0, 0, 0)
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        heartbeat = None
        seen = time.monotonic()
        try:
            while not self.stop.is_set():
                packet = self.client.read()
                if packet[4] != heartbeat:
                    heartbeat = packet[4]
                    seen = time.monotonic()
                if time.monotonic() - seen > 3:
                    raise RuntimeError("PC_HEARTBEAT_TIMEOUT")
                self.latest = packet
                self.client.status(*self.output)
                self.stop.wait(0.1)
        except Exception as exc:
            if not self.stop.is_set():
                self.error = str(exc)

    def status(self, state, ack, done, error=0):
        # A single tuple swap preserves one coherent FC16 status packet.
        self.output = (state, ack, done, error)

    def close(self):
        self.stop.set()
        self.client.sock.close()
        self.thread.join(timeout=3)
