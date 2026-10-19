"""Read-only camera/input display. No policy, actuator or physics callbacks."""
import time
import numpy as np
from PIL import Image


def depth_rgb(depth,near=.10,far=1.50):
    depth=np.asarray(depth)
    valid=np.isfinite(depth)&(depth>0)
    value=np.clip((np.where(valid,depth,near)-near)/(far-near),0,1)
    rgb=np.stack([value,1-np.abs(2*value-1),1-value],axis=-1)
    return np.where(valid[...,None],rgb*255,0).astype(np.uint8)


def display_rgba(array,size=(480,270)):
    """Letterbox a display copy; never resize or paint the control input."""
    array=np.asarray(array)
    if array.ndim==2:array=np.repeat(array[...,None],3,axis=-1)
    image=Image.fromarray(array.astype(np.uint8,copy=False)).convert('RGBA')
    image.thumbnail(size)
    canvas=Image.new('RGBA',size,(0,0,0,255))
    canvas.paste(image,((size[0]-image.width)//2,(size[1]-image.height)//2))
    return canvas.tobytes(),list(size)


def observed_stage(record):
    v=record.get('visual_servo',{})
    if v.get('observed_stopped_tray_opening'):return 'Release / box settlement'
    if v.get('observed_transfer_phase'):return 'Transfer: '+v['observed_transfer_phase']
    if v.get('bounded_camera_pull'):return 'Pull'
    if v.get('captured_proxy'):return 'Grip hold (encoder estimate)'
    if v.get('entry_ready'):return 'Close gripper'
    if v.get('pregrasp_reobservation_active'):return 'Stationary camera reobservation'
    if v.get('pregrasp_reobserved'):return 'Align / insert'
    return 'Clear-view acquisition / approach'


class LiveCameraView:
    def __init__(self):
        import omni.ui as ui
        self.updates=0;self.last_frames={};self.providers={};self.stamps={};self.buffers={}
        self.previous_update=None;self.wall_hz=None;self.sim_speed=None
        self.window=ui.Window('Student camera inputs',width=420,height=800)
        with self.window.frame:
            with ui.ScrollingFrame():
                with ui.VStack(spacing=4):
                    self.status=ui.Label('Starting camera Student + v20 assistance...',height=32,word_wrap=True)
                    self.progress=ui.Label('Live native inputs before model resizing | simulation time',height=40,word_wrap=True)
                    self.rgb_group=ui.CollapsableFrame('RGB / IR inputs',collapsed=False)
                    with self.rgb_group:
                        with ui.VStack(spacing=3):
                            for key,title in [('rear_rgb','Rear RGB'),('wrist_rgb','Wrist RGB'),('wrist_ir','Wrist RIGHT IR (sim geometry)')]:
                                self._tile(ui,key,title)
                    self.depth_group=ui.CollapsableFrame('Depth inputs (metres)',collapsed=True)
                    with self.depth_group:
                        with ui.VStack(spacing=3):
                            ui.Label('0.10..1.50 m: near blue / far red',height=22)
                            for key,title in [('rear_depth','Rear aligned depth'),('wrist_depth','Wrist aligned depth')]:
                                self._tile(ui,key,title)
                    ui.Label('Live camera Student + assistance. Camera panels show actual input frames. Ctrl+C stops the run.',height=32,word_wrap=True)
        self.docked_target=None

    def dock(self):
        """Dock after the new window has participated in its first UI render."""
        import omni.ui as ui
        from omni.kit.viewport.utility import get_active_viewport_window
        viewport=get_active_viewport_window()
        title=viewport.title if viewport is not None else 'Viewport'
        # Keep only this demonstration's two panes, including previously
        # inactive inspector tabs that would otherwise take over the dock.
        for other in ui.Workspace.get_windows():
            if other.title not in {title,'Student camera inputs'}:other.visible=False
        if viewport is not None:viewport.viewport_api.fill_frame=True
        own=ui.Workspace.get_window('Student camera inputs')
        target=ui.Workspace.get_window(title)
        if own is not None and target is not None:
            own.dock_in(target,ui.DockPosition.RIGHT,.30);self.docked_target=title

    def _tile(self,ui,key,title):
        with ui.VStack(height=205):
            self.stamps[key]=ui.Label(title,height=22)
            provider=ui.ByteImageProvider();self.providers[key]=provider
            ui.ImageWithProvider(provider,width=ui.Fraction(1),height=180,
                fill_policy=ui.IwpFillPolicy.IWP_PRESERVE_ASPECT_FIT)

    def update(self,capture,record,episode,color,planned,successes):
        self.updates+=1
        wall=time.monotonic();sim=float(record['sim_s'])
        if self.previous_update is not None:
            previous_wall,previous_sim=self.previous_update
            if wall>previous_wall and sim>previous_sim:
                self.wall_hz=1/(wall-previous_wall)
                self.sim_speed=(sim-previous_sim)/(wall-previous_wall)
        self.previous_update=(wall,sim)
        speed=(f' | actual {self.wall_hz:.1f} Hz | sim/wall {self.sim_speed:.2f}x'
            if self.wall_hz is not None else '')
        self.status.text=f'{"|/-"[self.updates%3]}  Attempt {episode+1}/{planned} ({color}) | {observed_stage(record)}'
        target=record.get('target',{});d=record.get('diagnostic',{})
        self.progress.text=(f'Completed successes: {successes} | sim {record["sim_s"]:.2f}s | '
            f'camera target: {"valid" if target.get("valid") else "not visible"} | '
            f'box settlement: {d.get("box_outcome_dwell_s",0):.2f}/0.60s'+speed)
        right=capture['right'];rear=capture['rear']
        pictures={'rear_rgb':(rear,rear['rgb']),'wrist_rgb':(right,right['rgb']),
            'wrist_ir':(right,right['ir']['ir_right']),
            'rear_depth':(rear,rear['aligned_depth_m']),
            'wrist_depth':(right,right['aligned_depth_m'])}
        titles={'rear_rgb':'Rear RGB','wrist_rgb':'Wrist RGB','wrist_ir':'Wrist RIGHT IR',
            'rear_depth':'Rear aligned depth','wrist_depth':'Wrist aligned depth'}
        for key,(frame,picture) in pictures.items():
            self.last_frames[key]=dict(frame_number=int(frame['frame_number']),stamp_s=float(frame['stamp_s']),
                native_shape=list(picture.shape))
            self.stamps[key].text=f'{titles[key]} | frame {frame["frame_number"]} | {frame["stamp_s"]:.3f}s'
            is_depth=key.endswith('_depth')
            if (self.depth_group if is_depth else self.rgb_group).collapsed:
                continue
            # Hidden panels need neither a colour map nor texture copies. The
            # native capture/controller still receives every original stream.
            if is_depth:picture=depth_rgb(picture)
            data,size=display_rgba(picture)
            # Installed omni.ui expects a contiguous buffer-protocol object,
            # and retaining it also covers asynchronous texture upload lifetime.
            self.buffers[key]=np.frombuffer(data,dtype=np.uint8).copy()
            self.providers[key].set_bytes_data(self.buffers[key].data,size)

    def result(self,color,status,successes,attempts):
        self.status.text=f'{color}: {status} | completed successes {successes}/{attempts}'

    def hold(self,sim,app,seconds):
        before=sim.current_time;end=time.monotonic()+seconds
        while app.is_running() and time.monotonic()<end:
            sim.render();time.sleep(1/30)
        if abs(sim.current_time-before)>1e-9:
            raise RuntimeError('Display hold must not advance physics time')

    def summary(self):
        return dict(mode='live_inference_gui',updates=self.updates,streams=self.last_frames,
            source='same capture dictionary passed into the camera controller',
            presentation_only=True,physics_or_actuator_callbacks=False,
            depth_color_range_m=[.10,1.50],display_letterbox_size=[480,270],
            hidden_panel_texture_processing=False,actual_control_hz=self.wall_hz,
            simulation_to_wall_speed=self.sim_speed,
            docked_target=self.docked_target)

    def close(self):
        self.window.destroy()
