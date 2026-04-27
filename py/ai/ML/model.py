# src/model.py

from lightgbm import LGBMClassifier,LGBMRegressor


def predict(model, X):
    return model.predict_proba(X)[:,1]


def train_model(X, y):
    model = LGBMClassifier(n_estimators=200)
    '''
    model1 = LGBMClassifier(
        n_estimators=100,
        max_depth=4,
        min_child_samples=10,
        learning_rate=0.05
    )
    '''
    
    model.fit(X, y)
    return model

def train_rank_model(X, y):
    model = LGBMRegressor(
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05
    )
    model.fit(X, y)
    return model

