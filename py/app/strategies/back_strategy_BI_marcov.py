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
from hmmlearn.hmm import GaussianHMM

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from order_book import *


 
class Markov:
    def __init__(self):
        self.matrices = {}

    #_hmm_states
    def build(self, df, n_states=3):

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

            ##
            X = X.dropna().to_numpy(dtype=float).reshape(-1, 1)

            # modello HMM
            model = GaussianHMM(
                n_components=n_states,
               # covariance_type="full",
                covariance_type="diag",
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

        result["next_state"] = result["state"].shift(-1)
        
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
        logger.info(f"\n{result}")

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


class BackStrategyIB_marcov(SmartStrategy):

    async def on_start(self):
        self.min_day_volume= self.params["min_day_volume"]
        self.max_back_steps= self.params["max_back_steps"]
        self.gain_2_perc= 2#self.params["gain_2_perc"]
        #self.trade_last_hh= self.params["trade_last_hh"]
        self.gain_perc = self.params["gain_perc"]
        self.drop_time_secs= self.params["drop_time_secs"]
        self.loss_by_trade=10

    def populate_indicators(self) :
        
        symbols = self.df_map[self.timeframe]["symbol"].unique().tolist()
        ts = self.df_map[self.timeframe].tail(1)["timestamp"].iloc[0]
        since=ts - 1000 * 60*60*24 * (20+140)
        logger.info(f" since {since} {type(symbols)}")

        h = self.client.history_data(symbols,"1d",since=since)

        #logger.info(f"\n{h}")
        #for symbol in symbols:
        #    logger.info(f"symbol { symbol}")

        self.markov = Markov()
        self.markov.build(h)
        #elf.markov.dump()

        ############

        max_1w= self.addIndicator(self.timeframe,MAX("max_1w","close", self.max_back_steps))

        #vol_day= self.addIndicator(self.timeframe,SUM("vol_day","quote_volume",1440))
        vol_day= self.addIndicator(self.timeframe,COPY("vol_day","quote_day_volume"))
        gain_day= self.addIndicator(self.timeframe,COPY("gain_day","day_gain"))
        sma_25= self.addIndicator(self.timeframe,SMA("sma_25","close",25))

        self.addIndicator(self.timeframe,TRADE_DATE("date"))
        vwap = self.addIndicator(self.timeframe, VWAPBands("vwap","vwap_up","vwap_down","vwap_perc","vwap_pos","close","quote_volume"))

        vwap_trend = self.addIndicator(self.timeframe, W_TREND("vwap_trend","vwap_trend_sign","vwap"))

        #vwap_perc = self.addIndicator(self.timeframe, DIFF_PERC("vwap_perc","vwap","vwap"))

        self.add_plot(vwap, "vwap","#a800a0", "main","vwap", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_up","#a800a0", "main","vwap_up", style="Dotted", lineWidth=1)
        self.add_plot(vwap, "vwap_down","#a800a0", "main","vwap_down", style="Dotted", lineWidth=1)
        
        self.add_plot(max_1w, "max_1w","#926B00FF", "main",style="Dotted", lineWidth=1)

        #self.add_plot(rsi, "rsi","#0318d3", "sub1", style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread","#0318d3","sub1", "vwap_trend" ,style="Solid", lineWidth=1)
        #self.add_plot(vwap_trend, "thread sign","#1bd303","sub1","vwap_trend_sign", style="Solid", lineWidth=1)
        
        self.add_plot(vwap, "vwap_perc","#1bd303","sub1","vwap_perc", style="Solid", lineWidth=1)
        self.add_plot(vwap, "vwap_pos","#d30337","sub1","vwap_pos", style="Solid", lineWidth=1)

        #self.add_plot(vol_day, "vol_day","#d30337","sub1","vol_day", style="Solid", lineWidth=1)
        self.add_plot(gain_day, "gain_day","#0311d3","sub1","gain_day", style="Solid", lineWidth=1)
        
      
     
        
    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):
        

        if not self.bootstrapMode:
            logger.info(f"\n{dataframe.tail(1)}") 

        if local_index < 2:
            return
        
        
        if not self.has_meta(symbol,"ai"): 
            self.set_meta(symbol,{"ai":{ "STATE": "WAITING","MAX_GAIN": 0}})
        ai = self.get_meta(symbol,"ai")   


        last = dataframe.iloc[local_index]
        vol_day = last["vol_day"]    
        gain_day = last["gain_day"] 
        sma_25= last["sma_25"] 
        if not self.hasCurrentTrade(symbol)  and ai["STATE"] == "WAITING" and (vol_day < self.min_day_volume):# or gain_day < 0
             return

        prev = dataframe.iloc[local_index-1]

        #markov = self.markov.get_chain_matrix(symbol,last["timestamp"] )
        #logger.info(f"symbol {symbol} {last['datetime']} \n{markov }")
        markov = self.markov.get_diagonal(symbol,last["timestamp"] )

        
        #logger.info(f"symbol {symbol} {last['datetime']} \n{markov }")

        max_1w = last["max_1w"]
        price = last["close"]
        vol = last["quote_volume"]
        vwap = last["vwap"]
        vwap_down = last["vwap_down"]
        
        trend =  last["vwap_trend"] * last["vwap_trend_sign"]
        last_trend =  prev["vwap_trend"] * prev["vwap_trend_sign"]
        
        vwap_perc = last["vwap_perc"]
        trend_pos =  last["vwap_pos"]

        gain_last = (price - prev["close"]) / prev["close"]*100
        gain_v = (vol - prev["quote_volume"]) / prev["quote_volume"]*100
        
        day = str(last["datetime"].date())
        if not "day_prob" in ai or ai["day_prob"] != day:
            prob=0
            if "BULL" in markov:
                prob = float(markov["BULL"] -  markov["BEAR"] if "BEAR" in markov else 0) 
            ai["day_prob"]  = prob
            
        await self.add_marker(symbol,"SPOT", f"{prob:.1f}",f"{prob:.1f}","#FF0000") 
       

        if not self.hasCurrentTrade(symbol):
                     
            if ai["day_prob"] > 0.5 and gain_day>0 and trend_pos > 50 and price > last["open"]:
                
                if not "day" in ai or ai["day"] != day:
                    ai["day"] = day
                    await self.add_marker(symbol,"SPOT", f"{day}",f"{day}","#FF0000") 
       
                    q = self.get_quantity( self.loss_by_trade, price    )
                    await self.buy( symbol, int(last["timestamp"]),price,  q, f"BUY {prob:.1f}" )

        elif self.hasCurrentTrade(symbol):

            gain,ts,pnl = self.buyGain(symbol, last["close"]) 
            self.set_current_price(symbol, last["close"])   
            dt = int(dataframe.iloc[local_index]["timestamp"])
            time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   

            if gain <-1:
                await  self.sell(symbol, dt, last["close"], f"SL"  )
                ai["STATE"] = "WAITING"  

            if last["low"] < prev["low"]:
                await  self.sell(symbol, dt, last["close"], f"TP"  )
                ai["STATE"] = "WAITING"  
