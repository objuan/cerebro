from data_loader import load_data
from features import *
from clustering import run_clustering
from model import *
from datetime import datetime, timedelta
from sklearn.decomposition import PCA
from evaluate import evaluate_ranking

import numpy as np
import pandas as pd



dt_start= datetime.now() - timedelta(days=10)
timestamp_ms = int(dt_start.timestamp() * 1000)

# 1. load
df = load_data( timeframe="1m", timestamp=timestamp_ms)

#print(df)
#exit(0)


df = compute_vwap(df)

print("1")

# 2. features
df = compute_features(df)
print("2")
df = clean_features(df)
print("3")

# open window
df_open = get_open_window(df, minutes=30)

print(df_open)
#exit(0)

# dataset
print("build_ranking_dataset")
df_rank = build_ranking_dataset(df_open, df)


features_cols = [c for c in df_rank.columns if c not in ['symbol','date','target']]

'''
split_date = df_rank['date'].quantile(0.7)

train = df_rank[df_rank['date'] <= split_date]
test  = df_rank[df_rank['date'] > split_date]
'''

split_idx = int(len(df_rank) * 0.7)

train = df_rank.iloc[:split_idx]
test  = df_rank.iloc[split_idx:]

X_train = train[features_cols]
y_train = train['target']

X_test = test[features_cols]
y_test = test['target']

print("Total samples:", len(df_rank))
print("X_train shape:", X_train.shape)
print("X_test shape:", X_test.shape)
print("Train rows:", len(train))
print("Test rows:", len(test))

model = train_rank_model(X_train, y_train)

print(model)

test['pred'] = model.predict(X_test)

results = evaluate_ranking(test, top_k=3)

print(results)


exit(0)

# 3. target giornaliero
daily_target = build_daily_target(df)

#print(daily_target)
#exit(0)

# 4. open window
df_open = get_open_window(df, minutes=30)

#print(df_open)
#exit(0)

# 5. pattern
X, keys = build_daily_patterns(df_open)

#print(X)
      
# 6. allinea target
y = np.array([daily_target.loc[k] for k in keys])


# 7. split
split = int(len(X) * 0.7)

pca = PCA(n_components=10)


X_train, X_test = X[:split], X[split:]
y_train, y_test = y[:split], y[split:]

###############
pca = PCA(n_components=10)
X_train = pca.fit_transform(X_train)
X_test = pca.transform(X_test)

X_train = np.array(X_train)
X_test = np.array(X_test)

lengths = [len(x) for x in X]
print("Min len:", min(lengths))
print("Max len:", max(lengths))

print("Baseline:", y_test.mean())

# 8. clustering
cluster_model, clusters = run_clustering(X_train)

#print(cluster_model)
#exit(0)

cluster_probs = pd.DataFrame({
    'cluster': clusters,
    'target': y_train
}).groupby('cluster')['target'].mean()

# 9. ML
model = train_model(X_train, y_train)

ml_probs = model.predict_proba(X_test)[:,1]

# 10. cluster prediction
test_clusters = cluster_model.predict(X_test)
cluster_pred = np.array([cluster_probs.get(c, 0.5) for c in test_clusters])

# 11. combinazione
final_prob = 0.6 * ml_probs + 0.4 * cluster_pred

# 12. valutazione semplice
accuracy = ((final_prob > 0.5) == y_test).mean()

print("Accuracy:", accuracy)