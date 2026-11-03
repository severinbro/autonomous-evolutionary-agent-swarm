import json, sys
from datetime import datetime
from croniter import croniter
exprs = [
    "0 0 13 * 5", "0 0 1,15 * mon", "0 9 * * mon-fri", "0 0 * jan,jul sun", "30 2 29 2 *",
    "0 0 31 * *", "*/15 9-17 * * 1-5", "5-55/10 * * * *", "0 */6 * * *", "0 0 * * 0",
    "0 0 * * 7", "0 12 1 */3 *", "59 23 31 12 *", "0 0 * * 5-7", "0 8-10/2 * * *",
    "15 14 1 * *", "0 22 * * 1-5", "23 0-20/2 * * *", "0 0 1 1 *", "0 4 8-14 * *",
    "0 0 29 2 1", "0 0 * * SAT,sun", "1,2,3 * * * *", "0 0 15 FEB-APR *", "45 23 * * 6",
    "@yearly", "@annually", "@monthly", "@weekly", "@daily", "@midnight", "@hourly",
    "0 0 1-7 * 1", "*/7 * * * *", "0 3 * 11 thu",
]
starts = [datetime(2027, 2, 26, 23, 59), datetime(2028, 2, 28, 12, 0), datetime(2026, 12, 31, 23, 58),
          datetime(2027, 3, 13, 0, 0), datetime(2026, 11, 13, 0, 0)]
out = {"next_fires": [], "invalid": []}
for e in exprs:
    for s in starts:
        it = croniter(e, s)
        out["next_fires"].append([e, s.isoformat(), [it.get_next(datetime).isoformat() for _ in range(5)]])
for bad in ["60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "* * * * 8", "*/0 * * * *",
            "* * * *", "a * * * *", "* * 32 * *", "1-61 * * * *", "* * * foo *", ""]:
    try:
        croniter(bad, starts[0]).get_next(datetime)
        print("croniter accepts", repr(bad), file=sys.stderr)
    except Exception:
        out["invalid"].append(bad)
json.dump(out, sys.stdout)
