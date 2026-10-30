unalias mf_launch mf_init_station mf_zenoh mf_dummy_zenoh mf_status 2>/dev/null || true
# 별칭 정의만 한다. source 시 기동/초기위치/환경 덮어쓰기 없음.
alias mf_env='source /home/vic/Downloads/handoff_completion_fix/environment.bash'
alias laun='bash /home/vic/vmany/main/farm_project/robot/tools/terminal/run.bash launch'
alias vinit='bash /home/vic/Downloads/manyfarm_terminal_20261024/run.bash init'
alias zen='bash /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/run.bash zenoh'
alias dzen='bash /home/vic/vmany-runtime-staging/jetson_reply_20261027_1741/run.bash dummy-zenoh'
alias vstat='bash /home/vic/Downloads/manyfarm_terminal_20261024/run.bash status'

# 14번 시험 초기위치
source /home/vic/vmany/main/farm_project/robot/tools/terminal/dinit_alias.bash
