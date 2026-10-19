"""Current URDF + right-wrist/rear D435 RGB/native depth viewer. No policy runs."""
import argparse
from pathlib import Path
import json
import time
from datetime import datetime
from isaaclab.app import AppLauncher

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--detector-model',type=Path,help='Optional YOLO segmentation checkpoint')
p.add_argument('--vision-python',type=Path,default=Path('.venvs/harvest_vision/bin/python'))
p.add_argument('--vision-device',default='cpu')
p.add_argument('--centre-offset-m',type=float,default=None,help='Optional provisional surface-to-centre ray offset, metres')
p.add_argument('--frames',type=int,default=0,help='0 keeps GUI open; headless requires positive frames')
p.add_argument('--output',type=Path)
p.add_argument('--camera-config',type=Path,default=Path(__file__).parent/'config/d435_nominal.json')
p.add_argument('--visual-scene',choices=('greenhouse_v1','legacy'),default='greenhouse_v1',help='Appearance only; fruit/robot/camera placement is unchanged')
p.add_argument('--save-scene-view',action='store_true',help='Preview only: export an additional static overview RGB; not a Student input')
p.add_argument('--fruit-front',type=float,default=.25,help='Metres beyond arm mounting plate front edge')
p.add_argument('--fruit-side',type=float,default=0.,help='Lateral offset from right arm mount, metres')
p.add_argument('--fruit-height',type=float,default=.15,help='Height relative to arm base, metres')
p.add_argument('--joint-positions',type=float,nargs=6,help='Right arm joint positions [rad], including gripper')
p.add_argument('--fruit-at-grasp',action='store_true',help='Static camera inspection: put the visual fruit at nominal jaw-centre FK, not a workspace/reachability test')
AppLauncher.add_app_launcher_args(p)
a=p.parse_args()
if a.frames<0 or (a.headless and a.frames==0):p.error('Headless requires --frames > 0')
if not .2<=a.fruit_front<=.3 or not -.175<=a.fruit_side<=.175 or not -.1<=a.fruit_height<=.35:
    p.error('Fruit range: front .20-.30, side +/-.175, height -.10 to .35 m')
a.enable_cameras=True
a.kit_args=(a.kit_args or '')+' --/plugins/carb.tasking.plugin/threadCount=1'
app=AppLauncher(a).app
failed=False
detector=None
try:
    import numpy as np
    import torch
    import yaml
    from PIL import Image, ImageDraw
    from scipy.spatial.transform import Rotation
    import isaaclab.sim as sim_utils
    from isaaclab.assets import Articulation,ArticulationCfg
    from isaaclab.actuators import ImplicitActuatorCfg
    from harvest_rl.current_robot import prepare_current_robot
    from harvest_rl.settings import ROOT,ASSETS,JOINTS
    from harvest_rl.d435_rig import DualD435Rig
    from harvest_rl.rgbd_geometry import depth_rgb,project
    from run import create_run_directory

    if a.detector_model:
        from harvest_vision.client import Detector
        from harvest_vision.geometry import Frame
        from harvest_vision.pipeline import process,save_packet
        detector=Detector(a.vision_python,a.detector_model,a.vision_device)
    config=json.loads(a.camera_config.read_text())
    out=create_run_directory(a.output or ROOT/'outputs/harvest_rl'/f'd435_preview_{datetime.now():%Y%m%d_%H%M%S}')
    usd,kin,asset=prepare_current_robot()
    sim=sim_utils.SimulationContext(sim_utils.SimulationCfg(dt=1/240,render_interval=8,device=a.device))
    sim.set_camera_view(eye=(1.35,-1.65,1.65) if a.visual_scene=='legacy' else (1.35,.80,1.65),target=(0.,-.25,.80))
    robot=Articulation(ArticulationCfg(prim_path='/World/Robot',
        spawn=sim_utils.UsdFileCfg(usd_path=str(usd)),
        actuators={'arm':ImplicitActuatorCfg(joint_names_expr=['arm_2_.*'],stiffness=25.,damping=1.5)}))
    ground=sim_utils.GroundPlaneCfg();ground.func('/World/Ground',ground)
    light=sim_utils.DomeLightCfg(intensity=1800.,color=(.85,.9,1.));light.func('/World/Light',light)
    rig=DualD435Rig(kin,config)
    scene_camera=None
    if a.save_scene_view:
        from isaaclab.sensors import Camera,CameraCfg
        scene_camera=Camera(CameraCfg(prim_path='/World/SceneReviewCamera',width=960,height=640,
            data_types=['rgb'],update_period=0.,spawn=sim_utils.PinholeCameraCfg(
                focal_length=24.,horizontal_aperture=36.,clipping_range=(.01,10.))))
    home=np.array([0.,-1.39,.77,.62,-1.522+np.pi/2,1.1]) if a.joint_positions is None else np.array(a.joint_positions)
    if not np.all((home>=kin.lower)&(home<=kin.upper)):raise ValueError('Pose outside URDF limits')
    assembly=yaml.safe_load((ROOT/'src/smartfarm_description/config/assembly.yaml').read_text())
    base=kin.fk(np.zeros(6),'arm_2/base_link')
    local=np.array([assembly['arm_mount_length']/2+a.fruit_front,a.fruit_side,a.fruit_height])
    fruit=base[:3,3]+base[:3,:3]@local
    if a.fruit_at_grasp:
        fruit=kin.grasp_fk(home)[:3,3]
    # Static visual target: this tool verifies sensor geometry, not detachment physics.
    meta=json.loads((ASSETS/'manifest.json').read_text())['Pepper_Red']
    size=np.diff(meta['bounds'],axis=0)[0]
    pepper=sim_utils.UsdFileCfg(usd_path=str(ASSETS/'Pepper_Red.usdc'),scale=(.07/max(size[:2]),.07/max(size[:2]),.075/size[2]))
    pepper.func('/World/TargetFruit',pepper,translation=tuple(fruit))
    from harvest_rl.visual_scene import describe,spawn,gray_ground
    visual_scene=describe(a.visual_scene)
    if a.visual_scene=='legacy':
        tree=sim_utils.UsdFileCfg(usd_path=str(ASSETS/'Tree_01.usdc'),scale=(.75,.75,1.35))
        for i in range(3):
            tree.func(f'/World/BackgroundTree_{i}',tree,translation=(float(base[0,3]+(i-1)*.40),float(fruit[1]-.38),.12))
    else:
        # Same crop-frame origin as RL: plate front edge projected onto ground,
        # rather than the arm base (65 mm behind that edge).
        world_from_crop=base.copy()
        world_from_crop[:3,3]+=base[:3,:3]@np.array([assembly['arm_mount_length']/2,0.,0.])
        world_from_crop[2,3]=0.
        visual_scene=spawn(sim.stage,'/World/GreenhouseVisual',world_from_crop)
        gray_ground(sim.stage)
    # Input metadata is independent of teacher's cached workspace.
    sim.reset()
    if scene_camera is not None:
        scene_camera.set_world_poses_from_view(torch.tensor([[1.35,.80,1.65]],device=sim.device),
            torch.tensor([[0.,-.50,.70]],device=sim.device))
    jids,_=robot.find_joints(['arm_2_'+j for j in JOINTS],preserve_order=True)
    if len(jids)!=6:raise RuntimeError(f'Unexpected controlled joints: {robot.joint_names}')
    wrist_id=robot.body_names.index('arm_2_gripper_link')
    q=robot.data.default_joint_pos.clone();q[:,jids]=torch.tensor(home,device=sim.device,dtype=q.dtype)
    robot.write_joint_state_to_sim(q,torch.zeros_like(q))
    robot.set_joint_position_target(q)
    robot.write_data_to_sim()
    sim.forward()
    robot.update(sim.get_physics_dt())
    for _ in range(12):sim.render()
    # Sensor initialization renders can advance the startup articulation once.
    # Reapply this static viewer's requested pose after that initialization.
    robot.write_joint_state_to_sim(q,torch.zeros_like(q))
    robot.set_joint_position_target(q)
    robot.write_data_to_sim()
    sim.forward()
    robot.update(sim.get_physics_dt())
    # Fabric/RTX needs render updates after world-camera pose changes. Otherwise
    # a one-frame export can still return the initial zero-joint camera pose.
    for _ in range(4):
        rig.follow_wrist(robot.data.body_link_pos_w[0,wrist_id],robot.data.body_link_quat_w[0,wrist_id])
        sim.render()
        rig.update(1/config['fps'])
    # Render-only inspection: hold the exact requested pose, no robot policy/physics rollout.
    providers={};windows=[]
    if not a.headless:
        import omni.ui as ui
        for name in ('right','rear'):
            window=ui.Window(f'D435 {name} - RGB | depth native | depth aligned',width=990,height=235)
            window.position_x=10;window.position_y=60 if name=='right' else 320
            windows.append(window)
            with window.frame:
                with ui.HStack():
                    for stream in (('rgb','ir_right','depth') if config.get('schema')=='d435_deployment_v2' and name=='right' else ('rgb','depth','aligned')):
                        with ui.VStack():
                            ui.Label(stream+' (depth: metres, invalid black)',height=22)
                            provider=ui.ByteImageProvider();providers[name,stream]=provider
                            ui.ImageWithProvider(provider,width=320,height=180)
    landmarks={'target_fruit':fruit,'box_place_right':kin.fk(home,'place_right')[:3,3],
               'right_tcp':kin.grasp_fk(home)[:3,3],
               'box_rim_center':kin.fk(home,'harvest_box')[:3,3]+np.array([0,0,assembly['box_height']])}

    def save_capture(frames):
        report=dict(asset=asset,camera_config=config,visual_scene=visual_scene,joint_positions_rad=home.tolist(),
                    actual_joint_positions_rad=robot.data.joint_pos[0,jids].cpu().tolist(),
                    fruit_center_world_m=fruit.tolist(),arm_base_world=base.tolist(),
                    fruit_at_grasp=a.fruit_at_grasp,
                    cameras={},note='Static pose sensor inspection. Projected points alone do not prove visibility. Ideal geometric depth, not physical stereo reconstruction.')
        panels=[]
        if scene_camera is not None:
            scene_camera.update(1/config['fps'])
            scene_rgb=scene_camera.data.output['rgb'][0,:,:,:3].cpu().numpy()
            Image.fromarray(scene_rgb).save(out/'scene_view.png')
        for name,data in frames.items():
            root=out/name;root.mkdir(exist_ok=True)
            Image.fromarray(data['rgb']).save(root/'rgb.png')
            if config.get('schema')=='d435_deployment_v2' and name=='right':
                Image.fromarray(data['ir']['ir_right']).save(root/'ir_right_geometry.png')
            if 'vision_records' in data:
                Image.fromarray(data['vision_overlay']).save(root/'overlay.png')
                (root/'detections.json').write_text(json.dumps(data['vision_records'],indent=2))
                save_packet(root,data['vision_frame'])
            np.save(root/'raw_depth_m.npy',data['raw_depth_m'])
            for field in ('depth_m','aligned_depth_m'):
                np.save(root/(field+'.npy'),data[field])
                Image.fromarray(depth_rgb(data[field],config['depth_min_m'],config['depth_max_m'])).save(root/(field+'.png'))
                Image.fromarray((data[field]>0).astype(np.uint8)*255).save(root/(field+'_valid.png'))
            cal={key:{s:v.tolist() for s,v in data[key].items()} for key in ('world_from_optical','intrinsics')}
            cal['color_from_depth']=data['color_from_depth'].tolist()
            if config.get('schema')=='d435_deployment_v2':
                cal.update(renderer_checks=data['renderer_checks'],stamp_s=data['acquisition_time_s'],
                    pose_stamp_s=data['acquisition_time_s'],frame_number=data['acquisition_sequence'],
                    mount_calibration_verified=False)
            cal['landmarks']={}
            for key,point in landmarks.items():
                values={}
                for stream in ('rgb','depth'):
                    shape=data['rgb'].shape[:2] if stream=='rgb' else data['depth_m'].shape
                    uv,z,inside=project([point],data['world_from_optical'][stream],data['intrinsics'][stream],shape)
                    values[stream]=dict(pixel=uv[0].tolist(),optical_z_m=float(z[0]),in_frustum=bool(inside[0]))
                    if inside[0]:
                        u,v=np.rint(uv[0]).astype(int);h,w=shape;u=min(w-1,u);v=min(h-1,v)
                        depth=data['aligned_depth_m'] if stream=='rgb' else data['depth_m']
                        values[stream]['measured_surface_z_m']=float(depth[v,u])
                cal['landmarks'][key]=values
            cal['raw_below_min_fraction']=float((np.isfinite(data['raw_depth_m']) & (data['raw_depth_m']<config['depth_min_m'])).mean())
            cal['native_valid_fraction']=float(data['depth_valid'].mean())
            cal['aligned_valid_fraction']=float((data['aligned_depth_m']>0).mean())
            # Optical transform check against current URDF FK, not an assumed old asset pose.
            prefix='arm_2/wrist_camera' if name=='right' else 'top_camera'
            for stream,frame in (('rgb','color'),('depth','depth')):
                if config.get('schema')=='d435_deployment_v2':
                    from harvest_sensors.deployment import expected_poses
                    expected=expected_poses(kin,robot.data.joint_pos[0,jids].cpu().numpy(),config)[name][stream]
                else:
                    expected=kin.fk(robot.data.joint_pos[0,jids].cpu().numpy(),f'{prefix}_{frame}_optical_frame')
                error=float(np.max(np.abs(expected-data['world_from_optical'][stream])))
                cal[stream+'_urdf_transform_max_error']=error
                if error>2e-4:
                    (out/'pose_error.json').write_text(json.dumps(dict(name=name,stream=stream,expected=expected.tolist(),actual=data['world_from_optical'][stream].tolist(),q=robot.data.joint_pos[:,jids].cpu().tolist(),home=home.tolist(),joint_names=robot.joint_names,body_names=robot.body_names,body_pos=robot.data.body_link_pos_w.cpu().tolist(),body_quat=robot.data.body_link_quat_w.cpu().tolist()),indent=2))
                    raise RuntimeError(f'{name}/{stream} camera pose disagrees with URDF: {error}')
            (root/'calibration.json').write_text(json.dumps(cal,indent=2))
            report['cameras'][name]=cal
            row=Image.new('RGB',(960,290),(24,24,24));draw=ImageDraw.Draw(row)
            panels_data=(('RGB',data['rgb']),('native depth',depth_rgb(data['depth_m'],config['depth_min_m'],config['depth_max_m'])),('depth aligned to RGB',depth_rgb(data['aligned_depth_m'],config['depth_min_m'],config['depth_max_m'])))
            if config.get('schema')=='d435_deployment_v2' and name=='right':
                panels_data=(('wrist RGB policy',data['rgb']),('right IR geometry policy',data['ir']['ir_right']),('wrist depth diagnostic only',depth_rgb(data['depth_m'],config['depth_min_m'],config['depth_max_m'])))
            for i,(title,img) in enumerate(panels_data):
                view=Image.fromarray(img);view.thumbnail((320,240));row.paste(view,(i*320,28));draw.text((i*320+8,5),name+' / '+title,fill='white')
            draw.text((8,270),f"Depth: red {config['depth_min_m']}m -> green -> blue {config['depth_max_m']}m; black invalid",fill='white')
            panels.append(row)
        overview=Image.new('RGB',(960,580));overview.paste(panels[0],(0,0));overview.paste(panels[1],(0,290));overview.save(out/'overview.png')
        (out/'report.json').write_text(json.dumps(report,indent=2))
        (out/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Dual D435 preview</title><style>body{background:#181818;color:white;font-family:sans-serif}img{max-width:100%}</style><h1>Current URDF — right wrist / rear D435</h1><p>RGB | native optical-Z depth | reprojected depth. Black = invalid. Metres; nominal pinhole calibration.</p><img src="overview.png"><p><a href="report.json">Calibration, transforms and projected landmarks</a></p>')
        print('D435_CAPTURE',out,flush=True)
        print('TARGET_PROJECTION',json.dumps({name:cal['landmarks']['target_fruit'] for name,cal in report['cameras'].items()}),flush=True)

    count=0
    while app.is_running() and (a.frames==0 or count<a.frames):
        rig.follow_wrist(robot.data.body_link_pos_w[0,wrist_id],robot.data.body_link_quat_w[0,wrist_id])
        sim.render();rig.update(1/config['fps']);frames=rig.capture()
        if detector is not None:
            # Static viewer: geometry is frozen, timestamp belongs to this capture.
            stamp=time.monotonic()
            for name,data in frames.items():
                frame=Frame(data['rgb'],data['aligned_depth_m'],data['intrinsics']['rgb'],
                    np.linalg.inv(base)@data['world_from_optical']['rgb'],stamp,stamp,name,
                    clock_id='host_monotonic',calibration_verified=False)
                if config.get('schema')=='d435_deployment_v2':
                    if name=='right':continue
                    from harvest_sensors.native_vision import process_native
                    records,overlay=process_native(frame,data,detector,stamp,a.centre_offset_m,
                        arm_roi=([assembly['arm_mount_length']/2+.20,-.175,-.10],[assembly['arm_mount_length']/2+.30,.175,.35]))
                else:
                    records,overlay=process(frame,detector,stamp,a.centre_offset_m,
                        arm_roi=([assembly['arm_mount_length']/2+.20,-.175,-.10],[assembly['arm_mount_length']/2+.30,.175,.35]))
                data.update(vision_records=records,vision_overlay=overlay,vision_frame=frame)
            if count==3:print('VISION_RESULT',json.dumps({k:v.get('vision_records',[]) for k,v in frames.items()}),flush=True)
        if count==3 or (a.frames>0 and count==a.frames-1):save_capture(frames)
        for name,data in frames.items():
            display=(('rgb',data.get('vision_overlay',data['rgb'])),('depth',depth_rgb(data['depth_m'],config['depth_min_m'],config['depth_max_m'])),('aligned',depth_rgb(data['aligned_depth_m'],config['depth_min_m'],config['depth_max_m'])))
            if 'ir_right' in data.get('ir',{}):display+= (('ir_right',np.repeat(data['ir']['ir_right'][...,None],3,axis=2)),)
            for stream,img in display:
                if (name,stream) in providers:
                    h,w=img.shape[:2];rgba=np.dstack((img,np.full((h,w),255,dtype=np.uint8)))
                    providers[name,stream].set_bytes_data(rgba.flatten().data,[w,h])
        count+=1
        if not a.headless:time.sleep(1/config['fps'])
except Exception:
    import traceback;traceback.print_exc();failed=True
finally:
    if detector is not None:detector.close()
    from harvest_rl.lifecycle import close_simulator
    if failed:
        close_simulator(app,failed=True)
    else:
        # Images/arrays are synchronously saved above. Camera render products
        # keep Replicator active; even orchestrator.stop() can hang on this
        # installed Sim build. This standalone viewer has no async writers.
        import sys
        sys.stdout.flush();sys.stderr.flush()
        app.close(wait_for_replicator=False,skip_cleanup=True)
