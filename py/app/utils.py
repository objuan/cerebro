import time

TIMEFRAME_SECONDS = {
    "1s": 1,
    "5s": 5,
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

def calculate_since(timeframe: str, N: int) -> int:
    now_ms = int(time.time() * 1000)
    tf_ms = timeframe_to_milliseconds(timeframe)
    since = now_ms - (tf_ms * N)
    return since