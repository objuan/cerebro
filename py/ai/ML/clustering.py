from sklearn.cluster import KMeans
import numpy as np

def fit_clusters(X, n_clusters=20):
    model = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = model.fit_predict(X)
    return model, clusters

def compute_cluster_prob(clusters, target):
    import pandas as pd
    df = pd.DataFrame({'cluster': clusters, 'target': target})
    probs = df.groupby('cluster')['target'].mean()
    return probs


def run_clustering(X, n_clusters=15):
    X = np.array(X)
    
    model = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = model.fit_predict(X)
    
    return model, clusters