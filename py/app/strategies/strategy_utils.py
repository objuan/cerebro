from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta   
import pytz
from reports.db_dataframe import MetaInfo
from utils import *

logger = logging.getLogger(__name__)


########################

class StrategyUtils:

  
    def check_pattern(dataframe, local_index, N,min_gain):
        if local_index < N - 1:
            return (False,0,0,0)

        window = dataframe.iloc[local_index - N  : local_index+1 ]

        # Separo ultime e precedenti
        prev_candles = window.iloc[:-1]
        last = window.iloc[-1]

        # 1. Controllo che le prime N-1 siano rosse
        if not (prev_candles['close'] < prev_candles['open']).all():
            return (False,0,0,0)

        # 2. Ultima verde
        if not (last['close'] > last['open']):
            return (False,0,0,0)

        # 3. Altezza ultima candela
        last_height = abs(last['close'] - last['open'])

        # 4. Range min/max delle N candele
        max_high = prev_candles['high'].max()
        min_low = prev_candles['low'].min()
        total_range = max_high - min_low
        gain_perc = 100.0 * (total_range / min_low)

        # Evita divisioni strane
        if total_range == 0:
            return (False,0,0,0)

        # 5. Condizione finale
        return (gain_perc > min_gain and last_height >= (total_range / 3)  
            and last_height < total_range  
            and last['close'] < max_high,
            min_low,
            max_high,gain_perc)
    
    def check_fvg( dataframe, local_index, max_gap_perc=2.0):
        if local_index < 2:
            return (False, None, None, None,None)

        c1 = dataframe.iloc[local_index - 2]
        c2 = dataframe.iloc[local_index - 1]
        c3 = dataframe.iloc[local_index]

        # ---- BEARISH FVG PRECISO ----
        cond_structure = (
            c1['low'] >= c2['low'] and
            c1['low'] <= c2['high'] and

            c3['high'] >= c2['low'] and
            c3['high'] <= c2['high'] and 

            c1['close'] <= c1['open']  and
            c2['close'] <= c2['open']  and
            c3['close'] <= c3['open'] 
        )

        cond_gap = c1['low'] > c3['high']

        if cond_structure and cond_gap:
            gap_low = c3['high']
            gap_high = c1['low']
            gap_size = gap_high - gap_low

            # filtro dimensione gap (in %)
            gap_perc = 100.0 * (gap_size / gap_low)

            if gap_perc <= max_gap_perc:
                return (True, "bearish", gap_low, gap_high, gap_perc)

        # ---- BULLISH (speculare) ----
        cond_structure = (
            c1['high'] >= c2['low'] and
            c1['high'] <= c2['high'] and
            c3['low'] >= c2['low'] and
            c3['low'] <= c2['high']  and 

            c1['close'] > c1['open']  and
            c2['close'] > c2['open']  and
            c3['close'] > c3['open'] 
        )

        cond_gap = c1['high'] < c3['low']

        if cond_structure and cond_gap:
            gap_low = c1['high']
            gap_high = c3['low']
            gap_size = gap_high - gap_low

            gap_perc = 100.0 * (gap_size / gap_low)

            if gap_perc <= max_gap_perc:
                return (True, "bullish", gap_low, gap_high, gap_perc)

        return (False, None, None, None,None)

   
    def compute_first_enter(client,symbol,dataframe,local_index, use_day):
          

                last = dataframe.iloc[local_index]
                if use_day:
                    date = datetime.now().date()    
                else:
                    date = last["datetime"].date()    

                sql = f"""SELECT * FROM ib_day_watch  
                            WHERE date = '{date}' AND symbol = '{symbol}' """
                
                #logger.info(f"SQL {sql}  ")
                d_df = client.get_df(sql)  
                
                #first_enter = d_df.iloc[0]["ds_timestamp"]
                if not d_df.empty:  
                    utc_dt = datetime.strptime(d_df.iloc[0]["ds_timestamp"], '%Y-%m-%d %H:%M:%S')
                    utc_dt = utc_dt.replace(tzinfo=pytz.utc)
                    first_enter = int(utc_dt.timestamp()  ) * 1000  
                else:
                    first_enter=-1
                return first_enter

              
    async def compute_open(strategy,symbol,dataframe,local_index,open_count = 15, use_day=True):
        trade_last_hh = strategy.trade_last_hh
        last = dataframe.iloc[local_index]
        if  strategy.market.is_in_time(last["datetime"],
            get_hour_ms(9,00),get_hour_ms(trade_last_hh,00),use_day):
            #logger.info(f'{last["datetime"]}')

            if strategy.market.is_in_time(last["datetime"],
                get_hour_ms(9,30),get_hour_ms(trade_last_hh,00),use_day):
                #logger.info(f'{last["datetime"]}')

                is_inside=True
                if not strategy.has_meta(symbol,"open_gap"):
                    last_close = MetaInfo.get(symbol,"last_close")
                    if not last_close:
                        last_close, ts_last_close=  await strategy.client.last_close(symbol,last["datetime"] ) 
                    
                    #logger.info(f'last_close {last_close}')

                    if last_close:
                        strategy.set_meta(symbol,{"open_gap": 100.0* (last["close"] - last_close) / last["close"] })

                        #pre_gain = MetaInfo.get(symbol,"pre_gain")
                        #logger.info(f"{symbol} t:{last['datetime']} {self.get_meta(symbol,'open_gap')} close:{last['close']} last_close:{last_close}")

                ###### 15 perc ######

                if strategy.market.is_in_time(last["datetime"],
                        get_hour_ms(9,45),get_hour_ms(trade_last_hh,00),use_day):

                    if not strategy.has_meta(symbol,"open_perc"):
                        window = dataframe.iloc[local_index-open_count:local_index]
                        if len(window)>0:   
                            low = window["low"].min()
                            high = window["high"].max()

                            l_h_perc = 100.0 * (high - low) / low

                            first = window.iloc[0]
                            last = window.iloc[-1]

                            perc = 100.0 * (last["close"] - first["open"]) / first["open"]
                            '''
                            first = dataframe.iloc[local_index-15]
                        
                            low = min(first["low"] , prev["low"])
                            high = max(first["high"] , prev["high"])
                                    
                            l_h_perc = 100.0* (high-low) / low
                            perc =  100.0 * (prev["close"]- first["open"]) / first["open"]
                            '''
                            #logger.info(f"OPEN {symbol} t:{last['datetime']}  OPEN 15M O:{first['open']}  C:{last['close']} perc:{perc} l_h_perc:{l_h_perc} local_index:{local_index} last_idx: { last.name}")

                            strategy.set_meta(symbol, 
                                    {
                                        "compute_open" : True,
                                    "open_high" : high,
                                    "open_low": low,
                                    "open_perc" : perc, 
                                    "open_perc_min_max":l_h_perc,
                                    "open_close_idx": local_index,
                                    "open_volume": last["day_volume_history"]   
                                    } )
        return strategy.has_meta(symbol,"open_high" )
    
    async def get_last_close(strategy,symbol, lastCandle, addMarker):
        if not strategy.has_meta(symbol,"last_close"):
            last_close, ts_last_close=  await strategy.client.last_close(symbol,lastCandle["datetime"] ) 
            strategy.set_meta(symbol,{"last_close": last_close})
            if addMarker:
                #logger.info(f"get_last_close {symbol} {last_close}")
                await strategy.add_marker(symbol,"SPOT","=","Last","#000000","square",position ="atPriceTop",timestamp=lastCandle["timestamp"],value=last_close)

        return strategy.get_meta(symbol,"last_close")


    async def get_first_day_price(strategy,symbol, lastCandle):
        if not strategy.has_meta(symbol,"first_day_price"):
            first_day_price, ts_last_close=  await strategy.client.first_day_price(symbol,lastCandle["datetime"] ) 
            strategy.set_meta(symbol,{"first_day_price": first_day_price})
        return strategy.get_meta(symbol,"first_day_price")

