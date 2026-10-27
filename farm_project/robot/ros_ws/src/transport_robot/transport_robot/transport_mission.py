"""목적지와 작업 기록 소유. 전체 작업을 순차 실행하는 루프를 두지 않는다."""
from pathlib import Path
from dataclasses import asdict
import json
import shutil
from datetime import datetime, timezone
from .mission_types import Request, Outcome, utc


class TransportMission:
    def __init__(self, journal: Path) -> None:
        self._journal = journal
        self.records = json.loads(journal.read_text()) if journal.exists() else {}
        self._contact = journal.with_suffix('.contact.json')
        self.recovery_required = self._contact.exists() or any(v['status'] == 'RUNNING' for v in self.records.values())

    def _save(self) -> None:
        self._journal.parent.mkdir(parents=True,exist_ok=True)
        temporary = self._journal.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.records,ensure_ascii=False,indent=2,allow_nan=False))
        temporary.replace(self._journal)

    def begin(self, request: Request) -> None:
        if request.task_id in self.records:
            raise ValueError('이미 등록된 task_id입니다. 재실행하지 않습니다.')
        self.records[request.task_id] = dict(request=asdict(request),status='RUNNING',timestamp=utc())
        self._save()

    def record_stage(self, request, stage, detail='') -> None:
        record = self.records[request.task_id]
        event = dict(stage=stage, detail=detail, timestamp=utc())
        record.setdefault('stages', []).append(event)
        record.update(stage=stage, stage_detail=detail, stage_timestamp=event['timestamp'])
        self._save()

    def finish(self, request: Request, outcome: Outcome) -> None:
        self.records[request.task_id].update(status=outcome.result_code,outcome=asdict(outcome),timestamp=utc())
        self._save()

    def set_contact(self, uncertain: bool) -> None:
        """접근 시작부터 이격 완료까지 재시작 자동 재개를 금지한다."""
        if uncertain:
            self._contact.parent.mkdir(parents=True,exist_ok=True)
            self._contact.write_text('{"contact_or_clearance_unverified": true}')
        else:
            self._contact.unlink(missing_ok=True)

    def operator_reset(self) -> None:
        """호출자가 유휴·정지·운영자 확인을 검사한 후에만 호출한다."""
        backup=self._journal.parent/'recovery_backups'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        backup.mkdir(parents=True)
        if self._journal.exists():shutil.copy2(self._journal,backup/self._journal.name)
        if self._contact.exists():shutil.copy2(self._contact,backup/self._contact.name)
        for record in self.records.values():
            if record['status']=='RUNNING':
                record.update(status='FAILED',timestamp=utc(),outcome=dict(result_code='FAILED',
                    error_code='MANUAL_RECOVERY',error_message='운영자가 도킹 구역 밖 재배치 확인',arrived=False,docked=False))
        self._save()
        self.set_contact(False)
        self.recovery_required=False
