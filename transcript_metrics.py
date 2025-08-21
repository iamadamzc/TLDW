from collections import Counter
from threading import Lock
from typing import Dict

_success = Counter()   # keys: 'yt_api', 'timedtext', 'youtubei', 'asr'
_fail = Counter()      # keys: 'timedtext', 'youtubei', 'asr', 'none'
_lock = Lock()

def inc_success(source: str):
    with _lock:
        _success[source] += 1

def inc_fail(stage: str):
    with _lock:
        _fail[stage] += 1

def snapshot() -> Dict[str, Dict[str, int]]:
    with _lock:
        return {
            "success_by_source": dict(_success),
            "fail_by_stage": dict(_fail),
            "total_success": sum(_success.values()),
            "total_fail": sum(_fail.values()),
        }
