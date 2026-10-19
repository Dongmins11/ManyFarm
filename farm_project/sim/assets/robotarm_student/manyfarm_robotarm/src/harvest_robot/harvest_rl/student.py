"""Bounded replay DAgger: expert labels at states visited by the student."""
import json
import torch
from torch.utils.tensorboard import SummaryWriter
from .policy import VisionStudent, History


def train_student(env, wrapped, expert, args, output):
    model = VisionStudent().to(env.device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4)
    history = History(*env.student_observations())
    obs = wrapped.get_observations()
    # Host replay is bounded, unlike an ever-growing image dataset on GPU.
    capacity = max(256, min(2048, 64*env.num_envs))
    images = torch.empty(capacity,*history.rgb.shape[1:],dtype=torch.uint8)
    proprio = torch.empty(capacity,3,18)
    labels = torch.empty(capacity,6)
    size, cursor = 0, 0
    writer = SummaryWriter(str(output))
    try:
        for iteration in range(args.iterations):
            beta = max(.05, 1.0-iteration/max(1,args.iterations*.7))
            for _ in range(16):
                with torch.no_grad():
                    target = expert(obs).clamp(-1,1)
                    predicted = model(history.rgb,history.proprio)
                    # Label before stepping; avoids image/action time misalignment.
                    for i in range(env.num_envs):
                        images[cursor].copy_(history.rgb[i].cpu())
                        proprio[cursor].copy_(history.proprio[i].cpu())
                        labels[cursor].copy_(target[i].cpu())
                        cursor = (cursor+1)%capacity
                        size = min(size+1,capacity)
                    choose_teacher = torch.rand(env.num_envs,1,device=env.device) < beta
                    action = torch.where(choose_teacher,target,predicted)
                    obs, _, done, _ = wrapped.step(action)
                    history.update(*env.student_observations(),done.bool())
            model.train()
            for _ in range(8):
                ids = torch.randint(size,(min(64,size),))
                rgb = images[ids].to(env.device)
                # Mild brightness augmentation; camera calibration remains provisional.
                rgb = (rgb.float()*torch.empty(len(ids),1,1,1,1,device=env.device).uniform_(.85,1.15)).clamp(0,255)
                pred = model(rgb,proprio[ids].to(env.device))
                loss = torch.nn.functional.mse_loss(pred,labels[ids].to(env.device))
                optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(model.parameters(),1.0)
                optimizer.step()
            model.eval()
            writer.add_scalar("student/action_mse",loss.item(),iteration)
            writer.add_scalar("student/expert_mix",beta,iteration)
            if iteration % 50 == 0:
                torch.save({"student":model.state_dict()},output/f"student_{iteration}.pt")
                print("STUDENT",iteration,"loss",loss.item(),"expert_mix",beta,flush=True)
            if args.show_camera:
                from run import show_camera
                show_camera(env)
        torch.save({"student":model.state_dict()},output/"student_final.pt")
        (output/"metrics.json").write_text(json.dumps(env.episode_metrics,indent=2))
    finally:
        writer.close()
