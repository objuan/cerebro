import time
from datetime import datetime, timedelta
import re
import logging
import asyncio
import inspect

logger = logging.getLogger()


SECONDS_TO_TIMEFRAME = {
    10 : "10s",
    30 : "30s",
    60 : "1m",
    300 : "5m",
    3600 : "1h",
}

TIMEFRAME_SECONDS = {
    "1s": 1,
    "5s": 5,
    "10s": 10,
    "15s": 15,
    "30s": 30,
    "1m": 60,
    "3m": 180,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "1d": 86400,
}
def candles_from_seconds(period_seconds: int, timeframe: str) -> int:
    tf_sec = TIMEFRAME_SECONDS[timeframe]
    return period_seconds // tf_sec

def seconds_from_candles(candles: int, timeframe: str) -> int:
    tf_sec = TIMEFRAME_SECONDS[timeframe]
    return candles * tf_sec

def timeframe_to_milliseconds(timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])

    if unit == 'm':
        return value * 60 * 1000
    elif unit == 'h':
        return value * 60 * 60 * 1000
    elif unit == 'd':
        return value * 24 * 60 * 60 * 1000
    else:
        raise ValueError(f"Timeframe non supportato: {timeframe}")

def numero_candele(minutes, timeframe: str) -> int:
    unit = timeframe[-1]
    value = int(timeframe[:-1])
    mult = 1
    if unit == 'm':
        mult= 1
    elif unit == 'h':
        mult= 60
    elif unit == 'd':
        mult= 60*60
   
    return int(minutes / mult)
    
def calculate_since(timeframe: str, N: int) -> int:
    now_ms = int(time.time() * 1000)
    tf_ms = timeframe_to_milliseconds(timeframe)
    since = now_ms - (tf_ms * N)
    return since

def ts_to_local_str(ts_ms: int) -> str:
    return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")

def datetime_to_unix(dt:datetime) -> int:
    return int(dt.timestamp())

def datetime_to_unix_ms(dt:datetime) -> int:
    return int(dt.timestamp())*1000

def prev_day_before_24(dt: datetime) -> datetime:
    #return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    return (
                (dt
                - timedelta(days=1))
                .replace(hour=23, minute=59, second=59, microsecond=0)
                
            )

def begin_day(dt: datetime) -> datetime:
    #return datetime.fromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")
    return dt.replace(hour=0, minute=0, second=1, microsecond=0)
                

TIME_MULTIPLIERS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400
}


DURATION_RE = re.compile(r"^(\d+)([smhd])$")


def duration_to_seconds(value):
    """
    Converte stringhe tipo '10s', '5m', '2h', '7d' in secondi.
    Ritorna il valore originale se non matcha.
    """
    if not isinstance(value, str):
        return value

    match = DURATION_RE.match(value)
    if not match:
        return value

    amount, unit = match.groups()
    return int(amount) * TIME_MULTIPLIERS[unit]


def convert_json(obj):
    """
    Scansione ricorsiva di dict e list.
    """
    if isinstance(obj, dict):
        return {k: convert_json(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [convert_json(v) for v in obj]

    return duration_to_seconds(obj)



#################################

class Scheduler:
    def __init__(self):
        self._tasks = []

    def schedule_in(self, delay_seconds, func, *args, **kwargs):
        """
        Esegue func dopo delay_seconds
        """
        run_at = time.time() + delay_seconds
        self._tasks.append((run_at, func, args, kwargs, False, 0))

    def schedule_at(self, when: datetime, func, *args, **kwargs):
        """
        Esegue func a una data/ora precisa
        """
        run_at = when.timestamp()
        self._tasks.append((run_at, func, args, kwargs, False, 0))

    def schedule_every(self, interval_seconds, func, *args, **kwargs):
        """
        Esegue func ogni interval_seconds
        """
        run_at = time.time() + interval_seconds
        self._tasks.append((run_at, func, args, kwargs, True, interval_seconds))

    def tick(self):
        """
        Da chiamare nel loop principale
        """
        now = time.time()

        for task in self._tasks[:]:
            run_at, func, args, kwargs, repeat, interval = task

            if now >= run_at:
                try:
                    func(*args, **kwargs)
                except:
                    logger.error("SCHEDULER ERROR", exc_info=True)

                if repeat:
                    # riprogramma
                    self._tasks.append(
                        (now + interval, func, args, kwargs, True, interval)
                    )

                self._tasks.remove(task)


class AsyncScheduler:
    def __init__(self):
        self._tasks = []

    def schedule_in(self, delay_seconds, coro, *args, **kwargs):
        run_at = time.monotonic() + delay_seconds
        self._tasks.append((run_at, coro, args, kwargs, False, 0))

    def schedule_at(self, when: datetime, coro, *args, **kwargs):
        run_at = when.timestamp()
        self._tasks.append(("wall", run_at, coro, args, kwargs, False, 0))

    def schedule_every(self, interval_seconds, coro, *args, **kwargs):
        run_at = time.monotonic() + interval_seconds
        self._tasks.append((run_at, coro, args, kwargs, True, interval_seconds))

    async def tick(self):
        now_mono = time.monotonic()
        now_wall = time.time()

        for task in self._tasks[:]:
            # distinzione monotonic / wall clock
            if task[0] == "wall":
                _, run_at, coro, args, kwargs, repeat, interval = task
                now = now_wall
            else:
                run_at, coro, args, kwargs, repeat, interval = task
                now = now_mono

            if now >= run_at:
                asyncio.create_task(coro(*args, **kwargs))

                self._tasks.remove(task)

                if repeat:
                    next_run = (
                        time.monotonic() + interval
                        if task[0] != "wall"
                        else time.time() + interval
                    )
                    self._tasks.append(
                        (next_run, coro, args, kwargs, True, interval)
                    )
import math

def sanitize(obj):
    if isinstance(obj, float) and math.isnan(obj):
        return None
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj


def floor_ts(ts_ms, sec):
    # ritorna in ms
    return (ts_ms // (sec*1000)) * (sec*1000)

def find_method(cls, method_name):
    if hasattr(cls, method_name):
        attr = getattr(cls, method_name)
        if callable(attr):
            return attr
    return None

def find_method_local(cls, method_name):
    return cls.__dict__.get(method_name)

class MyEvent:
    def __init__(self):
        self._handlers = []
        self.debug=False

    def __iadd__(self, handler):
        if handler not in self._handlers:
            self._handlers.append(handler)
        return self

    def __isub__(self, handler):
        if handler in self._handlers:
            self._handlers.remove(handler)
        return self

    '''
    def __call__(self, *args, **kwargs):
        for handler in self._handlers:
            handler(*args, **kwargs)
    '''

    def callSync(self, *args, **kwargs):
        
        for handler in self._handlers:
            
            handler(*args, **kwargs)

    async def __call__(self, *args, **kwargs):
        if self.debug:
            logger.info(f"CALL {self._handlers}")

        for handler in self._handlers:
            
            if inspect.iscoroutinefunction(handler):
                await handler(*args, **kwargs)
            else:
                handler(*args, **kwargs)

###########

def dict_to_paths(data, prefix=""):
    result = []

    for key, value in data.items():
        path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            result.extend(dict_to_paths(value, path))
        else:
            result.append({"path" : path , "value": value})

    return result

from datetime import datetime
import pytz

def convert_to_local(ts_str, tz_str='Europe/Rome'):
    # Parse il timestamp originale in UTC
    utc_dt = datetime.strptime(ts_str, '%Y-%m-%d %H:%M:%S')
    utc_dt = utc_dt.replace(tzinfo=pytz.utc)
    
    # Converti in timezone locale
    local_tz = pytz.timezone(tz_str)
    local_dt = utc_dt.astimezone(local_tz)
    
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')