"""Actor updates exclude overwritten proposals; critic/GAE retain real outcomes."""
import torch
from .bridge_pull_ppo import BridgePullPPO
from .native_control_mask import actor_advantages


class NativeControlPPO(BridgePullPPO):
    def bind(self, env):
        super().bind(env)
        if self.schedule != 'fixed' or self.entropy_coef != 0:
            raise ValueError('This version preserves conservative fixed-lr/entropy0')
        self.actor_active = torch.zeros_like(self.active)

    def process_env_step(self, obs, rewards, dones, extras):
        index = self.storage.step
        super().process_env_step(obs, rewards, dones, extras)
        self.actor_active[index] = self.before & self.env.native_actor_controlled

    def compute_returns(self, obs):
        super().compute_returns(obs)
        if (self.actor_active & ~self.active).any():
            raise ValueError('Actor sample outside real native trajectory')
        self.storage.advantages.copy_(actor_advantages(
            self.storage.returns, self.storage.values, self.actor_active))

    def update(self):
        ids = self.active.flatten().nonzero().flatten()
        policy_mask = self.actor_active.flatten()
        result = dict(value=0., surrogate=0., entropy=0., active_samples=int(len(ids)),
            actor_samples=int(policy_mask.sum()), controller_only_samples=int(len(ids)-policy_mask.sum()),
            optimizer_steps=0., actor_optimizer_steps=0.)
        if not len(ids):
            self.storage.clear(); self.active.zero_(); self.actor_active.zero_()
            return result
        storage = self.storage; obs = storage.observations.flatten(0, 1)
        actions, old_values, advantages, returns, old_log = [v.flatten(0, 1) for v in
            (storage.actions, storage.values, storage.advantages, storage.returns, storage.actions_log_prob)]
        updates = actor_updates = 0
        for _ in range(self.num_learning_epochs):
            shuffled = ids[torch.randperm(len(ids), device=self.device)]
            for batch in shuffled.tensor_split(min(self.num_mini_batches, len(ids))):
                values = self.policy.evaluate(obs[batch])
                if self.use_clipped_value_loss:
                    clipped = old_values[batch]+(values-old_values[batch]).clamp(-self.clip_param, self.clip_param)
                    value_loss = torch.maximum((values-returns[batch]).square(),
                        (clipped-returns[batch]).square()).mean()
                else:
                    value_loss = (values-returns[batch]).square().mean()
                actor_ids = batch[policy_mask[batch]]
                if len(actor_ids):
                    self.policy.act(obs[actor_ids])
                    log = self.policy.distribution.log_prob(actions[actor_ids])[:, :5].sum(-1)
                    ratio = torch.exp(log-old_log[actor_ids].squeeze(-1))
                    advantage = advantages[actor_ids].squeeze(-1)
                    surrogate = torch.maximum(-advantage*ratio,
                        -advantage*ratio.clamp(1-self.clip_param, 1+self.clip_param)).mean()
                    actor_updates += 1
                else:
                    # No actor graph/zero-gradient momentum step on batches
                    # where every proposal was replaced by a controller.
                    surrogate = values.new_zeros(())
                loss = surrogate+self.value_loss_coef*value_loss
                if not torch.isfinite(loss):
                    raise FloatingPointError('Nonfinite action-aware PPO loss')
                self.optimizer.zero_grad(set_to_none=True); loss.backward()
                torch.nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
                self.optimizer.step(); updates += 1
                result['value'] += float(value_loss.detach())
                result['surrogate'] += float(surrogate.detach())
        result['value'] /= updates
        result['surrogate'] /= updates
        result['optimizer_steps'] = updates; result['actor_optimizer_steps'] = actor_updates
        self.storage.clear(); self.active.zero_(); self.actor_active.zero_()
        return result
