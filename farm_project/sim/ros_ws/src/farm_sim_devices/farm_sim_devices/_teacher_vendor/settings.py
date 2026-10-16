"""60Hz r2 원본 계산에서 추출. 재생성: sim/tools/import_teacher60.py."""

from dataclasses import asdict, dataclass

from pathlib import Path

ROOT = Path(__file__).resolve().parent

URDF = ROOT / "src/smartfarm_description/urdf/harvest_robot.urdf"

CACHE = ROOT / "outputs/harvest_rl/assets"

JOINTS = ("shoulder_pan", "shoulder_lift", "elbow_flex", "wrist_flex", "wrist_roll", "gripper")

@dataclass

class TaskSettings:
    contract_version: int = 2
    reward_version: int = 7
    attachment_version: int = 2  # 1: legacy OR, 2: spring force AND extension, 3: native PhysX joint, 4: directional compliant stem
    entry_first_grasp: bool = False  # opt-in entry geometry gate and pre-entry contact cost
    entry_capture_shaping: bool = False  # unconfirmed capture: penalize one-sided pushing after entry too
    pull_recovery_shaping: bool = False  # terminal-corrected post-grasp distance potential
    pull_squeeze_rearm: bool = False  # rearm confirmed contact after explicit closing resumes
    pull_squeeze_ramp: bool = False  # opt-in gradual post-grasp preload; actuator cap unchanged
    pull_direction_shaping: bool = False  # penalize lateral/negative-axis pulling after confirmed grasp
    pull_progress_reward: bool = False  # bounded qualified tensile progress, no stationary payout
    stage_transfer: bool = False  # stable grasp progress and attached regrasp reference
    lock_attachment: bool = False  # native grasp/hold curriculum only
    native_detach_recovery: bool = True  # bounded provisional recovery for native harvest only
    captured_break_grace: bool = False  # confirm retained physical break even after grasp confirmation
    post_detach_hold_guard: bool = False  # staged early retention: suppress opening while captured
    detached_capture_orientation: bool = False  # separate post-break capture from approach orientation
    spring_grasp_grace: bool = False  # opt-in early target detach verification
    native_grasp_grace: bool = True  # confirm continuous centered hold after an early native break
    grasp_orientation: str = "free"  # horizontal: initial grasp across fruit sides
    grasp_angle_tolerance: float = 0.436332313  # radians, 25 degrees
    grasp_orientation_weight: float = 4.0
    grasp_version: int = 2  # 1: legacy contact-only, 2: centered bilateral contact
    grasp_center_tolerance: float = 0.010  # m, fruit body centre to calibrated grasp TCP
    pregrasp_fraction: float = 0.0  # training-only close/hold curriculum; evaluation must use HOME
    transport_replay_fraction: float = 0.0
    transport_start_min: float = 0.0
    transport_start_max: float = 0.0  # zero disables distance filtering
    start_bank: str = ""  # physical predecessor-success snapshots, train/eval separated
    task: str = "grasp"
    target_mode: str = "nearest"  # nearest sequence, random single assignment, external API
    sequence: bool = False
    random_colors: bool = True  # active only in sequential scenes
    timeout_scope: str = "fruit"
    background: str = "single"
    num_fruits: int = 1
    # Fixed docking pose. Origin is front edge, right arm centreline, mount height.
    region_origin: tuple = (0.30, -0.19, 0.713)
    region_min: tuple = (0.20, -0.175, -0.10)
    region_max: tuple = (0.30, 0.175, 0.35)
    diameter: float = 0.070
    length: float = 0.075  # whole asset including stem, until body-only dimensions are measured
    mass: float = 0.035  # plastic model: provisional, NOT fresh fruit mass
    spring_k: float = 120.0
    spring_d: float = 1.5
    angular_k: float = 0.015
    angular_d: float = 0.002
    stem_response_version: int = 3  # v4 only: 1 original explicit spring, 2 stable mesh-contact model, 3 fresh wrench frames + sustained overload, 4 implicit spring+damper
    stem_vertical_stiffness: float = 80.0  # response2 provisional hanger weight support, N/m
    stem_max_extension: float = 0.08  # v4 response2 connector travel limit, m; provisional
    tension_axis: tuple = (-1.0, 0.0, 0.0)  # v4 outward pull axis in simulation world frame
    tension_hold_s: float = 0.12  # v4 continuous tensile overload
    lateral_stiffness_ratio: float = 0.25  # v4 transverse stiffness / spring_k
    break_force: float = 2.5
    break_distance: float = 0.030  # legacy attachment v1 only
    break_hold_s: float = 0.04
    valid_pull_distance: float = 0.012  # v2: minimum extension; v1: minimum -X displacement
    grip_hold_s: float = 0.25
    place_hold_s: float = 0.6
    transport_linear_pose_stop: bool = False
    release_stop_s: float = 0.3
    release_speed: float = 0.05
    box_contact_tolerance: float = 0.003
    shape_placement: bool = False  # independent of controlled-release reward version
    box_bottom_contact_tolerance: float = 0.003
    legacy_box_bottom_margin: float = 0.0  # v1–6 centre-height placement test; metres
    contact_threshold: float = 0.08
    max_contact_force: float = 25.0
    action_speed: float = 0.8  # rad/s; five revolute joints
    gripper_speed: float = 1.2
    gripper_effort: float = 0.50  # simulation starting cap; must be measured before hardware use
    gripper_stiffness: float = 8.0  # Nm/rad; historical implicit drive
    gripper_damping: float = 0.3  # Nm s/rad
    grip_friction: float = 1.0  # rubber pad/plastic pair assumption; measure on hardware
    dynamic_friction: float = 1.0
    restitution: float = 0.02
    fruit_collision_mode: str = "legacy"  # preserve checkpoints; body_hull_v1 is an explicit contact experiment
    contact_stiffness: float = 0.0  # 0: historical rigid contacts; positive enables implicit compliant grip contact
    contact_damping: float = 0.0  # N s/m; provisional unless measured
    gripper_max_error: float = 0.04  # anti-windup closing error, rad
    contact_substeps: int = 1  # preserves control period while refining contact integration
    contact_solver_refine: bool = False  # explicit solver convergence comparison
    release_intent_mode: bool = False  # validate stop when opening starts, then monitor hand
    release_measured_open: bool = False  # evaluation opt-in: unload closing target once release is approved
    transport_adaptive_grip: bool = False  # saved transport controller contract
    transport_pose_stop: bool = False  # saved control-interval orientation stop criterion
    detached_grip_hold: bool = False  # opt-in position target retention after detachment
    gripper_hold_error: float = 0.035  # bounded compliant squeeze after confirmation
    hold_force: float = 0.6  # external +X test load after confirmed grasp, N
    hold_s: float = 1.0
    detached_hold_s: float = 0.5
    max_slip: float = 0.012
    physics_dt: float = 1.0 / 240.0
    decimation: int = 12  # 20 Hz policy
    render_hz: int = 0  # 0: historical control-rate rendering; explicit frequency divides actual physics Hz
    episode_s: float = 20.0
    tree_position: tuple = (0.85, -0.19, 0.0)
    tree_scale: tuple = (0.75, 0.75, 1.35)
    box_min: tuple = (0.305, -0.095, 0.506)
    box_max: tuple = (0.495, 0.095, 0.701)
    curriculum: float = 0.0  # 0: reachable targets near reset TCP, 1: complete candidate bank
    workspace_split: str = "train"  # disjoint deterministic target seed sets
    seed: int = 42

    def validate(self):
        if (self.attachment_version != 4 or self.contact_substeps != 1
                or abs(self.physics_dt-1/60)>1e-12 or self.decimation != 3):
            raise ValueError('60Hz / 20Hz / response6만 지원합니다.')
        import math
        if self.entry_capture_shaping and not self.entry_first_grasp:
            raise ValueError('Capture shaping requires entry-first grasp')
        if self.release_measured_open and not self.release_intent_mode:
            raise ValueError('Measured opening requires approved release-intent mode')
        if not math.isfinite(self.gripper_stiffness) or not math.isfinite(self.gripper_damping) or self.gripper_stiffness <= 0 or self.gripper_damping < 0:
            raise ValueError('Invalid gripper drive gains')
        if any(not math.isfinite(v) or v<0 for v in (self.contact_stiffness,self.contact_damping)) or (self.contact_stiffness==0 and self.contact_damping!=0):
            raise ValueError('Invalid contact compliance')
        if self.fruit_collision_mode not in ('legacy', 'body_hull_v1'):
            raise ValueError('Invalid fruit collision mode')
        if self.fruit_collision_mode != 'legacy' and (self.attachment_version != 4 or self.stem_response_version < 2):
            raise ValueError('Body hull requires the mesh-contact attachment4 asset')
        if type(self.contact_substeps) is not int or self.contact_substeps not in (1,2,4):
            raise ValueError("contact_substeps must be 1,2,4")
        if type(self.render_hz) is not int or self.render_hz < 0:
            raise ValueError('Invalid rendering frequency')
        from .simulation_clock import render_interval
        render_interval(self.physics_dt/self.contact_substeps,self.decimation*self.contact_substeps,self.render_hz)
        if self.target_mode not in ("nearest", "random", "external"):
            raise ValueError("Invalid target_mode")
        if self.target_mode != "nearest" and not self.sequence and not (
                self.target_mode == "external" and self.num_fruits in (1, 2) and self.task == "harvest") and not (
                self.target_mode == "random" and self.num_fruits == 1 and self.task in ("transport", "place") and self.start_bank):
            raise ValueError("Assigned targets require a sequence scene or one/two-fruit external harvest")
        if self.reward_version not in (1, 2, 3, 4, 5, 6, 7, 8) or not 0 <= self.pregrasp_fraction <= 1:
            raise ValueError("Invalid reward version or pregrasp fraction")
        if self.timeout_scope not in ("fruit", "episode"):
            raise ValueError("timeout_scope must be fruit or episode")
        if self.episode_s <= 0:
            raise ValueError("episode_s must be positive")
        if self.background not in ("single", "grove"):
            raise ValueError("background must be single or grove")
        if self.sequence and (self.num_fruits < 3 or (self.task == "harvest" and self.reward_version < 7)):
            raise ValueError("Sequence scene requires >=3 fruits; harvest requires reward >=7")
        if self.sequence and self.task != "harvest" and self.target_mode != "random":
            raise ValueError("Multi-fruit grasp/hold/pull requires random single target")
        if self.lock_attachment and (self.attachment_version != 3 or self.task not in ("grasp", "hold")):
            raise ValueError("lock_attachment supports native grasp/hold only")
        if self.reward_version == 8 and self.task not in ("harvest","transport","place"):
            raise ValueError("Reward8 requires harvest/transport/place")
        import math
        if self.grasp_orientation not in ("free", "horizontal"):
            raise ValueError("Unknown grasp orientation")
        if not 0 < self.grasp_angle_tolerance < math.pi/2 or not math.isfinite(self.grasp_orientation_weight) or self.grasp_orientation_weight < 0:
            raise ValueError("Invalid grasp orientation tolerance/weight")
        if self.grasp_orientation == "horizontal" and (self.grasp_version != 2 or self.reward_version < 3):
            raise ValueError("Horizontal grasp requires centered grasp2 and reward>=3")
        if self.grasp_version not in (1, 2):
            raise ValueError("Invalid grasp version")
        if not 0 < self.grasp_center_tolerance < self.diameter * .5:
            raise ValueError("Grasp centre tolerance must be positive and smaller than fruit radius")
        if self.reward_version in (3, 4, 5, 6, 7, 8) and self.grasp_version != 2:
            raise ValueError("Reward v3/v4/v5/v6/v7 requires centered grasp v2")
        if self.pregrasp_fraction and (self.num_fruits != 1 or self.task != "grasp"):
            raise ValueError("Pregrasp reset curriculum supports single-fruit grasp only")
        if self.workspace_split == "eval" and self.pregrasp_fraction:
            raise ValueError("Evaluation must start from HOME; set pregrasp_fraction=0")
        if self.task not in ("grasp", "hold", "pull", "harvest", "transport", "place"):
            raise ValueError("task must be grasp, hold, pull or harvest")
        if self.contract_version != 2:
            raise ValueError("Incompatible task contract; use a v2 checkpoint")
        if not 0 <= self.transport_replay_fraction < 1:
            raise ValueError("Replay fraction must be in [0,1)")
        if self.transport_replay_fraction and (self.task != "transport" or self.transport_start_min <= .03 or not self.transport_start_max):
            raise ValueError("Replay needs transport range with minimum above 3cm")
        if not (0 <= self.transport_start_min and 0 <= self.transport_start_max):
            raise ValueError("Transport start distances must be nonnegative")
        if self.transport_start_max and (self.task != "transport" or self.transport_start_min >= self.transport_start_max):
            raise ValueError("Start distance range requires transport and min < max")
        if self.transport_start_min and not self.transport_start_max:
            raise ValueError("Start distance minimum requires maximum")
        if self.task in ("transport","place"):
            if not self.start_bank or self.attachment_version not in (3,4) or self.reward_version != 8 or not self.stage_transfer or self.target_mode != "random":
                raise ValueError("Transport/place requires certified bank, native3, reward8, stage-transfer and random target")
        elif self.start_bank:
            raise ValueError("Start banks are only for transport/place; full harvest starts from HOME")
        if self.mass <= 0 or (self.task == "hold" and self.hold_force <= 0):
            raise ValueError("Positive fruit mass and hold-stage load are required")
        if not 0 < self.gripper_hold_error <= self.gripper_max_error:
            raise ValueError("Hold squeeze must be positive and within anti-windup error cap")
        if not 0 <= self.dynamic_friction <= self.grip_friction or not 0 <= self.restitution <= 1:
            raise ValueError("Invalid contact material")
        if min(self.hold_s, self.detached_hold_s, self.max_slip, self.gripper_max_error) <= 0 or self.hold_force < 0:
            raise ValueError("Invalid hold/control settings")
        if not 1 <= self.num_fruits <= 8:
            raise ValueError("num_fruits must be between 1 and 8")
        if not 0.025 <= self.diameter <= 0.080 or not 0.035 <= self.length <= 0.100:
            raise ValueError("Fruit dimensions outside tested configuration range")
        if not 0 <= self.curriculum <= 1:
            raise ValueError("curriculum must be in [0,1]")
        if self.workspace_split not in ("train", "eval"):
            raise ValueError("workspace_split must be train or eval")
        if self.attachment_version not in (1, 2, 3, 4) or min(self.spring_k, self.break_hold_s, self.valid_pull_distance, self.break_distance) <= 0 or self.spring_d < 0:
            raise ValueError("Invalid attachment parameters")
        if self.stem_response_version != 6 or not 0.02 <= self.stem_max_extension <= 0.15:
            raise ValueError("Invalid stem response version or travel limit")
        if self.attachment_version == 4:
            import math
            if not math.isfinite(self.stem_vertical_stiffness) or self.stem_vertical_stiffness <= 0:
                raise ValueError("Vertical connector stiffness must be finite and positive")
            if (len(self.tension_axis) != 3 or not all(math.isfinite(x) for x in self.tension_axis)
                    or sum(x*x for x in self.tension_axis) < 1e-12):
                raise ValueError("v4 tension_axis must be a finite nonzero 3-vector")
            if not math.isfinite(self.tension_hold_s) or self.tension_hold_s < self.physics_dt:
                raise ValueError("v4 tension_hold_s must be at least one physics step")
            if not 0 < self.lateral_stiffness_ratio <= 1:
                raise ValueError("v4 lateral_stiffness_ratio must be in (0,1]")
        if min(self.release_stop_s, self.release_speed) <= 0 or not 0 <= self.box_contact_tolerance <= .005:
            raise ValueError("Invalid controlled release settings")
        if not 0 <= self.legacy_box_bottom_margin <= .010:
            raise ValueError("legacy_box_bottom_margin must be within 0–10mm")
        if not 0 <= self.box_bottom_contact_tolerance <= .010:
            raise ValueError("box_bottom_contact_tolerance must be within 0–10mm")
        if self.break_force <= self.mass * 9.81:
            raise ValueError("Attachment must support gravity")
        return self

    def as_dict(self):
        return asdict(self)
