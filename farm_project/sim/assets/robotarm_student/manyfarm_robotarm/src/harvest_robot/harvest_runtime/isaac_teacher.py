"""Existing HarvestEnv/teacher binding; import-safe without Isaac/torch.

Caller must create the scene ONCE and supply a real Motion implementation.
There is deliberately no default joint interpolation/teleport return controller.
CurrentPairEnv already remaps the selected target to the v6 observation slots.
"""
from .executor import Executor, Target, Feedback
from .adapters import PolicyBackend, Observation


class IsaacTeacher:
    def __init__(self, env, wrapped, inference, target_slots, reset_policy_state):
        if env.num_envs != 1 or env.settings.target_mode != 'external' or env.settings.sequence:
            raise ValueError('Require one external, non-sequence environment')
        if env.settings.task != 'harvest':
            raise ValueError('Executor completion requires full harvest, not grasp/pull')
        if not target_slots or len(set(target_slots.values())) != len(target_slots):
            raise ValueError('Require unique persistent IDs mapped to unique slots')
        if any(type(v) is not int or not 0 <= v < env.settings.num_fruits for v in target_slots.values()):
            raise ValueError('Invalid fruit slot')
        self.env,self.wrapped,self.inference = env,wrapped,inference
        self.slots = dict(target_slots)
        self.reset_policy_state = reset_policy_state
        self.request = None

    def start_target(self, request, target):
        self.reset_policy_state()
        self.obs = self.env.assign_target(self.slots[request.target_id])
        self.request = request

    def act(self, observation):
        import torch
        with torch.inference_mode():
            return self.inference(observation.payload)

    def end_target(self):
        self.reset_policy_state()
        if self.request and self.env.assignment_status == 'SUCCEEDED':
            # Keep harvested bodies dynamic; exclude only verified completed fruit
            # from future non-target-detachment failure checks.
            self.env.collected[0,self.slots[self.request.target_id]] = True
        self.request = None

    def observe_target(self, target_id, now):
        slot = self.slots[target_id]
        position = self.env.fruits[slot].data.root_link_pos_w[0]-self.env.scene.env_origins[0]
        valid = bool(self.env.attached[0,slot] & ~self.env.collected[0,slot] & self.env.ripe[0,slot])
        return Target(target_id,'simulation_world',tuple(position.cpu().tolist()),now,valid)

    def read(self, request, now):
        return Observation(request.request_id,request.target_id,'simulation_world',now,self.obs)

    def completion(self, request, now):
        # Keep prior deposits part of the task even after changing target slot.
        if bool(self.env.collected.any()):
            import torch
            from .deposit_guard import still_in_box
            for slot,fruit in enumerate(self.env.fruits):
                if bool(self.env.collected[0,slot]):
                    if not still_in_box(fruit,self.env):
                        return Feedback(request.request_id,request.target_id,'FAILED',f'previous_deposit_{slot}_lost')
        status = self.env.assignment_status
        if status == 'RUNNING':
            return Feedback(request.request_id,request.target_id,'RUNNING')
        if status == 'SUCCEEDED':
            return Feedback(request.request_id,request.target_id,'SUCCEEDED','simulator_harvest_placement_confirmed')
        return Feedback(request.request_id,request.target_id,'TIMED_OUT' if status=='TIMED_OUT' else 'FAILED','simulator_'+status)

    def validate(self, action, observation):
        import torch
        if action.shape != (1,6) or not bool(torch.isfinite(action).all()):
            raise ValueError('Teacher must output finite (1,6) actions')
        # Existing PPO can emit unbounded values; wrapper's documented clip=1
        # is preserved explicitly in apply rather than changing the policy.

    def apply(self, action, now):
        import torch
        with torch.inference_mode():
            self.obs,_,_,_=self.wrapped.step(action.clamp(-1.,1.))


def make_executor(env, wrapped, inference, motion, target_slots, *, reset_policy_state):
    """No scene reset here. motion must safely advance physics outside task steps.

    reset_policy_state is required: no-op for stateless v6 MLP, explicit recurrent
    reset for other policies. The adapter is teacher-only: never use its truth
    observations as a student or real Vision provider.
    """
    teacher=IsaacTeacher(env,wrapped,inference,target_slots,reset_policy_state)
    backend=PolicyBackend(teacher,motion,read_observation=teacher.read,
        completion=teacher.completion,validate_action=teacher.validate,apply_action=teacher.apply)
    return Executor(backend,teacher.observe_target,'simulation_world'),teacher
