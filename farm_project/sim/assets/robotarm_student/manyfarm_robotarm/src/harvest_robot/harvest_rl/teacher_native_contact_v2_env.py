"""Same reward/controls/floor; train-only sampling removes nested old weights."""
from .teacher_native_contact_env import TeacherNativeContactEnv
from .native_contact_refine_v2 import training_pool


class TeacherNativeContactV2Env(TeacherNativeContactEnv):
    def __init__(self, *args, bias_training=False, **kwargs):
        if bias_training and kwargs.get('domain_split') != 'train':
            raise ValueError('No held-out priority sampling')
        super().__init__(*args, bias_training=False, **kwargs)
        if bias_training:
            mixed, hard = training_pool(self.domain_pools[3], self.domain_bank_ids, self.points,
                train_end=self.train_bank_end_exclusive)
            self.domain_pools[3] = mixed
            self.priority_bank_ids = self.domain_bank_ids[hard].cpu().tolist()
