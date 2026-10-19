"""GPU ring buffer of completed episodes; independent of cumulative rates."""
import torch

class RecentEpisodes:
    def __init__(self,capacity,device):
        self.capacity=capacity;self.count=0;self.cursor=0
        self.values=torch.zeros(capacity,3,device=device)

    def add(self,success,failure,replay):
        n=len(success)
        if not n:return
        rows=torch.stack((success,failure,replay),-1).float()[-self.capacity:]
        n=len(rows)
        ids=(torch.arange(n,device=rows.device)+self.cursor)%self.capacity
        self.values[ids]=rows
        self.cursor=(self.cursor+n)%self.capacity
        self.count=min(self.capacity,self.count+n)

    def metrics(self):
        v=self.values[:self.count]
        # Empty windows produce zero counts/rates, not NaN.
        success=v[:,0];failure=v[:,1];replay=v[:,2];primary=1-replay
        return {'Recent/episodes':self.values.new_tensor(self.count),
                'Recent/success_rate':success.sum()/max(1,self.count),
                'Recent/failure_rate':failure.sum()/max(1,self.count),
                'Recent/timeout_rate':((1-success)*(1-failure)).sum()/max(1,self.count),
                'Recent/primary_episodes':primary.sum(),
                'Recent/primary_success_rate':(success*primary).sum()/primary.sum().clamp_min(1),
                'Recent/replay_episodes':replay.sum(),
                'Recent/replay_success_rate':(success*replay).sum()/replay.sum().clamp_min(1)}
