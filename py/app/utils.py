import time

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