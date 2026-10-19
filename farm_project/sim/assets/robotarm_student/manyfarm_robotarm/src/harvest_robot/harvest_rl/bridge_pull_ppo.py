"""Selective arm5 PPO; frozen grasp/bridge transitions never enter the loss.

Uses the installed RSL-RL policy/storage/optimizer and checkpoint format.
Normalization is frozen; all real finite-budget timeouts are terminal.
"""
import torch
from rsl_rl.algorithms import PPO
from .bridge_pull_training import masked_returns


class BridgePullPPO(PPO):
    def bind(self,env):
        if self.policy.is_recurrent or self.rnd or self.symmetry or self.is_multi_gpu:
            raise ValueError('Continuous masked pull supports plain single-GPU ActorCritic only')
        self.env=env
        self.active=torch.zeros(self.storage.rewards.shape[:2],dtype=torch.bool,device=self.device)

    def act(self,obs):
        self.before=self.env.pull_active.clone()
        actions=super().act(obs)
        self.transition.actions_log_prob=self.policy.distribution.log_prob(actions)[:,:5].sum(-1).detach()
        self.transition.values=torch.where(self.before[:,None],self.transition.values,0.)
        return actions

    def process_env_step(self,obs,rewards,dones,extras):
        # Inactive actions were replaced by the frozen grasp policy. They are
        # not on-policy samples from this learner and must never affect PPO.
        self.active[self.storage.step]=self.before
        self.transition.rewards=torch.where(self.before,rewards,0.).clone()
        self.transition.dones=dones
        self.storage.add_transitions(self.transition)
        self.transition.clear();self.policy.reset(dones)
        # Preserve all parent normalization buffers. No HOME observations or
        # reset observations from terminal transitions contaminate them.

    def compute_returns(self,obs):
        last=self.policy.evaluate(obs).detach()
        returns,advantages=masked_returns(self.storage.rewards,self.storage.values,self.storage.dones,
            self.active,last,self.env.pull_active,self.gamma,self.lam)
        self.storage.returns.copy_(returns);self.storage.advantages.copy_(advantages)

    def update(self):
        ids=self.active.flatten().nonzero().flatten()
        result=dict(value=0.,surrogate=0.,entropy=0.,active_samples=int(len(ids)),optimizer_steps=0.)
        if not len(ids):
            self.storage.clear();self.active.zero_();return result
        storage=self.storage
        obs=storage.observations.flatten(0,1)
        tensors=[v.flatten(0,1) for v in [storage.actions,storage.values,storage.advantages,storage.returns,
                  storage.actions_log_prob,storage.mu,storage.sigma]]
        updates=0
        for _ in range(self.num_learning_epochs):
            shuffled=ids[torch.randperm(len(ids),device=self.device)]
            for batch in shuffled.tensor_split(min(self.num_mini_batches,len(ids))):
                actions,old_values,advantages,returns,old_log,old_mu,old_sigma=[v[batch] for v in tensors]
                self.policy.act(obs[batch]);values=self.policy.evaluate(obs[batch])
                log=self.policy.distribution.log_prob(actions)[:,:5].sum(-1)
                mean=self.policy.action_mean[:,:5];sigma=self.policy.action_std[:,:5]
                entropy=self.policy.distribution.entropy()[:,:5].sum(-1)
                if self.desired_kl is not None and self.schedule=='adaptive':
                    with torch.no_grad():
                        kl=(torch.log(sigma/old_sigma[:,:5]+1e-5)+(old_sigma[:,:5].square()+
                            (old_mu[:,:5]-mean).square())/(2*sigma.square())-.5).sum(-1).mean()
                        if kl>2*self.desired_kl:self.learning_rate=max(1e-5,self.learning_rate/1.5)
                        elif 0<kl<.5*self.desired_kl:self.learning_rate=min(1e-3,self.learning_rate*1.5)
                        for group in self.optimizer.param_groups:group['lr']=self.learning_rate
                ratio=torch.exp(log-old_log.squeeze(-1))
                advantage=advantages.squeeze(-1)
                surrogate=torch.maximum(-advantage*ratio,-advantage*ratio.clamp(1-self.clip_param,1+self.clip_param)).mean()
                if self.use_clipped_value_loss:
                    clipped=old_values+(values-old_values).clamp(-self.clip_param,self.clip_param)
                    value_loss=torch.maximum((values-returns).square(),(clipped-returns).square()).mean()
                else:value_loss=(values-returns).square().mean()
                loss=surrogate+self.value_loss_coef*value_loss-self.entropy_coef*entropy.mean()
                if not torch.isfinite(loss):raise FloatingPointError('Nonfinite selective PPO loss')
                self.optimizer.zero_grad();loss.backward()
                torch.nn.utils.clip_grad_norm_(self.policy.parameters(),self.max_grad_norm)
                self.optimizer.step();updates+=1
                result['value']+=float(value_loss.detach());result['surrogate']+=float(surrogate.detach())
                result['entropy']+=float(entropy.mean().detach())
        for key in ['value','surrogate','entropy']:result[key]/=updates
        result['optimizer_steps']=updates
        self.storage.clear();self.active.zero_()
        return result
