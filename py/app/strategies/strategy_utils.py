from typing import Dict
import pandas as pd
import logging
from datetime import datetime, timedelta
from bot.indicators import *
from bot.smart_strategy import SmartStrategy
from zoneinfo import ZoneInfo
from market import Market
from collections import defaultdict

logger = logging.getLogger(__name__)

from report import *
from reports.db_dataframe import *
from renderpage import RenderPage
from utils import *
from reports.report_manager import ReportManager

from order_book import *


    


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

   
    async def compute_first_enter(client,symbol,dataframe,local_index, use_day):
          

                last = dataframe.iloc[local_index]
                if use_day:
                    date = datetime.now().date()    
                else:
                    date = last["datetime"].date()    

                d_df = client.get_df(f"""SELECT * FROM ib_day_watch  
                            WHERE date = '{date}' AND symbol = '{symbol}' """)  
                
                #first_enter = d_df.iloc[0]["ds_timestamp"]
                if not d_df.empty:  
                    utc_dt = datetime.strptime(d_df.iloc[0]["ds_timestamp"], '%Y-%m-%d %H:%M:%S')
                    utc_dt = utc_dt.replace(tzinfo=pytz.utc)
                    first_enter = int(utc_dt.timestamp()  ) * 1000  
                else:
                    first_enter=-1
                return first_enter

              