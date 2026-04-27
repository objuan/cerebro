
import numpy as np

def backtest(preds, target, threshold=0.6):
    signals = preds > threshold
    
    returns = signals * target  # semplificato
    
    accuracy = (signals == target).mean()
    hit_rate = returns.sum() / (signals.sum() + 1e-6)
    
    return {
        "accuracy": accuracy,
        "hit_rate": hit_rate,
        "trades": signals.sum()
    }