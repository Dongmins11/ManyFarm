"""공통 Navigator만 호출하며 로봇 기종·목적지 상수를 소유하지 않는다."""
from typing import Any
import math
from .mission_state import MissionState


class NavigationMoveState(MissionState):
    name = 'NAVIGATION_MOVE'
    def enter(self) -> None:
        self.controller.feedback('RETURNING' if self.controller.request.kind == 'return' else ('MOVING_STARTED' if self.controller.request.kind in ('pickup','unload') else 'MOVING'))
        self.controller.run_async(self, self._move, self._arrived)

    def _move(self) -> Any:
        nav = self.controller.navigator
        nav.preflight_navigation()
        self.controller.check()
        request = self.controller.request
        harvest=getattr(self.controller,'harvest_approach',None)
        if harvest is not None and harvest.applies(request):return harvest.move(request)
        approach=getattr(self.controller,'sorter_approach',None)
        if approach is not None and approach.applies(request):return approach.move(request)
        yaw=request.yaw
        if request.entry_stage:
            plan=nav.plan(request.xy)
            # Arrive along the incoming path, stop; precision then rotates at A.
            for a,b in reversed(list(zip(plan.points,plan.points[1:]))):
                if math.dist(a,b)>1e-6:
                    yaw=math.atan2(b[1]-a[1],b[0]-a[0]);break
        return nav.navigate(request.xy,yaw)

    def _arrived(self, result: Any) -> None:
        self.controller.arrived()
