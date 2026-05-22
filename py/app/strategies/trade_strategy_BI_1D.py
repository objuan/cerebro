from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from balance import Balance, PositionTrade
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
from zoneinfo import ZoneInfo
from market import Market
from collections import defaultdict
import math

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from order_book import *
from hmmlearn.hmm import GaussianHMM

 

class Markov:
    def __init__(self):
        self.matrices = {}

    def build(self, df):

        df = df.copy()
        n = 20
        # features per ogni symbol
        df["return"] = (
            df.groupby("symbol")["close"]
            .pct_change()
        )

        hmm_states=[]
        for symbol, group in df.groupby("symbol"):

            n = 20
            g = group.copy()

            # somma dei ritorni precedenti
            rolling_gain = (
                        g["return"]
                        .rolling(window=n)
                        .sum()
            )
                    
            g["HMM_STATE"] = 0
            g["state"] = "STAND"

            g.loc[rolling_gain >= 0.05, "HMM_STATE"] = 2
            g.loc[rolling_gain <= -0.05, "HMM_STATE"] = 1

            g.loc[rolling_gain >= 0.05, "state"] = "BULL"
            g.loc[rolling_gain <= -0.05, "state"] = "BEAR"

            hmm_states.append(g)

            #logger.info(f"{symbol} \n{g.tail(20)}")

        #logger.info(f"\n{hmm_states}")
        
        # merge finale
        result = pd.concat(hmm_states)

        result["next_state"] = (
            result.groupby("symbol")["state"]
            .shift(-1)
        )
      
        
        #logger.info(f"\n{result.tail(60)}")
        
        self.df= result

    #_hmm_states
    def build_full(self, df, n_states=3):

        # ordinamento temporale
        #df = self.df.sort_values(
        #    ["symbol", "timestamp"]
        #).copy()
        df = df.copy()

        # features per ogni symbol
        df["return"] = (
            df.groupby("symbol")["close"]
            .pct_change()
        )

        # volatilità rolling
        df["volatility"] = (
            df.groupby("symbol")["return"]
            .transform(
                lambda x: x.rolling(10).std()
            )
        )

        # momentum
        df["momentum"] = (
            df.groupby("symbol")["close"]
            .transform(
                lambda x: x / x.shift(5) - 1
            )
        )

        # volume normalizzato
        if "quote_volume" in df.columns:

            df["volume_z"] = (
                df.groupby("symbol")["quote_volume"]
                .transform(
                    lambda x:
                    (
                        x - x.rolling(20).mean()
                    ) / x.rolling(20).std()
                )
            )

        #logger.info(f"\n{df}")
        hmm_states = []

        # HMM separato per ogni symbol
        for symbol, g in df.groupby("symbol"):

            g = g.copy()

            # features HMM
            features = [
                "return",
                "volatility",
                "momentum"
            ]

            if "volume_z" in g.columns:
                features.append("volume_z")

            # rimuove NaN
            g = g.dropna(subset=features)

            if len(g) < 30:
                continue

            X = g[features].values

            #logger.info(f"{symbol} {X}")
            ##
            #X = X.dropna().to_numpy(dtype=float).reshape(-1, 1)

            # modello HMM
            model = GaussianHMM(
                n_components=n_states,
                covariance_type="full",
               # covariance_type="diag",
                n_iter=200,
                random_state=42
            )

            model.fit(X)

            # hidden states
            hidden_states = model.predict(X)

            g["HMM_STATE"] = hidden_states

            # mapping automatico:
            # stato con rendimento medio più alto -> BULL
            # più basso -> BEAR
            # restante -> STAND

            means = {}

            for s in range(n_states):

                means[s] = (
                    g.loc[
                        g["HMM_STATE"] == s,
                        "return"
                    ].mean()
                )

            ordered = sorted(
                means.items(),
                key=lambda x: x[1]
            )

            bear_state = ordered[0][0]
            bull_state = ordered[-1][0]

            state_map = {}

            for s in range(n_states):

                if s == bull_state:
                    state_map[s] = "BULL"

                elif s == bear_state:
                    state_map[s] = "BEAR"

                else:
                    state_map[s] = "STAND"

            g["state"] = (
                g["HMM_STATE"]
                .map(state_map)
            )

            #logger.info(f"\n{g.tail(60)}")
            

            hmm_states.append(g)

        #logger.info(f"\n{hmm_states}")
        
        # merge finale
        result = pd.concat(hmm_states)

        result["next_state"] = (
            result.groupby("symbol")["state"]
            .shift(-1)
        )

        self.df= result

        '''
        # aggiorna dataset
        self.df.loc[
            result.index,
            "MARKOV"
        ] = result["MARKOV"]

        self.df.loc[
            result.index,
            "HMM_STATE"
        ] = result["HMM_STATE"]
        '''
        #logger.info(f"\n{result}")

       # return self.df
        
        return None

    def build22(self, df):
        for symbol, group in df.groupby("symbol"):

            n = 20
            m = 5

            #df = df.sort_values(["symbol", "date"])

            # media mobile per symbol
            df["ma"] = (
                df.groupby("symbol")["close"]
                .transform(lambda x: x.rolling(n).mean())
            )

            # std rolling per symbol
            df["std"] = (
                df.groupby("symbol")["close"]
                .transform(lambda x: x.rolling(n).std())
            )

            # z-score
            df["z"] = (
                (df["close"] - df["ma"]) /
                df["std"]
            )

            # slope della media
            df["slope"] = (
                df.groupby("symbol")["ma"]
                .transform(lambda x: x / x.shift(m) - 1)
            )

            # classificazione stati
            conditions = [
                (df["z"] > 0.5) & (df["slope"] > 0),
                (df["z"] < -0.5) & (df["slope"] < 0)
            ]

            choices = ["BULL", "BEAR"]
        
            df["state"] = np.select(
                conditions,
                choices,
                default="STAND"
            )


            df["next_state"] = df["state"].shift(-1)

        logger.info(f"\n{df.tail(60)}")
        self.df=df

    def get_state(self,symbol, current_ts):
        dt = datetime.utcfromtimestamp(current_ts/1000)
        prev = dt - timedelta(days=1)
        prev_ts = int(prev.timestamp())*1000

        #print(prev_ts)
        find = self.df[self.df["timestamp"] < prev_ts].tail(1)
        if not find.empty:
            return find.iloc[0]["HMM_STATE"]
        else:
            return 0

    def get_chain_matrix(self,symbol, current_ts):

        dt = datetime.utcfromtimestamp(current_ts/1000)
        prev = dt - timedelta(days=1)
        prev_ts = int(prev.timestamp())*1000

        g = self.df[
            (self.df["symbol"] == symbol) &
            (self.df["timestamp"] <= prev_ts)
        ].copy().tail(20)

        #logger.info(f"==> {current_ts}  {dt} \n{g.tail(1)}")

        counts = pd.crosstab(
                g["state"],
                g["next_state"]
        )

        matrix = counts.div(
                counts.sum(axis=1),
                axis=0
        )

        return matrix
    
    
    def get_diagonal(self,symbol, current_ts):
        matrix = self.get_chain_matrix(  symbol,current_ts )

         # diagonale
        diagonal = {}

        for state in matrix.index:

            if state in matrix.columns:

                diagonal[state] = matrix.loc[
                    state,
                    state
                ]
                
        return diagonal

    def build1(self, df):
        for symbol, group in df.groupby("symbol"):

            group = group.copy()

            # rendimento
            group["return"] = group["close"].pct_change()

            # stati
            group["state"] = group["return"].apply(
                lambda x: "UP" if x > 0 else "DOWN"
            )

            # stato successivo
            group["next_state"] = group["state"].shift(-1)

            # matrice conteggi
            counts = pd.crosstab(
                group["state"],
                group["next_state"]
            )

            # matrice probabilità
            matrix = counts.div(
                counts.sum(axis=1),
                axis=0
            )

            self.matrices[symbol] = matrix

    def dump(self):
        for symbol in self.matrices.keys():
            logger.info(f"symbol {symbol} {self.matrices[symbol] }")


class MarkovIndicator(Indicator):
    def __init__(self, target,target_prob, markov):
        super().__init__([target,target_prob])
        self.target=target
        self.target_prob=target_prob
        self.markov=markov

    def compute_fast(self, symbol, dataframe: pd.DataFrame, symbol_idx, from_local_index):
        # 1. Riferimenti agli array numpy per le performance ⚡
        dest = dataframe[self.target].to_numpy()
        dest_prob = dataframe[self.target_prob].to_numpy()
        timestamp = dataframe["timestamp"].to_numpy()

        # 2. Definiamo il range di calcolo
        # Partiamo da from_local_index per non ricalcolare il passato
        start = max(0, from_local_index)
        
     
        #logger.info(f"{new_dates}")
        # 4. Assegnazione incrementale
        for i, i_idx in enumerate(range(start, len(symbol_idx))):
            idx = symbol_idx[i_idx]
            #print(timestamp[idx])
            v = self.markov.get_state(symbol,timestamp[idx])
            #print(v)
            if v == 1:
                dest[idx] = -1
            elif v == 2:
                dest[idx] = 1
            else:
                dest[idx] = 0

            
            d_markov = self.markov.get_diagonal(symbol,timestamp[idx])

            

            prob=0
            if "BULL" in d_markov :
                #logger.info(d_markov)
                prob = float(d_markov["BULL"] -  d_markov["BEAR"] if "BEAR" in d_markov else 0) 
            elif "BEAR" in d_markov :
                #logger.info(d_markov)
                prob = float(-d_markov["BEAR"]  )

            dest_prob[idx] = prob
            


class BackStrategyIB_1D(SmartStrategy):

    async def on_start(self):
        pass

    def populate_indicators(self) :

        symbols = self.df_map[self.timeframe]["symbol"].unique().tolist()
        ts = self.df_map[self.timeframe].tail(1)["timestamp"].iloc[0]
        since=ts - 1000 * 60*60*24 * (20+140)
        logger.info(f" since {since} {type(symbols)}")

        h = self.client.history_data(symbols,"1d",since=since)

        logger.info(f"\n{h}")
        self.markov = Markov()
        self.markov.build(h)

        max_1w= self.addIndicator(self.timeframe,MAX("max_1w","close", 7))

        m = self.addIndicator(self.timeframe, MarkovIndicator("markov", "markov_prob", self.markov))


        self.add_plot(m, "markov","#0311d3","sub1","markov", style="Solid", lineWidth=1)
        self.add_plot(m, "markov_prob","#6b0020","sub1","markov_prob", style="Solid", lineWidth=1)

        
        #self.add_plot(max_1w, "max_1w","#610000FF", "main",style="Dotted", lineWidth=1)

        pass
     
        
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        

        if not self.bootstrapMode:
            logger.info(f"\n{dataframe.tail(1)}") 

        last = dataframe.iloc[local_index]

        if symbol == "EDEN ":
            logger.info(f"\n{last}")