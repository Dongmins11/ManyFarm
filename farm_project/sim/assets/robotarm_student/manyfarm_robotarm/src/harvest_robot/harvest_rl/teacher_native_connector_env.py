"""Same selected Teacher/control/gates, explicit alternative plant connector."""
import torch
from .teacher_friction_progress_env import TeacherFrictionProgressEnv
from .native_connector import NativeConnectors,ConnectorSpec


class TeacherNativeConnectorEnv(TeacherFrictionProgressEnv):
    def __init__(self,*args,connector_spec=None,**kwargs):
        self.connector_spec=(connector_spec or ConnectorSpec()).validate()
        super().__init__(*args,**kwargs)
        self.native_connectors=NativeConnectors(self,self.connector_spec)

    def _apply_action(self):
        before=self.attached.clone()
        super()._apply_action()
        if hasattr(self,'native_connectors'):self.native_connectors.disable_detached(before)

    def _reset_impl(self,ids):
        super()._reset_impl(ids)
        if hasattr(self,'native_connectors'):
            selected=self.robot._ALL_INDICES if ids is None else ids
            self.native_connectors.reset(selected)

    def _get_rewards(self):
        value=super()._get_rewards()
        if hasattr(self,'native_connectors'):
            # The inherited virtual-wrench flag is inapplicable to D6 drives.
            # Do not label the clipped spring estimate as a force measurement.
            fields=dict(stem_force_measured=torch.zeros_like(self.success),
                native_connector_load_is_estimate=torch.ones_like(self.success))
            self.last_diagnostics.update(fields)
            self.chain_snapshot.update({k:v.clone() for k,v in fields.items()})
        return value
