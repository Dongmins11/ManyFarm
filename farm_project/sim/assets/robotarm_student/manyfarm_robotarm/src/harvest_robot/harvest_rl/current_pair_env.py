"""Current-URDF one-assignment evaluation. One/two fruits; no sequential collection."""
import numpy as np
import torch
from .env import HarvestEnv
from .current_pair_geometry import selected_teacher_observation,select_layout


class CurrentPairEnv(HarvestEnv):
    def __init__(self,*args,layout_points,layout_pairs,requested_target,layout_seed,distractor_points=None,distractor_spacing=.18,**kwargs):
        self.distractor_points=distractor_points
        self.distractor_spacing=distractor_spacing
        self.layout_points=layout_points
        self.layout_pairs=layout_pairs
        self.requested_target=requested_target
        self.layout_seed=layout_seed
        self.layout_episode=0
        self.last_layout=None
        super().__init__(*args,**kwargs)

    def _reset_impl(self,env_ids):
        super()._reset_impl(env_ids)
        if not len(env_ids):return
        if self.num_envs!=1:raise ValueError('Explicit assignment evaluation requires one env')
        positions,slot=select_layout(self.layout_points,self.layout_pairs,self.layout_seed,self.layout_episode,self.requested_target)
        if self.distractor_points is not None:
            from .current_pair_geometry import add_matched_distractor
            positions=add_matched_distractor(positions,slot,self.distractor_points,self.distractor_spacing,self.layout_seed,self.layout_episode)
        self.layout_episode+=1
        self.logical_target=slot
        self.assignment_slot=slot if len(self.fruits)==2 else 0
        self.last_layout=dict(episode=self.layout_episode-1,target_color=('Red','Yellow')[slot],
            target_slot=self.assignment_slot,pair_positions_policy_m=positions.tolist(),
            center_distance_m=float(np.linalg.norm(positions[0]-positions[1])))
        actual=positions if len(self.fruits)==2 else positions[slot:slot+1]
        for i,fruit in enumerate(self.fruits):
            state=fruit.data.default_root_state.clone()
            state[:,:3]=torch.as_tensor(actual[i],device=self.device,dtype=torch.float32)+self.scene.env_origins
            state[:,3:7]=torch.tensor([1.,0.,0.,0.],device=self.device)
            state[:,7:]=0
            fruit.write_root_state_to_sim(state)
            fruit.reset()
            self.anchors[:,i]=state[:,:3]+self.fruit_tips[i]
            self.rest_quat[:,i]=state[:,3:7]
        # Independent, matched target attachment threshold for both scene sizes.
        rng=np.random.default_rng(np.random.SeedSequence([self.layout_seed,self.layout_episode-1,99]))
        thresholds=self.settings.break_force*rng.uniform(.8,1.2,2)
        self.threshold[:]=torch.as_tensor(thresholds if len(self.fruits)==2 else thresholds[slot:slot+1],device=self.device)
        self.target_index.fill_(self.assignment_slot)
        self._draw_stems()

    def _get_observations(self):
        obs=super()._get_observations()
        obs['policy']=selected_teacher_observation(obs['policy'])
        return obs
