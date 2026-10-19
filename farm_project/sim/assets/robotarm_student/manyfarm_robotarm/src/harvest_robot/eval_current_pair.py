"""Current URDF + separated red/yellow fruits; evaluate one assigned harvest, no learning."""
import argparse
from pathlib import Path
from datetime import datetime
import json
import hashlib
import numpy as np
from harvest_rl.settings import ROOT,CACHE
from harvest_rl.kinematics import ArmKinematics
from harvest_rl.current_pair_geometry import current_to_policy_frame,separated_pairs
from run import load_settings,create_run_directory
from isaaclab.app import AppLauncher

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--capture-settle',action='store_true',help='Teacher evaluation: hold arm targets during qualified grasp/retention confirmation')
p.add_argument('--capture-gripper-target-hold',action='store_true',help='Teacher comparison: preserve established gripper target during qualified post-break retention confirmation')
p.add_argument('--transport-gripper-target-hold',action='store_true',help='Teacher comparison: carry the preserved gripper target through qualified transport, never through release')
p.add_argument('--transport-gripper-preload-step',type=float,default=0.,help='Teacher comparison: one extra closing target step at transport handoff, 0..0.010 rad')
p.add_argument('--transport-bounded-preload',action='store_true',help='Teacher comparison: rate/budget-limited preload maintenance; freeze adjustment on contact loss')
p.add_argument('--transport-preload-max-close',type=float,default=.020,help='Total closing budget from transport handoff target, rad, including initial preload')
p.add_argument('--transport-preload-rate',type=float,default=.020,help='Additional closing target rate limit, rad/s')
p.add_argument('--transport-preload-error',type=float,default=.010,help='Desired jaw position error, rad; not a measured force setpoint')
p.add_argument('--transport-linear-pose-stop',action='store_true',help='Evaluation-only bounded pose-speed transport stop')
p.add_argument('--eval-fruit-mass',type=float,help='Teacher-only mass transfer evaluation in kg; no training')
p.add_argument('--eval-fruit-collision',choices=('legacy','body_hull_v1'),help='Explicit Teacher contact-model comparison, no training')
p.add_argument('--eval-gripper-gains',choices=('baseline','reduced'),help='Explicit Teacher drive comparison: baseline 8/.3 or reduced 2/.05; effort cap unchanged')
p.add_argument('--eval-contact-model',choices=('rigid','compliant'),help='Explicit provisional grip compliance comparison: 15000N/m, 20Ns/m; no training')
p.add_argument('--eval-physics-hz',type=int,choices=(240,480),help='Explicit Teacher physics transfer; preserves 20Hz policy period')
p.add_argument('--eval-release-measured-open',action='store_true',help='Teacher comparison: remove closing preload once an approved release starts')
p.add_argument('--eval-render-hz',type=int,choices=(10,20,30,60),help='Rendering frequency in simulation time, not guaranteed wall-clock FPS')
p.add_argument('--visual-scene',choices=('greenhouse_v1','legacy'),default='greenhouse_v1',help='Appearance only; legacy preserves the old background for comparisons')
p.add_argument('--student-reachable-approach',action='store_true',help='Reachable pose/corridor diagnostic, no harvest')
p.add_argument('--student-align-approach',action='store_true',help='FK/vision alignment then insertion diagnostic')
p.add_argument('--student-open-approach',action='store_true',help='Diagnostic only: open jaws before approach; stop on estimated entry, no harvest')
p.add_argument('--entry-checkpoint',type=Path,help='Entry perception shadow evaluation only')
p.add_argument('--student-checkpoint',type=Path,help='Closed-loop Student v2 evaluation; never calls Teacher actions')
p.add_argument('--collect-student',action='store_true',help='Record dual RGB-D expert demonstrations; no training')
p.add_argument('--camera-config',type=Path,default=ROOT/'src/harvest_robot/config/d435_nominal.json',help='Same RGB-D profile for collection and Student evaluation')
p.add_argument('--student-detector',type=Path,default=Path('/home/bhc/Downloads/model_yolo11_seg_ver1.2.pt'))
p.add_argument('--student-vision-python',type=Path,default=ROOT/'.venvs/harvest_vision/bin/python')
p.add_argument('--student-centre-offset',type=float,default=.035)

p.add_argument('--near-fruit-arm-scale',type=float,default=1.,help='Diagnostic arm action scale within 6cm while fruit remains attached')
p.add_argument('--harvest-order',choices=('lowest-first','color'),default='lowest-first',help='Continuous execution order, independent of scene layout')
p.add_argument('--entry-first-grasp',action='store_true',help='Entry-before-contact grasp training contract')
p.add_argument('--entry-capture-shaping',action='store_true',help='Grasp refinement: penalize pushing until bilateral capture confirmation')
p.add_argument('--deployment-nine-gram',action='store_true',help='Explicit 9g runtime for training/BC/Student; preserves 480Hz physics and contact settings')
p.add_argument('--dagger-approach',action='store_true',help='Simulation-only Student approach rollout with read-only entry oracle, then Teacher recovery')
p.add_argument('--dagger-beta',type=float,default=.25,help='Teacher action probability during approach collection; not Student evaluation')
p.add_argument('--dagger-approach-s',type=float,default=2.,help='Maximum Student approach before Teacher recovery')
p.add_argument('--sequence-start-scene',type=int,default=0)
p.add_argument('--diagnostic-transport-ramp-s',type=float,default=0.,help='Evaluation: ramp transport arm scale to one over this many simulated seconds')
p.add_argument('--diagnostic-transport-scale',type=float,default=1.,help='Evaluation only: scale clamped arm increments during transport; gripper unchanged')
p.add_argument('--sequence-trace',action='store_true',help='Record per-control-step sequential contact/state diagnostics')
p.add_argument('--place-handoff-bank',type=Path,help='Capture actual transport-to-place states')
p.add_argument('--transport-pose-stop',action=argparse.BooleanOptionalAction,default=None,help='Transport training/evaluation: pose-change stop criterion; defaults to checkpoint')
p.add_argument('--transport-recovery',action='store_true',help='Staged diagnostic: slow bounded recentering after 10 seconds of transport')
p.add_argument('--transport-adaptive-grip',action=argparse.BooleanOptionalAction,default=None,help='Transport training/evaluation: compliant closing; defaults to checkpoint')
p.add_argument('--trace-transition',action='store_true',help='Save fixed batch control and contact traces')
p.add_argument('--transport-block-opening',action='store_true',help='Staged evaluation only: clamp positive transport gripper commands to zero')
p.add_argument('--staged-release',choices=('policy','fixed'),default='policy')
p.add_argument('--handoff-bank',type=Path,help='Capture physical pull-to-transport transition states during staged evaluation')
p.add_argument('--allow-appearance-only-change',action='store_true',help='Permit verified visual-material-only robot changes; geometry/physics changes still rejected')
p.add_argument('--allow-wrist-camera-mount-change',action='store_true',help='Explicit comparison: permit ONLY four verified fixed wrist camera mount/body origins and arm colors; dynamics need revalidation')
p.add_argument('--captured-break-grace',action='store_true',help='Verify retained physical break even if grasp was already confirmed; not tensile approval')
p.add_argument('--post-detach-hold-guard',action='store_true',help='Block opening during captured post-break retention before transport')
p.add_argument('--detached-capture-orientation',action='store_true',help='Use physical capture, not approach orientation, during early-detach verification')
p.add_argument('--spring-grasp-grace',action='store_true',help='Verify continuously captured early separation before rejecting it')
p.add_argument('--grasp-expert',type=Path,help='Optional entry-first grasp expert before the existing pull expert')
p.add_argument('--transport-expert',type=Path)
p.add_argument('--place-expert',type=Path)
p.add_argument('--record-teacher-motion',action='store_true',help='Save original timed joint commands for single-fruit evaluation; no hardware access')
p.add_argument('--pull-squeeze-rearm',action='store_true',help='Diagnostic opt-in; new pull training always enables confirmed-contact squeeze rearming')
p.add_argument('--pull-exploration-std',type=float,default=.02,help='Pull warm-start exploration std; bounded to half/twice this value')
p.add_argument('--pull-direction-shaping',action='store_true',help='Penalize transverse bending/pushing during confirmed attached pull')
p.add_argument('--pull-recovery-shaping',action='store_true',help='Terminal-corrected post-grasp reacquisition potential')
p.add_argument('--sts3215-gripper',action='store_true',help='12V C018 datasheet rated gripper cap 0.980665 Nm; approximate servo dynamics')
p.add_argument('--gripper-effort',type=float,help='Explicit simulation gripper torque cap in Nm; not a calibrated continuous servo rating')
p.add_argument('--grip-friction',type=float,help='Diagnostic static/dynamic contact friction override')
p.add_argument('--short-hook',action='store_true',help='Opt-in finite-travel response5 connector')
p.add_argument('--gentle-hook',action='store_true',help='Use attachment4 response4 dissipative 2.5N hook preset')
p.add_argument('--probe-noise-scale',type=float,default=0.,help='Diagnostic policy Gaussian noise multiplier of saved per-joint std')
p.add_argument('--grasp-eval',action='store_true',help='Evaluate current-robot grasp checkpoint without changing task or training')
p.add_argument('--probe-mode',choices=('command_hold','command_pull'),help='Explicit scripted diagnostic after grasp')
p.add_argument('--probe-duration',type=float,default=0.,help='Diagnostic total scene seconds; 0 uses episode limit')
p.add_argument('--probe-policy',action='store_true',help='Evaluate unassisted pull policy on seeded diagnostic scenes')
p.add_argument('--probe-ramp',action='store_true',help='Ramp diagnostic squeeze after a stationary hold')
p.add_argument('--probe-recenter',action='store_true',help='Track fruit laterally during diagnostic pull')
p.add_argument('--probe-preload',type=float,default=0.,help='Probe-only post-grasp squeeze error (rad), at unchanged actuator effort limit')
p.add_argument('--probe-close',action='store_true',help='Probe pull using continuous close command and unchanged training squeeze settings')
p.add_argument('--pull-probe',action='store_true',help='Policy grasp followed by scripted physical pull; no training')
p.add_argument('--train-task',choices=('grasp','pull','harvest','transport','place'),help='Warm-start current-URDF pull stage from grasp/pull checkpoint')
p.add_argument('--scratch-grasp',action='store_true',help='Random policy initialization for current-URDF horizontal grasp training')
p.add_argument('--place-gripper-transfer',action='store_true',help='Initialize only gripper output for place exploration')
p.add_argument('--transport-arm-scale',type=float,default=1.,help='One-time transport arm output scaling; preserve gripper')
p.add_argument('--contact-substeps',type=int,choices=(1,2,4))
p.add_argument('--contact-solver-refine',action='store_true')
p.add_argument('--release-intent-mode',action='store_true')
p.add_argument('--detached-grip-hold',action='store_true')
p.add_argument('--stop-probe',choices=('policy','hold','release','place-policy','harvest-policy'),help='Fixed-batch transport stop diagnostic, no training')
p.add_argument('--start-bank',type=str)
p.add_argument('--export-start-bank',type=Path)
p.add_argument('--bank-size',type=int,default=512)
p.add_argument('--transport-start-min',type=float,default=0.)
p.add_argument('--transport-start-max',type=float,default=0.)
p.add_argument('--checkpoint',type=Path,default=ROOT/'outputs/harvest_rl/single_teacher_reference_20260921/checkpoint/teacher_final.pt')
p.add_argument('--robot-source',choices=('current','legacy'),default='current',help='Controlled asset-only comparison; layout and teacher remain identical')
p.add_argument('--legacy-box-bottom-margin',type=float,default=None,help='v6 lower centre-height margin in metres; default current=0.010, legacy=checkpoint value; 0 reproduces strict comparison')
p.add_argument('--layout-domain',choices=('expanded','legacy-near'),default='expanded',help='legacy-near restores checkpoint region and HOME TCP 9–18cm candidates; optional matched distractor')
p.add_argument('--train-iterations',type=int,default=0,help='Warm-start single-fruit behavior on the current robot')
p.add_argument('--num-envs',type=int,default=2048,help='Training only; external evaluation always uses one env')
p.add_argument('--return-path',choices=('direct','retrace'),default='direct')
p.add_argument('--behavior-mode',choices=('checkpoint','horizontal','strict'),default='checkpoint',help='strict requires horizontal grasp and stopped controlled release; does not retrain weights')
p.add_argument('--continuous',action='store_true',help='Harvest both targets without scene reset, with physical HOME return')
p.add_argument('--fruits',type=int,choices=(1,2),default=2)
p.add_argument('--target',choices=('red','yellow','random'),default='red')
p.add_argument('--min-spacing',type=float,default=.18,help='Minimum fruit CENTRE distance, metres')
p.add_argument('--front-range',type=float,nargs=2,default=(.20,.30),help='Metres beyond mount plate front edge')
p.add_argument('--seed',type=int,default=42)
p.add_argument('--episodes',type=int,default=10)
p.add_argument('--student-episode-start',type=int,default=0,help='Collection/evaluation only: replay a deterministic layout episode without replaying preceding episodes')
p.add_argument('--steps',type=int,default=10000,help='Total control-step budget')
p.add_argument('--preview',action='store_true',help='Display two fruits and assigned target without policy/physics steps')
p.add_argument('--frames',type=int,default=0,help='Preview frames; 0 keeps GUI open')
p.add_argument('--output',type=Path)
AppLauncher.add_app_launcher_args(p)
a=p.parse_args()
if a.dagger_approach and (not a.student_checkpoint or not a.collect_student or a.student_open_approach or a.student_align_approach or a.student_reachable_approach):
    p.error('DAgger requires ordinary Student camera rollout; no approach diagnostic controllers')
if not 0<=a.dagger_beta<=1 or not 0<a.dagger_approach_s<=5:p.error('Invalid DAgger beta/time')
if a.student_episode_start<0 or (a.student_episode_start and (not a.collect_student or a.train_iterations)):
    p.error('--student-episode-start requires collection/evaluation and a nonnegative index')
if a.diagnostic_transport_ramp_s<0:p.error('Ramp duration must be nonnegative')
if a.sequence_start_scene<0 or not 0<=a.diagnostic_transport_scale<=1:p.error('Invalid diagnostic scene/scale')
if a.sequence_start_scene and not a.continuous:p.error('Scene offset requires continuous evaluation')
if (a.diagnostic_transport_scale!=1 or a.diagnostic_transport_ramp_s) and (not (a.continuous or a.collect_student) or a.train_iterations):p.error('Transport shaping requires sequence evaluation or student collection')
if not 0<a.near_fruit_arm_scale<=1:p.error('near-fruit-arm-scale must be in (0,1]')
if a.near_fruit_arm_scale!=1 and not a.transport_expert:p.error('near-fruit-arm-scale requires staged teacher')
if a.transport_recovery and not a.transport_adaptive_grip:p.error('transport-recovery requires transport-adaptive-grip')
if (a.transport_recovery or a.transport_block_opening or a.place_handoff_bank or a.staged_release!='policy') and (not a.transport_expert or a.train_iterations):p.error('Place diagnostic requires staged evaluation, no training')
if (a.transport_pose_stop is not None or a.transport_adaptive_grip is not None) and not (a.transport_expert or a.train_task=='transport' or a.stop_probe=='policy'):
    p.error('Transport controls require transport training/policy evaluation or staged evaluation')
if a.continuous and (a.handoff_bank or a.place_handoff_bank or a.trace_transition):
    p.error('Fixed-batch bank/trace collection is not supported in continuous mode')
if a.place_handoff_bank and a.place_handoff_bank.exists():p.error('Place bank must be a new file')
if a.handoff_bank and (not a.transport_expert or a.handoff_bank.exists()):p.error('handoff-bank requires staged evaluation and a new output file')
if a.grasp_expert and (not a.transport_expert or a.train_iterations):p.error('grasp-expert requires staged evaluation, no training')
if a.transport_expert or a.place_expert:
    if not (a.transport_expert and a.place_expert) or (a.stop_probe!='harvest-policy' and not a.continuous and not a.collect_student) or a.train_iterations:
        p.error('Both experts require harvest-policy evaluation, no training')
if a.record_teacher_motion and (a.train_iterations or a.scratch_grasp or a.preview or a.continuous or a.pull_probe or a.grasp_eval or a.fruits!=1):
    p.error('--record-teacher-motion requires ordinary single-fruit harvest evaluation')
if a.grasp_eval:
    if a.train_task or a.train_iterations or a.scratch_grasp or a.pull_probe or a.probe_mode or a.probe_close:
        p.error("--grasp-eval is a standalone policy evaluation")
    a.pull_probe=True
    a.probe_policy=True
if not 0 < a.pull_exploration_std <= .2:p.error('pull exploration std must be in (0, 0.2]')
if not 0 <= a.probe_noise_scale < float('inf'):p.error('probe noise scale must be finite and nonnegative')
if not 0 <= a.probe_duration <= 20:p.error('probe duration must be in [0,20]')
if a.probe_mode and (not a.pull_probe or a.probe_policy):p.error('probe mode requires scripted pull probe')
if a.probe_policy and not a.pull_probe:p.error('--probe-policy requires --pull-probe')
if a.probe_noise_scale and not a.probe_policy:p.error('--probe-noise-scale requires --probe-policy')
if a.scratch_grasp and (not a.train_iterations or a.robot_source!='current' or a.behavior_mode!='horizontal'):
    p.error('--scratch-grasp requires current robot, horizontal behavior, and training')
if a.scratch_grasp and '--checkpoint' in __import__('sys').argv:
    p.error('--scratch-grasp cannot load --checkpoint')
if a.train_task and (a.scratch_grasp or not a.train_iterations or a.behavior_mode!=('strict' if a.train_task in ('harvest','transport','place') else 'horizontal') or '--checkpoint' not in __import__('sys').argv):
    p.error('--train-task requires explicit checkpoint, training, and horizontal (pull) or strict (harvest) behavior')
if not 0<=a.probe_preload<=.06 or (a.probe_preload and not a.pull_probe):p.error('probe preload requires pull probe and 0..0.06 rad')
if a.pull_probe and (a.train_iterations or a.scratch_grasp or a.continuous or a.fruits!=1):
    p.error('pull probe requires single fruit evaluation')
if a.train_iterations<0 or a.num_envs<1:p.error('Invalid training limits')
if a.train_iterations and (a.continuous or a.preview or a.fruits!=1 or a.behavior_mode not in ('horizontal','strict')):
    p.error('Training requires --fruits 1 --behavior-mode horizontal or strict, no continuous/preview')
if a.continuous and (a.fruits!=2 or a.preview or a.target=='random'):p.error('continuous requires two fruits, explicit order, no preview')
if a.layout_domain=='legacy-near' and a.target=='random':p.error('legacy-near requires an explicit red/yellow target')
if a.fruits==1 and a.target=='random':p.error('Matched single-fruit comparison requires --target red or yellow')
if not 0<=a.transport_arm_scale<=1 or (a.transport_arm_scale!=1 and (a.train_task!='transport' or not a.train_iterations)):
    p.error('transport-arm-scale requires transport training and value 0..1')
if a.seed<0 or a.episodes<1 or a.steps<1 or a.frames<0:p.error('Invalid seed/episode/step/frame limits')
if a.preview and a.headless and a.frames==0:p.error('Headless preview requires --frames > 0')
if not 0<=a.front_range[0]<a.front_range[1]:p.error('Invalid front range')
if a.entry_checkpoint and (not a.collect_student or not a.entry_checkpoint.is_file()):p.error('--entry-checkpoint requires camera path and model file')
if a.student_reachable_approach and a.student_align_approach:p.error('Choose only one approach controller')
if a.student_align_approach or a.student_reachable_approach:a.student_open_approach=True
if a.student_open_approach and not a.student_checkpoint:p.error('--student-open-approach requires Student checkpoint')
if a.student_checkpoint and (not a.collect_student or not a.student_checkpoint.is_file()):p.error('--student-checkpoint requires camera collection path and existing checkpoint')
if a.collect_student:
    if a.continuous or a.train_iterations or a.train_task or a.preview or a.stop_probe or a.pull_probe or a.export_start_bank or a.scratch_grasp or a.robot_source!='current' or not a.grasp_expert or not a.transport_expert or a.num_envs!=1:
        p.error('Student collection requires current robot, staged grasp experts, one env, ordinary assigned evaluation only')
    if not a.student_detector.is_file() or not a.student_vision_python.is_file(): p.error('Missing detector or vision Python')
    if not 0<=a.student_centre_offset<=.1:p.error('Invalid centre offset')
    a.enable_cameras=True
elif a.enable_cameras:p.error('Use preview_current_d435.sh or --collect-student')
# Load original reference defaults and verify preserved robot/workspace provenance FIRST.
settings=load_settings(argparse.Namespace(checkpoint=None if a.scratch_grasp else a.checkpoint,resume=None,warm_start=None,
    mode='train' if a.scratch_grasp else 'play',seed=a.seed,split='eval',use_prepared_assets=True,current_asset_adapter=True))
if a.scratch_grasp:
    settings.task='grasp';settings.attachment_version=2;settings.reward_version=3
if not a.transport_expert and not a.scratch_grasp and not a.train_task and not a.pull_probe and not a.stop_probe and not a.export_start_bank and (settings.task!='harvest' or settings.attachment_version not in (2,4)):
    p.error('This comparison requires an attachment2/4 harvest teacher')
if a.grasp_eval and settings.task != "grasp":p.error("--grasp-eval requires a grasp checkpoint")
if a.place_gripper_transfer and a.train_task!='place':p.error('place-gripper-transfer requires place training')
original=settings.as_dict()
if a.entry_first_grasp:
    if a.train_task!='grasp':p.error('entry-first-grasp is for explicit grasp training; evaluation inherits checkpoint')
    settings.entry_first_grasp=True
if a.train_task=='grasp':
    settings.task='grasp';settings.reward_version=3;settings.start_bank=''
    settings.stage_transfer=True;settings.pull_progress_reward=False
    settings.pull_direction_shaping=False;settings.pull_recovery_shaping=False
    settings.detached_grip_hold=False
    settings.transport_adaptive_grip=False;settings.transport_pose_stop=False
if a.entry_capture_shaping:
    if a.train_task!='grasp' or not settings.entry_first_grasp:p.error('Capture shaping requires entry-first grasp training')
    settings.entry_capture_shaping=True
if a.transport_adaptive_grip is not None:settings.transport_adaptive_grip=a.transport_adaptive_grip
if a.transport_pose_stop is not None:settings.transport_pose_stop=a.transport_pose_stop
if a.contact_substeps is not None:settings.contact_substeps=a.contact_substeps
if a.contact_solver_refine:settings.contact_solver_refine=True
if a.release_intent_mode:settings.release_intent_mode=True
if a.detached_grip_hold:settings.detached_grip_hold=True
if a.sts3215_gripper:
    if a.gripper_effort is not None:p.error('choose --sts3215-gripper or --gripper-effort')
    settings.gripper_effort=.980665
if a.pull_direction_shaping:
    if a.train_task!='pull':p.error('direction shaping requires pull training')
    settings.pull_direction_shaping=True
if a.pull_recovery_shaping:
    if not a.train_task:p.error('recovery shaping requires pull training')
    settings.pull_recovery_shaping=True
if a.gripper_effort is not None:
    if not 0 < a.gripper_effort <= 2.94:p.error('gripper effort must be in (0,2.94] Nm')
    settings.gripper_effort=a.gripper_effort
if a.grip_friction is not None:
    if not 0 < a.grip_friction <= 2:p.error('friction must be in (0,2]')
    settings.grip_friction=settings.dynamic_friction=a.grip_friction
if (a.train_task=='pull' or a.pull_probe) and not a.grasp_eval:
    if settings.task not in ('grasp','pull') or settings.attachment_version!=4 or settings.stem_response_version not in (4,5):
        p.error('Pull transfer requires an attachment4/response4 or5 grasp or pull checkpoint')
    settings.task='pull'
    settings.reward_version=5
    settings.pull_progress_reward=bool(a.train_task)
    if a.train_task:
        settings.stage_transfer=True
        settings.pull_squeeze_ramp=True
        settings.pull_squeeze_rearm=True
    if a.pull_squeeze_rearm: settings.pull_squeeze_rearm=True
if a.train_task in ('harvest','transport','place'):
    from harvest_rl.behavior_contract import prepare_harvest_transfer
    prepare_harvest_transfer(settings)
    settings.task=a.train_task
    settings.start_bank=a.start_bank or ''
    settings.transport_start_min=a.transport_start_min
    settings.transport_start_max=a.transport_start_max
    settings.transport_replay_fraction=0.

if a.gentle_hook or a.scratch_grasp:
    from harvest_rl.behavior_contract import apply_gentle_hook
    apply_gentle_hook(settings)
if a.short_hook:
    from harvest_rl.behavior_contract import apply_short_hook
    apply_short_hook(settings)
if a.robot_source=='current':
    settings.shape_placement=True
    settings.box_bottom_contact_tolerance=.010
from harvest_rl.behavior_contract import apply_behavior_mode
apply_behavior_mode(settings,a.behavior_mode)
if a.behavior_mode=='strict':
    print('STRICT_BEHAVIOR: horizontal grasp + stopped release; old v6 weights have not learned these requirements',flush=True)
if a.legacy_box_bottom_margin is not None:
    settings.legacy_box_bottom_margin=a.legacy_box_bottom_margin
elif a.robot_source=='current':
    settings.legacy_box_bottom_margin=.010
settings.num_fruits=a.fruits;settings.sequence=False;settings.target_mode='external'
settings.pregrasp_fraction=0.;settings.random_colors=False;settings.curriculum=1.
settings.region_min=(a.front_range[0],-.175,-.10)
settings.region_max=(a.front_range[1],.175,.35)
if a.layout_domain=='legacy-near':
    settings.curriculum=0.
    settings.region_min=tuple(original['region_min'])
    settings.region_max=tuple(original['region_max'])
if a.train_iterations or a.pull_probe or a.export_start_bank or a.stop_probe:
    settings.target_mode='nearest'
    settings.workspace_split='train'
if a.train_task in ('transport','place') or a.stop_probe or (a.export_start_bank and settings.task=='transport'):
    settings.target_mode='random'
if a.export_start_bank:
    if settings.task not in ('pull','transport') or a.bank_size<1:
        p.error('Bank export requires pull/transport policy, no training, positive bank size')
    if a.export_start_bank.exists():p.error('Bank output already exists')
if a.stop_probe in ('policy','place-policy') and a.start_bank:
    settings.start_bank=a.start_bank
    settings.transport_start_min=a.transport_start_min;settings.transport_start_max=a.transport_start_max
if a.stop_probe=='release':
    if not a.start_bank:p.error('release probe requires place start bank')
    settings.task='place';settings.start_bank=a.start_bank
    settings.transport_start_min=0.;settings.transport_start_max=0.
if a.stop_probe=='harvest-policy':
    from harvest_rl.behavior_contract import prepare_harvest_transfer
    prepare_harvest_transfer(settings)
    settings.task='harvest';settings.start_bank='';settings.target_mode='nearest'
    settings.transport_start_min=0.;settings.transport_start_max=0.
if (a.continuous or a.collect_student) and a.transport_expert:
    from harvest_rl.behavior_contract import prepare_harvest_transfer
    prepare_harvest_transfer(settings)
    settings.task='harvest';settings.start_bank='';settings.target_mode='external'
    settings.transport_start_min=0.;settings.transport_start_max=0.
if a.stop_probe:
    if settings.task!=('harvest' if a.stop_probe=='harvest-policy' else 'place' if a.stop_probe in ('release','place-policy') else 'transport') or a.train_iterations or a.train_task or a.pull_probe or a.export_start_bank or a.preview or a.continuous:
        p.error('stop-probe requires a transport checkpoint and no other execution mode')
if a.spring_grasp_grace:
    if not a.grasp_expert or settings.attachment_version!=4:p.error('spring-grasp-grace requires entry staged attachment4 evaluation')
    settings.spring_grasp_grace=True
if a.captured_break_grace:
    if not a.spring_grasp_grace:p.error('captured-break-grace requires spring-grasp-grace')
    settings.captured_break_grace=True
if a.post_detach_hold_guard:
    if not a.grasp_expert or not a.transport_expert:p.error('post-detach-hold-guard requires staged experts')
    settings.post_detach_hold_guard=True
if a.detached_capture_orientation:
    if not a.spring_grasp_grace:p.error('detached-capture-orientation requires spring-grasp-grace')
    settings.detached_capture_orientation=True
if a.grasp_expert:
    settings.entry_first_grasp=True
    settings.entry_capture_shaping=json.loads((a.grasp_expert.parent/'run.json').read_text())['task'].get('entry_capture_shaping',False)
if a.capture_settle:
    if not a.collect_student or a.student_checkpoint or a.train_iterations or a.train_task:p.error("Capture settle requires Teacher evaluation")
if a.capture_gripper_target_hold and (not a.capture_settle or not a.grasp_expert or not a.transport_expert):
    p.error('Capture gripper target hold requires capture-settle and staged Teacher experts')
if a.transport_gripper_target_hold and not a.capture_gripper_target_hold:
    p.error('Transport gripper target hold requires capture-gripper-target-hold')
if not 0<=a.transport_gripper_preload_step<=.010 or (a.transport_gripper_preload_step and not a.transport_gripper_target_hold):
    p.error('Transport preload step must be 0..0.010 rad and requires transport-gripper-target-hold')
if a.transport_bounded_preload:
    if not a.transport_gripper_target_hold:p.error('Bounded preload requires transport-gripper-target-hold')
    if not (0<a.transport_preload_max_close<=.040 and a.transport_gripper_preload_step<=a.transport_preload_max_close
            and 0<a.transport_preload_rate<=.05 and 0<a.transport_preload_error<=.035):
        p.error('Bounded preload: budget in (0,.040] rad including initial step, rate in (0,.05] rad/s, error in (0,.035] rad')
if a.transport_linear_pose_stop:
    if not a.collect_student or a.student_checkpoint or a.train_iterations or a.train_task:p.error("Pose stop comparison requires Teacher evaluation")
    settings.transport_linear_pose_stop=True
if a.eval_fruit_mass is not None:
    if not a.collect_student or a.student_checkpoint or a.train_iterations or a.train_task or not 0<a.eval_fruit_mass<=.1:p.error('--eval-fruit-mass requires Teacher-only camera evaluation, mass in (0,0.1] kg')
    print(f'EVAL_FRUIT_MASS: {settings.mass} -> {a.eval_fruit_mass} kg; weights unchanged',flush=True)
    settings.mass=a.eval_fruit_mass
if a.deployment_nine_gram:
    if a.eval_fruit_mass is not None:p.error('Choose deployment preset or quarantined mass evaluation')
    if not (a.train_task=='grasp' or a.collect_student):p.error('9g deployment preset supports grasp training or staged camera collection/evaluation')
    settings.mass=.009
    if a.collect_student:
        settings.transport_linear_pose_stop=True
        settings.release_measured_open=True
        if not settings.release_intent_mode:p.error('9g release preset requires release-intent mode')
contact_transfer=any(v is not None for v in (a.eval_fruit_collision,a.eval_gripper_gains,a.eval_physics_hz,a.eval_contact_model))
if contact_transfer or a.eval_render_hz is not None or a.eval_release_measured_open:
    if not a.collect_student or a.student_checkpoint or a.train_iterations or a.train_task or not a.transport_expert:
        p.error('Contact/clock overrides require frozen staged Teacher evaluation, no Student or training')
    if a.eval_fruit_collision is not None:settings.fruit_collision_mode=a.eval_fruit_collision
    if a.eval_gripper_gains is not None:
        settings.gripper_stiffness,settings.gripper_damping=(8.,.3) if a.eval_gripper_gains=='baseline' else (2.,.05)
    if a.eval_contact_model is not None:
        settings.contact_stiffness,settings.contact_damping=(0.,0.) if a.eval_contact_model=='rigid' else (15000.,20.)
    if a.eval_physics_hz is not None:
        if settings.physics_dt!=1/240 or settings.decimation!=12:p.error('Clock transfer requires original 20Hz/nominal240Hz profile')
        settings.contact_substeps=a.eval_physics_hz//240
    if a.eval_render_hz is not None:settings.render_hz=a.eval_render_hz
    if a.eval_release_measured_open:
        if not settings.release_intent_mode:p.error("Measured release requires approved release-intent mode")
        settings.release_measured_open=True
settings.validate()
# RTX camera collection needs concurrent rendering tasks. Keep the established
# single-worker setting for non-camera evaluation/training.
task_threads = 8 if a.collect_student else 1
a.kit_args=(a.kit_args or '')+f' --/plugins/carb.tasking.plugin/threadCount={task_threads}'
app=AppLauncher(a).app
env=None;failed=False
try:
    import torch
    import yaml
    from scipy.spatial.transform import Rotation
    from harvest_rl.current_robot import prepare_current_robot
    from harvest_rl.current_pair_env import CurrentPairEnv
    from harvest_rl.policy import teacher_config
    from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
    from rsl_rl.runners import OnPolicyRunner
    source_meta={} if a.scratch_grasp else json.loads((a.checkpoint.parent/'run.json').read_text())
    selected_camera_config=json.loads(a.camera_config.read_text()) if a.collect_student else None
    if selected_camera_config and selected_camera_config.get('schema')=='d435_deployment_v2':
        from harvest_sensors.deployment_asset import prepare_deployment_robot
        usd,kin,asset=prepare_deployment_robot(source_meta['current_asset'],selected_camera_config)
    else:
        usd,kin,asset=prepare_current_robot()
    if source_meta.get('current_asset') and source_meta['current_asset']['asset_input_sha256']!=asset['asset_input_sha256']:
        from harvest_rl.current_robot import appearance_only_change,wrist_mount_only_change
        appearance_ok=(a.collect_student or a.allow_appearance_only_change) and appearance_only_change(source_meta['current_asset'],asset)
        camera_ok=a.allow_wrist_camera_mount_change and wrist_mount_only_change(source_meta['current_asset'],asset)
        if not (appearance_ok or camera_ok):
            raise ValueError('Current robot changed since this checkpoint; validate asset change explicitly')
        metadata_change='wrist-camera fixed origins/colors only; dynamics require revalidation' if camera_ok else 'appearance only; geometry/physics preserved'
        asset['checkpoint_transfer']=dict(previous_sha256=source_meta['current_asset']['asset_input_sha256'],change=metadata_change)
        print('ROBOT_ASSET:',metadata_change,flush=True)
    old=ArmKinematics(CACHE/'harvest_training.urdf')
    bank=np.load(CACHE/'workspace.npz')
    frame,errors=current_to_policy_frame(old,kin,np.vstack((bank['home'],bank['q'])))
    assembly=yaml.safe_load((ROOT/'src/smartfarm_description/config/assembly.yaml').read_text())
    box=(frame@kin.fk(bank['home'],'harvest_box'))[:3,3]
    bounds_min=box+np.array([-assembly['box_length']/2+assembly['box_wall'],
                             -assembly['box_width']/2+assembly['box_wall'],assembly['box_wall']])
    bounds_max=box+np.array([assembly['box_length']/2-assembly['box_wall'],
                             assembly['box_width']/2-assembly['box_wall'],assembly['box_height']])
    if not np.allclose(bounds_min,settings.box_min) or not np.allclose(bounds_max,settings.box_max):
        raise ValueError('Current box dimensions differ from teacher success geometry; review before evaluation')
    points=bank['points'][int(len(bank['points'])*.8):]
    lo=np.array(settings.region_origin)+settings.region_min;hi=np.array(settings.region_origin)+settings.region_max
    home_tcp=old.grasp_fk(bank['home'],settings.diameter)[:3,3]
    distance=np.linalg.norm(points-home_tcp,axis=-1)
    eligible=((points>=lo)&(points<=hi)).all(-1)&(distance>.09)
    distractor_points=points[eligible].copy()
    if a.layout_domain=='legacy-near':eligible &= distance<.18
    points=points[eligible]
    if not len(points):raise ValueError('No candidates in requested layout domain')
    # Duplicate logical slots represent one uniformly sampled fruit, not two actors.
    pairs=np.column_stack((np.arange(len(points)),np.arange(len(points)))) if a.layout_domain=='legacy-near' and not a.continuous else separated_pairs(points,a.min_spacing)
    if a.min_spacing<settings.diameter+.035:raise ValueError('Requested spacing below conservative fruit clearance')
    q=Rotation.from_matrix(frame[:3,:3]).as_quat()[[3,0,1,2]]
    colors=['Red','Yellow'] if a.fruits==2 else ['Red' if a.target=='red' else 'Yellow']
    out=create_run_directory(a.output or ROOT/'runs/harvest_rl'/f'current_pair_{datetime.now():%Y%m%d_%H%M%S}')
    metadata=dict(asset=json.loads((CACHE/'preparation.json').read_text()),train_iterations=a.train_iterations,num_envs=a.num_envs if (a.train_iterations or a.stop_probe or a.export_start_bank) else 1,behavior_mode=a.behavior_mode,return_path=a.return_path,continuous=a.continuous,robot_source=a.robot_source,layout_domain=a.layout_domain,home_tcp_policy_m=home_tcp.tolist(),candidate_points_policy_m=points.tolist(),command=__import__('sys').argv,scratch_grasp=a.scratch_grasp,checkpoint=None if a.scratch_grasp else str(a.checkpoint),
        checkpoint_sha256=None if a.scratch_grasp else hashlib.sha256(a.checkpoint.read_bytes()).hexdigest(),original_task=original,task=settings.as_dict(),
        current_asset=asset,current_base_to_policy_world=frame.tolist(),fk_errors=errors,
        box_min_verified=bounds_min.tolist(),box_max_verified=bounds_max.tolist(),
        distractor_candidate_count=len(distractor_points),candidate_count=len(points),pair_count=len(pairs),min_spacing_m=a.min_spacing,target=a.target,
        observation='v6 selected target remapped to original slot0; all distractor slots padded with zero. No obstacle-aware policy or normalizer adaptation.',
        limits=('Two assigned harvests with physical recorded-path return; near mode puts BOTH targets in the original near domain. Not matched to single-target RNG; no vision selection.' if a.continuous else 'One assigned harvest per trial; not sequential harvesting or vision selection. Source robot is rotated as a whole into original policy coordinates. Actual new geometry is simulated.'))
    (out/'run.json').write_text(json.dumps(metadata,indent=2))
    common=dict(visual_scene=a.visual_scene,robot_usd=usd if a.robot_source=='current' else CACHE/'harvest_robot.usd',
        robot_root_pose=(tuple(frame[:3,3]),tuple(q)) if a.robot_source=='current' else None,
        fruit_color_override=colors,fruit_asset_cache=usd.parent/'pair_fruit_assets')
    if a.train_iterations or a.pull_probe or a.export_start_bank or a.stop_probe:
        from harvest_rl.env import HarvestEnv
        class PullProbeEnv(HarvestEnv):
            def _get_dones(self):
                self._update_task()
                return torch.zeros_like(self.success),torch.zeros_like(self.success)
        EnvClass=PullProbeEnv if a.stop_probe or (a.pull_probe and not a.export_start_bank) else HarvestEnv
        env=EnvClass(settings,num_envs=1 if a.pull_probe and not a.export_start_bank else a.num_envs,device=a.device,**common)
    else:
        PairEnv=CurrentPairEnv
        if a.collect_student:
            from harvest_rl.d435_rig import DualD435Rig
            camera_config=json.loads(a.camera_config.read_text())
            if camera_config.get('schema') == 'd435_deployment_v2':
                from harvest_sensors.deployment import validate_deployment
                validate_deployment(camera_config)
            class CameraPairEnv(CurrentPairEnv):
                def _setup_scene(self):
                    super()._setup_scene()
                    self.student_rig=DualD435Rig(kin,camera_config,frame)
            PairEnv=CameraPairEnv
        env=PairEnv(settings,num_envs=1,device=a.device,**common,
            layout_points=points,layout_pairs=pairs,requested_target=a.target,layout_seed=a.seed,
            distractor_points=distractor_points if a.layout_domain=='legacy-near' and a.fruits==2 and not a.continuous else None,
            distractor_spacing=a.min_spacing)
        if a.collect_student and camera_config.get('schema') == 'd435_deployment_v2':
            env.student_rig.install_physics_hook(env)
            asset['sensor_visual_revision']=dict(current_wrist_meshes=env.student_rig.visual_mesh_count,
                arm_appearance_groups=env.student_rig.arm_appearance_groups,
                physics_properties_verified_unchanged=env.student_rig.physics_properties_checked,
                physical_asset_preserved=True,scope='current arm appearance and right fixed gripper/camera display meshes; no collisions, mass or drives changed')
    metadata['visual_scene']=env.visual_scene
    (out/'run.json').write_text(json.dumps(metadata,indent=2))
    runtime_limits=env.robot.root_physx_view.get_dof_max_forces()[0,env.jids].cpu().tolist()
    (out/'actuator_runtime.json').write_text(json.dumps(dict(
        joint_names=[env.robot.joint_names[i] for i in env.jids],
        physx_effort_limits_Nm=runtime_limits,
        gripper_requested_Nm=settings.gripper_effort,
        torque_diagnostic='implicit PD estimate, not measured drive torque'),indent=2))
    if abs(runtime_limits[-1]-settings.gripper_effort)>1e-5:
        raise RuntimeError('PhysX gripper limit differs from requested setting')
    hud=None
    if not a.headless:
        import omni.ui as ui
        hud_window=ui.Window('Assigned harvest test',width=460,height=100)
        with hud_window.frame:
            hud=ui.Label('Preparing scene...',word_wrap=True)
    def show_target():
        if hud is not None:
            hud.text=f"Target: {env.last_layout['target_color']} | fruits: {a.fruits} | centre spacing: {env.last_layout['center_distance_m']:.3f} m"
    def check_pose():
        joint=env.robot.data.joint_pos[0,env.jids].cpu().numpy()
        expected=old.fk(joint,'arm_2/gripper_link')[:3,3]
        actual=(env.robot.data.body_link_pos_w[0,env.tcp_body]-env.scene.env_origins[0]).cpu().numpy()
        error=float(np.linalg.norm(actual-expected))
        if error>2e-4:raise RuntimeError(f'Current robot FK/world frame mismatch: {error}m')
        return error
    def check_target(obs):
        selected=env.fruits[env.assignment_slot].data.root_link_pos_w
        torch.testing.assert_close(env._target_fruit().data.root_link_pos_w,selected)
        torch.testing.assert_close(obs['policy'][:,25:28],selected-env._tcp()[0])
        torch.testing.assert_close(obs['policy'][:,44:47],selected-env._tcp()[0])
    if a.preview:
        env.layout_episode=0;env.reset();obs=env.assign_target(env.assignment_slot);check_target(obs);show_target()
        (out/'layout.json').write_text(json.dumps(env.last_layout,indent=2))
        print('PREVIEW_LAYOUT',env.last_layout,flush=True)
        print('FK_POSITION_ERROR_M',check_pose(),flush=True)
        count=0
        while app.is_running() and (a.frames==0 or count<a.frames):
            env.sim.render();count+=1
    else:
        wrapped=RslRlVecEnvWrapper(env,clip_actions=1.)
        cfg=teacher_config();cfg['seed']=a.seed
        if a.train_iterations and not a.scratch_grasp:
            cfg['algorithm'].update(learning_rate=5e-5,schedule='fixed',entropy_coef=.001)
        runner=OnPolicyRunner(wrapped,cfg,str(out) if a.train_iterations else None,device=a.device)
        if not a.scratch_grasp:
            runner.load(str(a.checkpoint),load_optimizer=False)
        policy=runner.get_inference_policy(device=a.device)
        if a.transport_expert:
            from harvest_runtime.staged_teacher import StagedTeacher
            policy=StagedTeacher(env,runner.alg.policy,a.transport_expert,a.place_expert,a.grasp_expert,allow_mass_transfer=a.eval_fruit_mass is not None or a.deployment_nine_gram,allow_contact_transfer=contact_transfer)
            if a.deployment_nine_gram:
                policy.contract.pop('evaluation_mass_override_kg',None)
                policy.contract['deployment_mass_kg']=settings.mass
            policy.release_mode=a.staged_release
            policy.capture_settle=a.capture_settle
            env.capture_gripper_target_hold=a.capture_gripper_target_hold
            env.transport_gripper_target_hold=a.transport_gripper_target_hold
            env.transport_gripper_preload_step=a.transport_gripper_preload_step
            env.transport_bounded_preload=a.transport_bounded_preload
            env.transport_preload_max_close=a.transport_preload_max_close
            env.transport_preload_rate=a.transport_preload_rate
            env.transport_preload_error=a.transport_preload_error
            policy.near_fruit_arm_scale=a.near_fruit_arm_scale
            policy.block_transport_opening=a.transport_block_opening
            policy.diagnostic_transport_scale=a.diagnostic_transport_scale
            policy.diagnostic_transport_ramp_s=a.diagnostic_transport_ramp_s
            policy.contract['action_execution']=dict(version=1,labels='post_controller_clipped_action',
                transport_initial_scale=a.diagnostic_transport_scale,transport_ramp_s=a.diagnostic_transport_ramp_s,
                near_fruit_arm_scale=a.near_fruit_arm_scale,block_transport_opening=a.transport_block_opening,
                release_mode=a.staged_release,transport_recovery=a.transport_recovery,
                student_reapply_teacher_ramp=False)
            if a.capture_settle:policy.contract['action_execution']['capture_settle']=True
            if a.capture_gripper_target_hold:policy.contract['action_execution']['capture_gripper_target_hold']=True
            if a.transport_gripper_target_hold:policy.contract['action_execution']['transport_gripper_target_hold']=True
            if a.transport_gripper_preload_step:policy.contract['action_execution']['transport_gripper_preload_step_rad']=a.transport_gripper_preload_step
            if a.transport_bounded_preload:
                policy.contract['action_execution']['transport_bounded_preload']=dict(
                    max_close_rad=a.transport_preload_max_close,rate_rad_s=a.transport_preload_rate,
                    desired_error_rad=a.transport_preload_error,loss_behavior='freeze target; pause additional closing; scoring unchanged')
            env.transport_adaptive_grip=settings.transport_adaptive_grip
            env.transport_pose_stop=settings.transport_pose_stop
            if a.transport_recovery:
                from harvest_runtime.transport_recovery import TransportRecovery
                policy.recovery=TransportRecovery(env)
            if a.place_handoff_bank:
                from harvest_rl.stage_bank import StageBankCollector
                import copy
                capture_settings=copy.deepcopy(settings);capture_settings.task="transport"
                policy.place_collector=StageBankCollector(capture_settings,a.transport_expert,a.num_envs)
            if a.handoff_bank:
                from harvest_rl.stage_bank import StageBankCollector
                import copy
                capture_settings=copy.deepcopy(settings);capture_settings.task="pull"
                policy.collector=StageBankCollector(capture_settings,a.checkpoint,a.num_envs)
                policy.collector.metadata["staged_experts"]=policy.contract
            (out/"expert_contract.json").write_text(json.dumps(policy.contract,indent=2))
        if a.pull_probe:
            a.probe_std=runner.alg.policy.std.detach().clone()
        if a.collect_student:
            from harvest_runtime.student_collect import evaluate
            evaluate(env,wrapped,policy,a,out,app,kin,frame)
        elif a.stop_probe:
            from harvest_runtime.stop_probe import evaluate
            evaluate(env,wrapped,policy,a,out)
            if a.handoff_bank:policy.collector.save(a.handoff_bank)
            if a.place_handoff_bank:policy.place_collector.save(a.place_handoff_bank)
        elif a.export_start_bank and not a.train_iterations:
            from harvest_rl.stage_bank import StageBankCollector
            env.bank_collector=StageBankCollector(settings,a.checkpoint,a.bank_size)
            obs=wrapped.get_observations()
            with torch.inference_mode():
                for _ in range(a.steps):
                    obs,_,_,_=wrapped.step(policy(obs))
                    if env.bank_collector.count>=a.bank_size:break
            if env.bank_collector.count<a.bank_size:raise RuntimeError('Insufficient successful physical starts; no bank saved')
            env.bank_collector.save(a.export_start_bank)
        elif a.train_iterations:
            if not a.scratch_grasp:
                from harvest_rl.exploration import prepare_stage_normalizers,configure_exploration
                changes=prepare_stage_normalizers(runner.alg.policy)
                if a.place_gripper_transfer:
                    from harvest_rl.exploration import initialize_place_gripper
                    initialize_place_gripper(runner.alg.policy)
                if a.transport_arm_scale!=1:
                    from harvest_rl.exploration import scale_warm_start_arm
                    scale_warm_start_arm(runner.alg.policy,a.transport_arm_scale)
                    (out/'arm_transfer.json').write_text(json.dumps(dict(scale=a.transport_arm_scale,gripper_preserved=True)))
                (out/'normalization_override.json').write_text(json.dumps(changes,indent=2))
                std=a.pull_exploration_std if a.train_task else .1
                guard=configure_exploration(runner.alg.policy,runner.alg.optimizer,reset_std=std,minimum=std/2,maximum=std*2)
                (out/'exploration_override.json').write_text(json.dumps(dict(reset_std=std,minimum=std/2,maximum=std*2),indent=2))
            runner.current_learning_iteration=0
            runner.learn(num_learning_iterations=a.train_iterations,init_at_random_ep_len=False)
            runner.save(str(out/'teacher_final.pt'))
            if a.export_start_bank:
                from harvest_rl.stage_bank import StageBankCollector
                env.bank_collector=StageBankCollector(settings,out/'teacher_final.pt',a.bank_size)
                obs=wrapped.get_observations()
                with torch.inference_mode():
                    for _ in range(a.steps):
                        obs,_,_,_=wrapped.step(policy(obs))
                        if env.bank_collector.count>=a.bank_size:break
                if env.bank_collector.count<a.bank_size:raise RuntimeError('Insufficient successful stage starts')
                env.bank_collector.save(a.export_start_bank)

        elif a.pull_probe:
            from harvest_runtime.scripted_pull_probe import evaluate
            evaluate(env,wrapped,policy,a,out,app)
        elif a.continuous:
            from harvest_runtime.sequence_eval import evaluate
            evaluate(env,wrapped,policy,a,out,app)
        else:
            results=[];steps=0
            with torch.inference_mode():
                for episode in range(a.episodes):
                    if steps>=a.steps or not app.is_running():break
                    env.layout_episode=episode;env.reset()
                    obs=env.assign_target(env.assignment_slot)
                    check_target(obs)
                    show_target()
                    record=dict(env.last_layout,initial_fk_error_m=check_pose(),
                                target_break_threshold_N=float(env.threshold[0,env.assignment_slot]),fruit_colors=list(env.fruit_colors))
                    record['pair_positions_current_base_m']=((np.array(record['pair_positions_policy_m'])-frame[:3,3])@frame[:3,:3]).tolist()
                    record['initial_observation']=obs['policy'][0].cpu().tolist()
                    record['initial_action']=policy(obs)[0].cpu().tolist()
                    elapsed=0
                    motion=None
                    if a.record_teacher_motion:
                        from harvest_rl.teacher_motion_record import MotionRecord
                        motion=MotionRecord(env.step_dt,env.robot.data.joint_pos[0,env.jids].cpu().tolist(),
                                            a.checkpoint,[env.robot.joint_names[i] for i in env.jids])
                    while env.assignment_status=='RUNNING' and steps<a.steps and app.is_running():
                        obs,reward,_,_=wrapped.step(policy(obs))
                        if motion is not None:
                            motion.append(env.targets[0].cpu().tolist(),env.robot.data.joint_pos[0,env.jids].cpu().tolist())
                        if not torch.isfinite(obs['policy']).all():raise FloatingPointError('Non-finite teacher observation')
                        elapsed+=1;steps+=1
                    if env.assignment_status=='RUNNING':env.cancel_target()
                    record.update(status=env.assignment_status,sim_s=elapsed*env.step_dt,
                                  grasp=bool(env.has_grasped[0]),detach=bool(env.valid_detach[0]),
                                  other_attached=bool(env.attached[0,1-env.assignment_slot]) if a.fruits==2 else None,
                                  target_position_policy_m=(env._target_fruit().data.root_link_pos_w[0]-env.scene.env_origins[0]).cpu().tolist(),
                                  terminal_diagnostics={k:float(v[0]) for k,v in env.last_diagnostics.items() if k.startswith('failure_')})
                    results.append(record)
                    if motion is not None and motion.samples:
                        motion.save(out/f'teacher_motion_{episode:03d}.json',env.assignment_status,record)
                    (out/'episodes.json').write_text(json.dumps(results,indent=2))
                    print('ASSIGNED_HARVEST',json.dumps(record),flush=True)
            summary={status:sum(r['status']==status for r in results) for status in ('SUCCEEDED','FAILED','TIMED_OUT','CANCELLED')}
            summary.update(episodes=len(results),grasp=sum(r['grasp'] for r in results),detach=sum(r['detach'] for r in results),steps=steps)
            (out/'metrics.json').write_text(json.dumps(summary,indent=2))
            print('CURRENT_PAIR_METRICS',summary,flush=True)
except KeyboardInterrupt:
    print('Interrupted by user',flush=True);failed=True
except Exception:
    import traceback;traceback.print_exc();failed=True
finally:
    from harvest_rl.lifecycle import close_simulator
    if a.collect_student:
        # RTX sensor destruction in env.close can hang and retain GPU memory.
        # This standalone worker has no async writers; data is already flushed.
        import sys
        sys.stdout.flush();sys.stderr.flush()
        if failed:
            close_simulator(app,None,True)
        else:
            app.close(wait_for_replicator=False,skip_cleanup=True)
    else:
        close_simulator(app,env,failed)
