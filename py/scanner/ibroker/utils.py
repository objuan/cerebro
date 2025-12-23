import time
from datetime import datetime

class Scheduler:
    def __init__(self):
        self.tasks = []

    def every(self, seconds, func):
        self.tasks.append({
            "func": func,
            "interval": seconds,
            "last_run": 0
        })

    def run(self):
        while True:
            now = time.time()
            for task in self.tasks:
                if now - task["last_run"] >= task["interval"]:
                    task["func"]()
                    task["last_run"] = now
            time.sleep(0.05)



def parse_field(field, min_val, max_val):
    if field == "*":
        return set(range(min_val, max_val + 1))

    values = set()
    for part in field.split(","):
        if "-" in part:
            start, end = map(int, part.split("-"))
            values.update(range(start, end + 1))
        else:
            values.add(int(part))
    return values


class CronJob:
    def __init__(self, cron_expr, func):
        self.func = func
        fields = cron_expr.split()
        if len(fields) != 5:
            raise ValueError("Espressione cron non valida")

        self.minutes  = parse_field(fields[0], 0, 59)
        self.hours    = parse_field(fields[1], 0, 23)
        self.days     = parse_field(fields[2], 1, 31)
        self.months   = parse_field(fields[3], 1, 12)
        self.weekdays = parse_field(fields[4], 0, 6)

    def match(self, dt):
        return (
            dt.minute in self.minutes and
            dt.hour in self.hours and
            dt.day in self.days and
            dt.month in self.months and
            dt.weekday() in self.weekdays
        )


class CronScheduler:
    def __init__(self):
        self.jobs = []

    def add(self, cron_expr, func):
        self.jobs.append(CronJob(cron_expr, func))

    def run(self):
        print("Cron scheduler avviato")
        last_minute = None

        while True:
            now = datetime.now()

            # evita doppia esecuzione nello stesso minuto
            if now.minute != last_minute:
                for job in self.jobs:
                    if job.match(now):
                        job.func()
                last_minute = now.minute

            time.sleep(1)

def df_delta(df_old, df_new, key="conidex"):
    m = df_old.merge(df_new, on=key, how="outer",
                     suffixes=("_old", "_new"), indicator=True)

    return {
        "added":   m[m["_merge"] == "right_only"],
        "removed": m[m["_merge"] == "left_only"],
        "changed": m[
            (m["_merge"] == "both") &
            (m.filter(like="_old") != m.filter(like="_new")).any(axis=1)
        ]
    }

def remove_dicts(data, **criteria):
    return [
        d for d in data
        if not all(d.get(k) == v for k, v in criteria.items())
    ]