"""수신/검사 시각을 구분해 기존 -0.1~0.5초 조건을 그대로 설명한다."""
def timing(key: str, stamp_ns: int, receive_ns: int, check_ns: int, receipt_age_s: float) -> dict:
    age=(check_ns-stamp_ns)/1e9
    reason=('receipt_expired' if receipt_age_s>.5 else
            'future_stamp' if age<-.1 else 'stamp_expired' if age>.5 else '')
    return dict(key=key,stamp_ns=stamp_ns,receive_ns=receive_ns,check_ns=check_ns,
                age_at_receive_s=(receive_ns-stamp_ns)/1e9,measurement_age_s=age,
                receipt_age_s=receipt_age_s,reason=reason)


def summarize(rows: list) -> dict:
    result={}
    for key in sorted({row['key'] for row in rows}):
        selected=[row for row in rows if row['key']==key]
        result[key]=dict(checks=len(selected),distinct_stamps=len({r['stamp_ns'] for r in selected}),
                        min_age_s=min(r['measurement_age_s'] for r in selected),
                        max_age_s=max(r['measurement_age_s'] for r in selected),
                        max_age_at_receive_s=max(r['age_at_receive_s'] for r in selected),
                        max_receipt_age_s=max(r['receipt_age_s'] for r in selected),
                        failures=[r for r in selected if r['reason']][:10])
    return result
