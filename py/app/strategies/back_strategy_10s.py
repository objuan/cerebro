from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from telegram import send_telegram_message
from strategies.strategy_utils import StrategyUtils
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
from company_loaders import *
from collections import deque
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager
from order_book import *
#from strategy.order_strategy import *


#################

class BackStrategy10s(SmartStrategy):

    async def on_start(self):

        self.sub_timeframe = "1m"
        self.min_gain = 20
        self.min_volume = 100000

        self.buffers = {}   # {symbol: DataFrame}
        self.last_candle_key = {}  # {symbol: timestamp}
        self.local_df = {}   # {symbol: DataFrame finale}
        
        self.localIndicators = []  
        self.localPlots=[]

        self.max_gain={}
        self.last_trade={}
        pass

    async def onBackEnd(self):
        def onClose(trade):
            logger.info(f"CLOSE {trade.symbol}  gain {trade.gain()} pnl : {trade.pnl()}")
            self.add_marker(trade.symbol,"BUY","CLOSE","#000000","arrowDown")
        self._book.end(0,onClose)

    def addLocalIndicator(self, ind:Indicator):
        self.localIndicators.append(ind)
        ind.client = self.client
        return ind
    
    def addLocalPlot(self,ind : Indicator ,name :str,  color:str,panel: str ='main',source = None, style="Solid",lineWidth=1):
        if not source:
            source = ind.target_cols[0]
        self.localPlots.append({"ind": ind ,"name" : name ,"source" : source, "color" : color, "panel" : panel,"style":style,"lineWidth": lineWidth})
        pass
    

    def populate_indicators(self) :
        h = self.addIndicator(self.timeframe,MAX("high_max","high",timeperiod=6))
        l=self.addIndicator(self.timeframe,MIN("low_max","low",timeperiod=6))
        self.addIndicator(self.timeframe,SUM("vol_max","base_volume",timeperiod=6))

        self.addIndicator(self.timeframe,CHAIN("chain_down",False))

        chain = self.addLocalIndicator(CHAIN("chain_up",True))
        self.addLocalIndicator(GAIN("GAIN","close",timeperiod=1))

        self.addLocalPlot(chain, "chain_up","#a70000", "sub1", style="Solid", lineWidth=1)

        self.add_plot(h, "hi","#a70000", "main", style="Solid", lineWidth=1)
        self.add_plot(l, "low","#a4a700cf", "main", style="Solid", lineWidth=1)
        pass
    
    
    def dump_indicators1(self):
        ret = super().dump_indicators()

        base_seconds = TIMEFRAME_SECONDS[self.timeframe]
        sub_seconds = TIMEFRAME_SECONDS[self.sub_timeframe]

        steps = 1;#int(sub_seconds / base_seconds)-1
        time_step = base_seconds*1000

        #df = self.df(self.timeframe)
        
        o=[]
        for p in  self.localPlots:
            for col in p["ind"].target_cols:
                if (col ==p["source"] or not p["source"]):

                    d = p.copy()
                    del d["ind"]

                    d["timeframe"] = self.timeframe
                   # df_data = p["ind"].get_render_data(df,col)

                    #df_data = pd.DataFrame(columns=[
                    #    'symbol','value','time'
                    #])
                    expanded_rows = []


                    for symbol,df in self.local_df.items():
                    #logger.info(f"process {col}")
                   
                        _df_data = (
                            df[["symbol", "timestamp", col]]
                            .dropna(subset=[col])
                            .rename(columns={
                                col: "value",
                                "timestamp": "time"
                            })
                        )
                    
                        
                        # espando 
                        #expanded_rows = []

                    #  print(steps,time_step,df_data)
                        for _, row in _df_data.iterrows():
                            for i in range(steps):
                                new_time = int(row["time"]) + i * time_step

                                expanded_rows.append({
                                    "symbol": row["symbol"],
                                    "time": new_time,
                                    "value": row["value"]
                                })
                        
                    df_data = pd.DataFrame(expanded_rows)            
                    df_data.to_csv("df_data.csv", index=False)

                    #print(df_data.head(30))
                    d["data"] = df_data.to_dict(orient="records")
                        
                    o.append(d)

        return o
    



    def live_indicators(self,symbol,timeframe,from_ts,to_ts):
        data = super().live_indicators(symbol, timeframe,from_ts,to_ts)
        list = data["list"]
        logger.info(f"sssssssss {list}")
    
    def get_key(self,timeframe,dt ):
        if timeframe =="1m":
            return dt.minute
        elif timeframe =="30s":
                # 0 oppure 1
            half = dt.second // 30
            return (dt.minute, half)
             
    def compute_local_df(self,timeframe, symbol:str, dataframe: pd.DataFrame,local_index : int):

        row = dataframe.iloc[local_index]
        #timestamp = pd.to_datetime(row['timestamp'])
        datetime = row["datetime"]
        timestamp = row["timestamp"]

     
        
        # inizializza strutture
        if symbol not in self.buffers:
            self.buffers[symbol] = []
            self.last_candle_key[symbol] = self.get_key(timeframe,datetime)
            self.local_df[symbol] = pd.DataFrame(columns=[
                'symbol','datetime','timestamp', 'open','high', 'low',   'close', 'base_volume'
            ])

        # aggiungi al buffer
        self.buffers[symbol].append({
            'timestamp': timestamp,
            'datetime': datetime,
            'open':  row['open'],
            'high':  row['high'],
            'low':  row['low'],
            'close':  row['close'],
            'base_volume': row.get('base_volume', 0)
        })

        key = self.get_key(timeframe,datetime)
        # 🔑 chiusura candela quando secondi == 0
        if key != self.last_candle_key[symbol]:
            self.last_candle_key[symbol]=key
            
            actual = self.buffers[symbol][-1]
            self.buffers[symbol] = self.buffers[symbol][:-1]

            buf = pd.DataFrame(self.buffers[symbol])

            if len(buf) == 0:
                return None

            open_ = buf.iloc[0]['open']
            close_ = buf.iloc[-1]['close']
            high_ = buf['high'].max()
            low_ = buf['low'].min()
            volume_ = int(buf['base_volume'].sum())

            #timestamp = buf.iloc[0]['timestamp']
            # timestamp della candela = minuto appena chiuso
            datetime = buf.iloc[0]['datetime']#.replace(second=0, microsecond=0)

            new_row = {
                'symbol' : symbol,
                'datetime' : datetime,
                'timestamp':  int(datetime.timestamp())*1000,#candle_time.totimestamp(),
                'open': open_,
                'high': high_,
                'low': low_,
                'close': close_,
                'base_volume': volume_
            }

            self.local_df[symbol] = pd.concat([
                self.local_df[symbol],
                pd.DataFrame([new_row])
            ], ignore_index=True)

            # reset buffer (inizia nuova candela)
            self.buffers[symbol] = [actual]

            try:

                for  ind in self.localIndicators:  
                   # logger.info(f"{ self.local_df[symbol]}")
                    ind.apply(symbol,  self.local_df[symbol] ,  self.local_df[symbol] , len(self.local_df[symbol])-1)
            except:
                logger.error("error",exc_info=True)

            return new_row
        else:
            return None


    async def trade_symbol_at(self, symbol:str, dataframe: pd.DataFrame,local_index : int, metadata: dict):

        use_day=not self.backtestMode

        
        #if symbol != "BIRD":
        #[]    return
        
        #row_1m = self.compute_local_df(self.sub_timeframe,symbol,dataframe, local_index)
        
        ####################################

        if (local_index < 6):   
            return
        
        last = dataframe.iloc[local_index]
        prev = dataframe.iloc[local_index-6]

        if last["base_volume"] == 0:
            return
        if dataframe.iloc[local_index-1]["base_volume"] == 0:
            return
        if dataframe.iloc[local_index-2]["base_volume"] == 0:
            return

        high_max = last["high_max"]
        low_max = last["low_max"]
        vol_max = last["vol_max"]

        chain_gain = (high_max-low_max) / low_max * 100

        gain = (last["close"] -prev["close"] ) / prev["close"] * 100

        #chain_gain = 30
        ###### FIRST ENTER ########
        if not self.has_meta(symbol,"first_enter"): 
            first_enter = StrategyUtils.compute_first_enter(self.client,symbol,dataframe,local_index, use_day)
            #await self.compute_first_enter(symbol, dataframe,local_index, use_day, value= close )
            self.set_meta(symbol, {"first_enter": first_enter }) 

        if  not last["timestamp"] > self.get_meta(symbol,"first_enter"):
            return
        
        '''
        df = self.local_df[symbol]
        if len(df)==0:
            return
        last_1m =  df.iloc[-1]

        chain_up = int(last_1m["chain_up"])
        '''
        
        #if row_1m:
        #    logger.info(f"{last_1m}")

        #return

        last_trade_time = 999999
        if (symbol in self.last_trade):
            last_trade_time = (int(last["timestamp"]) - self.last_trade[symbol]) / 1000
            #logger.info(last_trade_time)

        #if row_1m:
        if not self.hasCurrentTrade(symbol) and last_trade_time > 60*10:
            #df = self.local_df[symbol]
            #last_1m =  df.iloc[-1]
            
            #logger.info(f"{last_1m}")

            if chain_gain>=self.min_gain and gain > self.min_gain/2:

                    #logger.info(df.head(10))    
                 
                    volume = vol_max
                    if True:#volume > self.min_volume :

                        logger.info(f"BUY {symbol}  {last['datetime']}  {chain_gain} ")#\n{last_1m}")

                        await self.buy(symbol, int(last["timestamp"]), last["close"], 100, "buy")
                        self.max_gain[symbol] =0
                        self.last_trade[symbol] = int(last["timestamp"])

        if self.hasCurrentTrade(symbol):

                    gain,ts,pnl = self.buyGain(symbol, last["close"]) 

                    #logger.info(f"SELL GAIN {symbol}  gain {gain} ts{ts} pnl {pnl}")

                    dt = int(dataframe.iloc[local_index]["timestamp"])
                    self.set_current_price(symbol, last["close"])         
                    time_elapsed_secs = (int(last["timestamp"]) - ts) / 1000   
                    
                    chain_down = last ["chain_down"]

                    self.max_gain[symbol] = max(self.max_gain[symbol] , gain)
                    
                    logger.info(f"SELL GAIN {symbol}  {last['datetime']} secs: {time_elapsed_secs} gain {gain} pnl {pnl} chain_down {chain_down}")

                    if chain_down>=3:
                        trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                        self.del_meta(symbol,"state")

                    '''
                    if last["close"] < sl:#-self.magain_percx_loss:
                            if self.sl_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"SL"  )
                                self.del_meta(symbol,"state")

                        
                    elif gain > self.gain_perc:
                            if self.tp_enabled(symbol):
                                trade = await  self.sell(symbol, dt, last["close"], f"TP"  )
                                self.del_meta(symbol,"state")
                    '''