"""Manual ROIs on actual simulated RGB, using the real HCR HSV classifier."""

import importlib.util
import json
import time
import uuid
from collections import deque
from pathlib import Path
import numpy as np
from .model import ROOT, OUT, NAMES

spec = importlib.util.spec_from_file_location(
    "hcr_real_vision", ROOT / "src/sorting_station/hcr/zone_preview.py"
)
real = importlib.util.module_from_spec(spec)
spec.loader.exec_module(real)


class Vision:
    def __init__(self, cfg, gui=True):
        import cv2

        self.cv = cv2
        self.cfg = cfg
        self.gui = gui
        self.window = None
        self.pending_keys = deque()
        self.file = OUT / "zones.json"
        self.rois = {}
        self.edit = None
        self.start = None
        self.states = {}
        self.trackers = {n: real.Stable(0.3) for n in NAMES}
        self.session = str(uuid.uuid4())
        self.counter = 0
        self.guides = {}
        self.lane_map = {n: n for n in NAMES}
        self.roi_error = ""
        self.notice = ""
        self.size = [cfg["camera"]["width"], cfg["camera"]["height"]]
        self.source = "hcr_sim_" + str(cfg["camera"])
        if self.file.exists():
            s = json.loads(self.file.read_text())
            if s.get("size") == self.size and s.get("source") == self.source:
                real.validate_rois(s["rois"], *self.size)
                self.rois = s["rois"]
        if gui:
            from .cv_window import CameraWindow

            self.window = CameraWindow(cv2, OUT)

    def mouse(self, event, x, y, flags, param):
        if self.edit is None:
            return
        w, h = self.size
        x = int(np.clip(x, 0, w))
        y = int(np.clip(y, 0, h))
        if event == self.cv.EVENT_LBUTTONDOWN:
            self.start = (x, y)
        if event == self.cv.EVENT_LBUTTONUP and self.start:
            a, b = self.start
            r = [min(a, x), min(b, y), abs(a - x), abs(b - y)]
            candidate = dict(self.rois)
            candidate[self.edit] = r
            try:
                real.validate_rois(candidate, w, h)
                self.rois = candidate
                self.edit = None
                self.notice = ""
                self.trackers = {n: real.Stable(0.3) for n in NAMES}
            except ValueError as exc:
                self.notice = str(exc)
                print(exc, flush=True)
            self.start = None

    def map_lanes(self):
        """Map user's labels to physical lanes by calibrated image geometry."""
        if not self.guides or set(self.rois) != set(NAMES):
            return True
        mapping = {}
        for n, (x,y,w,h) in self.rois.items():
            lane = min(self.guides, key=lambda k: abs(x+w/2-self.guides[k][0]))
            gx,gy = self.guides[lane]
            if abs(x+w/2-gx) > 34 or abs(y+h/2-gy) > 28:
                self.roi_error = f"ROI {n}: draw at bottom pickup guide"
                return False
            mapping[n] = lane
        if len(set(mapping.values())) != 4:
            self.roi_error = "ROI: select one different lane for each A/B/C/D"
            return False
        self.lane_map = mapping
        self.roi_error = ""
        return True

    def update(self, rgb, simtime, phase, counts, job=None, error="", supply="PRELOADED"):
        bgr = np.ascontiguousarray(rgb[:, :, :3][:, :, ::-1])
        self.counter += 1
        observations = {}
        for n, (x, y, w, h) in self.rois.items():
            raw, r, yel = real.classify(bgr[y : y + h, x : x + w], 0.08, 90, 60)
            observations[n] = (self.trackers[n].update(raw, simtime), r, yel)
        self.states = {n: o[0] for n, o in observations.items()}
        ready = set(self.rois) == set(NAMES) and self.edit is None and self.map_lanes()
        zone, color = real.select(self.states) if ready else (0, 0)
        supply_ready = supply in ("PRELOADED", "READY")
        frame = self.cv.copyMakeBorder(
            bgr, 0, 191, 0, 0, self.cv.BORDER_CONSTANT, value=(18, 18, 18)
        )
        palette = {
            "RED": (50, 50, 240),
            "YELLOW": (0, 230, 240),
            "NO_COLOR": (130, 130, 130),
            "WAIT": (220, 150, 80),
            "MIXED": (210, 80, 210),
        }
        for gx,gy in self.guides.values():
            self.cv.rectangle(frame,(int(gx-20),int(gy-7)),(int(gx+20),int(gy+7)),(180,180,180),1)
        for n, (x, y, w, h) in self.rois.items():
            state = self.states[n]
            ink = palette[state]
            self.cv.rectangle(
                frame,
                (x, y),
                (x + w, y + h),
                ink,
                3 if zone == NAMES.index(n) + 1 else 1,
            )
            label = n + ":" + state[:1]
            self.cv.putText(frame, label, (x, max(15, y - 6)), 0, 0.5, (0, 0, 0), 3)
            self.cv.putText(frame, label, (x, max(15, y - 6)), 0, 0.5, ink, 1)
        lines = [
            f"SIM {phase} | RED {counts[0]} YELLOW {counts[1]}",
            "   ".join(n + ":" + self.states.get(n, "UNSET") for n in NAMES),
            f'Next camera candidate: {NAMES[zone-1] if zone else "-"} / {"RED" if color==1 else "YELLOW" if color==2 else "-"}',
            (
                f"Executing job {job[0]}: {job[1]} {job[2]}"
                if job
                else "No motion in progress"
            ),
            "a/b/c/d: draw ROI | s: save | g: start | x/Shift+C: cancel | q: quit",
            f'Editing: {self.edit or "-"} | 4 ROIs required | frame {self.counter}',
            f'Transport: {supply} | t: unload only | r: recover ROI fault',
            (error or self.roi_error or self.notice)[:93],
        ]
        for i, line in enumerate(lines):
            self.cv.putText(
                frame,
                line,
                (10, self.size[1] + 20 + i * 23),
                0,
                0.45,
                (210, 230, 210),
                1,
            )
        real.atomic_json(
            OUT / "state.json",
            dict(
                timestamp=time.time(),
                monotonic=time.monotonic(),
                camera_session=self.session,
                ready=ready,
                zone_states=self.states if supply_ready else dict.fromkeys(NAMES,"WAIT"),
                zone=zone if supply_ready else 0,
                color=color if supply_ready else 0,
                counter=self.counter,
                valid=bool(zone) and supply_ready,
                simulation=True,
                lane_map=self.lane_map,
                supply_phase=supply,
            ),
        )
        if self.gui:
            self.window.show(frame)
        self.last_frame = frame
        self.last_rgb = rgb
        return ready, zone, color

    def key(self):
        if self.window:
            for event in self.window.poll():
                kind = event.get("kind")
                if kind == "mouse":
                    self.mouse(event["event"], event["x"], event["y"], event["flags"], None)
                elif kind == "key":
                    key = ord("C") if event["key"] == ord("x") else event["key"]
                    self.handle_key(key)
                    if key in (27, ord("q"), ord("g"), ord("r"), ord("t"), ord("C")):
                        self.pending_keys.append(key)
                elif kind == "closed":
                    self.pending_keys.append(ord("q"))
        return self.pending_keys.popleft() if self.pending_keys else 255

    def handle_key(self, key):
        if key in map(ord, "abcdABCD") and key != ord("C"):
            self.edit = chr(key).upper()
            self.start = None
        elif key == ord("s"):
            real.atomic_json(
                self.file, dict(size=self.size, source=self.source, rois=self.rois)
            )
            print("Saved simulation ROIs", flush=True)

    def close(self):
        real.atomic_json(OUT / "state.json", dict(ready=False, simulation=True))
        if self.gui:
            self.window.close()
