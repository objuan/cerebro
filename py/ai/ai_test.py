# ================================
# 1) Install Libraries
# ================================
import subprocess
import sys

def install(package):
    subprocess.check_call([sys.executable, "-m", "pip", "install", package])

packages = ["yfinance", "hmmlearn", "matplotlib", "pandas", "numpy", "scikit-learn"]

for p in packages:
    try:
        __import__(p)
    except ImportError:
        install(p)

# ================================
# Imports
# ================================
import yfinance as yf
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from hmmlearn.hmm import GaussianHMM


# ================================
# 2) Get Data
# ================================
'''
df = yf.download(
    "BTC-USD",
    period="730d",
    interval="1h"
)
'''
df = yf.download(
    "BTC-USD",
    start="2026-01-01",
    end="2026-02-17",
    interval="1h"
)

# Handle possible MultiIndex columns
if isinstance(df.columns, pd.MultiIndex):
    df.columns = df.columns.get_level_values(0)

# Ensure only required columns exist
df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

# ================================
# 3) Feature Engineering
# ================================
data = df.copy()

data['Returns'] = data['Close'].pct_change()
data['Range'] = (data['High'] - data['Low']) / data['Close']
data['Vol_Change'] = data['Volume'].pct_change()

# Clean data
data.replace([np.inf, -np.inf], np.nan, inplace=True)
data.dropna(inplace=True)
#data.replace([np.inf, -np.inf], np.nan, inplace=True)
#data.dropna(inplace=True)

# ================================
# 4) Train Model
# ================================
X = data[['Returns', 'Range', 'Vol_Change']].values

model = GaussianHMM(
    n_components=7,
    covariance_type="full",
    n_iter=1000,
    random_state=42
)

model.fit(X)

states = model.predict(X)
data['State'] = states

# ================================
# 5) Analyze
# ================================
summary = data.groupby('State').agg(
    Mean_Return=('Returns', 'mean'),
    Volatility=('Returns', 'std'),
    Count=('Returns', 'count')
)

summary = summary.sort_values(by="Mean_Return", ascending=False)

print("\nState Summary:")
print(summary)

# ================================
# 6) Visualize
# ================================
last = data.tail(500)

plt.figure(figsize=(14,7))

plt.plot(last.index, last['Close'], label="BTC Close", alpha=0.6)

scatter = plt.scatter(
    last.index,
    last['Close'],
    c=last['State'],
    cmap='tab10',
    s=30
)

plt.title("Bitcoin Price Regimes (HMM)")
plt.xlabel("Time")
plt.ylabel("Price")

legend1 = plt.legend(*scatter.legend_elements(), title="State")
plt.gca().add_artist(legend1)

plt.legend()
plt.tight_layout()
plt.savefig("btc_regimes.png", dpi=300)
try:
    plt.show()
except:
    plt.savefig("btc_regimes.png", dpi=300)
    print("Backend non interattivo: grafico salvato su file.")