"""Read-only overview and actual policy-camera recording for a native mission.

Uses existing sensor render passes; never steps physics or supplies policy data.
Playback follows simulation time (20 frames/s), not slow rendering wall time.
"""
import json
from pathlib import Path

import cv2
import numpy as np


class MissionVideo:
    def __init__(self, env, output, camera_kind):
        import omni.replicator.core as rep
        from pxr import UsdGeom, Gf
        self.output = Path(output)
        self.camera_kind = camera_kind
        self.frames = 0
        self.last_frame = None
        camera = UsdGeom.Camera.Define(env.sim.stage, '/World/MissionRecordingCamera')
        camera.CreateFocalLengthAttr(28.)
        camera.CreateClippingRangeAttr(Gf.Vec2f(.01, 100.))
        target = np.array([.40, -.08, .82])
        eye = target + np.array([.05, -1.1, .75])
        camera.AddTransformOp().Set(Gf.Matrix4d().SetLookAt(
            Gf.Vec3d(*eye), Gf.Vec3d(*target), Gf.Vec3d(0, 0, 1)).GetInverse())
        self.product = rep.create.render_product(str(camera.GetPath()), (960, 720))
        self.rgb = rep.AnnotatorRegistry.get_annotator('rgb')
        self.rgb.attach(self.product)
        self.writer = cv2.VideoWriter(str(self.output/'mission_raw.mp4'),
            cv2.VideoWriter_fourcc(*'mp4v'), 20., (1280, 800))
        if not self.writer.isOpened():
            raise RuntimeError('Could not open mission video encoder')

    @staticmethod
    def _text(canvas, text, xy, scale=.55, colour=(225, 230, 240)):
        cv2.putText(canvas, text, xy, cv2.FONT_HERSHEY_SIMPLEX, scale,
                    colour, 1, cv2.LINE_AA)

    def append(self, mission, capture, now):
        rgb = np.asarray(self.rgb.get_data())
        if rgb.shape[:2] != (720, 960):
            raise RuntimeError('Missing native overview video frame')
        canvas = np.full((800, 1280, 3), (19, 23, 30), dtype=np.uint8)
        canvas[80:, :960] = cv2.cvtColor(rgb[:, :, :3], cv2.COLOR_RGB2BGR)
        count = len(mission.harvested)
        complete = mission.state == 'DONE'
        colour = (80, 230, 110) if complete else (220, 200, 90)
        self._text(canvas, self.camera_kind.upper()+' STUDENT + CAMERA ASSIST | LOWEST FIRST', (18, 27), .7)
        self._text(canvas, f'Sim {now:6.2f}s | 1x simulation time | In box: {count}/{len(mission.targets)}', (18, 56), .6)
        self._text(canvas, 'MISSION COMPLETE' if complete else mission.state, (820, 27), .65, colour)
        self._text(canvas, mission.target.target_id+' / '+mission.target.label, (820, 56), .55)
        panels = [('right', 'rgb', 'Wrist RGB'), ('right', 'ir_right', 'Wrist right IR (sim)'), ('rear', 'rgb', 'Rear RGB')]
        for index, (name, stream, title) in enumerate(panels):
            top = 80 + index*225
            self._text(canvas, title, (976, top+23), .55)
            data = capture.get(name, {}).get(stream)
            if data is None and stream == 'ir_right':
                data = capture.get(name, {}).get('ir', {}).get('ir_right')
            if data is None:
                self._text(canvas, 'Stream not present', (976, top+90), .5)
                continue
            data = np.asarray(data)
            if data.ndim == 2:
                if data.dtype != np.uint8:
                    data = np.clip(data*255 if np.max(data)<=1 else data, 0, 255).astype(np.uint8)
                data = cv2.cvtColor(data, cv2.COLOR_GRAY2BGR)
            else:
                data = cv2.cvtColor(data[:, :, :3], cv2.COLOR_RGB2BGR)
            scale = min(304/data.shape[1], 184/data.shape[0])
            tile = cv2.resize(data, (round(data.shape[1]*scale), round(data.shape[0]*scale)))
            y, x = top+32, 968+(304-tile.shape[1])//2
            canvas[y:y+tile.shape[0], x:x+tile.shape[1]] = tile
        self._text(canvas, 'Actual simulation capture', (976, 778), .45)
        self.writer.write(canvas)
        if self.frames == 0:
            cv2.imwrite(str(self.output/'video_first_frame.jpg'), canvas)
        self.frames += 1
        self.last_frame = canvas

    def close(self, report=None):
        hold = 40 if report and report.get('mission_complete') else 0
        if self.last_frame is not None:
            cv2.imwrite(str(self.output/'video_last_frame.jpg'), self.last_frame)
            for _ in range(hold): self.writer.write(self.last_frame)
        self.writer.release()
        self.rgb.detach(self.product)
        self.product.destroy()
        (self.output/'video.json').write_text(json.dumps(dict(
            camera=self.camera_kind, fps=20, simulation_frames=self.frames,
            final_hold_frames=hold, playback='1x simulation time; not wall-clock performance',
            policy_cameras='actual capture, display resize only',
            mission_complete=bool(report and report.get('mission_complete')),
            harvest_successes=(report or {}).get('harvest_successes'),
            video='mission_raw.mp4'), indent=2)+'\n')
