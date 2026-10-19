"""Deterministic contract demo only: NO robot/simulator/policy learning."""
from .executor import Executor, Request, Target, Feedback
from .adapters import Observation, PolicyBackend


class DemoPolicy:
    def start_target(self, request, target):
        self.history = []

    def act(self, observation):
        self.history.append(observation.stamp_s)
        return .1

    def end_target(self):
        self.history = []


class DemoWorld:
    def __init__(self, fail_target=None):
        self.deposited = set()
        self.commands = {}
        self.fail_target = fail_target
        self.stopped = False
        self.active = None

    def observe(self, target_id, now):
        return Target(target_id, 'arm_base', (.2,0,.1), now)

    def read(self, request, now):
        self.active = request.target_id
        return Observation(request.request_id,request.target_id,'arm_base',now,{'demo':True})

    def apply(self, action, now):
        self.commands[self.active] = self.commands.get(self.active,0)+1

    def validate(self, action, observation):
        if not isinstance(action,(float,int)) or not -1 <= action <= 1:
            raise ValueError('Invalid demo action')

    def completion(self, request, now):
        count = self.commands.get(request.target_id,0)
        status = 'RUNNING'
        reason = ''
        if count >= 3:
            if request.target_id == self.fail_target:
                status, reason = 'FAILED', 'demo_contact_failure'
            else:
                self.deposited.add(request.target_id)
                status, reason = 'SUCCEEDED', 'demo_deposit_sensor'
        return Feedback(request.request_id,request.target_id,status,reason)

    def start_return(self, request, now):
        self.return_at = now+.2

    def tick_return(self, request, now):
        done = now >= self.return_at
        return Feedback(request.request_id,request.target_id,'SUCCEEDED' if done else 'RUNNING',
                        'demo_safe_return' if done else '')

    def stop(self, reason, now):
        self.stopped = True

    def tick_stop(self, now):
        return self.stopped


def build_demo(fail_target=None):
    world = DemoWorld(fail_target)
    backend = PolicyBackend(DemoPolicy(),world,read_observation=world.read,
        completion=world.completion,validate_action=world.validate,apply_action=world.apply)
    executor = Executor(backend,world.observe,'arm_base')
    return executor,world
