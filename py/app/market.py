import pandas as pd
import json
from datetime import datetime, timedelta
from datetime import time as _time
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Dict, List
from config import DB_FILE,CONFIG_FILE
from utils import convert_json
from enum import Enum

rome_zn= ZoneInfo("Europe/Rome")

class MarketZone(Enum):
    PRE = "PRE"
    LIVE = "LIVE"
    AFTER = "AFTER"
    CLOSED = "CLOSED"

MZ_TABLE = {
                MarketZone.CLOSED: 0,
                MarketZone.AFTER: 3,
                MarketZone.LIVE: 2,
                MarketZone.PRE: 1,
}


@dataclass
class Session:
    start: datetime.time
    end: datetime.time

    def contains(self, t: datetime.time) -> bool:
        return self.start <= t < self.end

@dataclass
class Market:
    name: str
    exchanges: List[str]
    timezone: str
    premarket: Session
    market: Session
    after: Session

    TZ_MAP = {
        "ET": "America/New_York"
    }
    def start(self):
        self.tz = ZoneInfo(self.TZ_MAP[self.timezone])

    def is_in_time( self, dt, from_day_ms, to_day_ms, onlyDay =True):

        ny_time = dt.astimezone(self.tz)
        today_ny = datetime.now(self.tz).date()

        if onlyDay and ny_time.date() != today_ny:
            return False

        ms_day = (
            ny_time.hour * 3600000 +
            ny_time.minute * 60000 +
            ny_time.second * 1000 +
            ny_time.microsecond // 1000
        )

        return from_day_ms <= ms_day <= to_day_ms

    def getPrevCloseDate(self, dt: datetime | None = None) -> datetime:
        """
        Ritorna il datetime della chiusura del giorno lavorativo precedente
        (es. 16:00 ET per USA).
        """
        # se dt non fornito → ora attuale del mercato
        if dt is None:
            dt = datetime.now(self.tz)
        else:
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=self.tz)
            else:
                dt = dt.astimezone(self.tz)

        # data di partenza
        day = dt.date()

        # se oggi è weekend → parti da venerdì
        if day.weekday() == 5:      # sabato
            day -= timedelta(days=1)
        elif day.weekday() == 6:    # domenica
            day -= timedelta(days=2)

        # se siamo PRIMA della chiusura odierna,
        # il "previous close" è quello del giorno prima
        if dt.time() < self.market.end:
            day -= timedelta(days=1)

        # se finisce nel weekend, torna indietro
        while day.weekday() >= 5:
            day -= timedelta(days=1)

        # datetime della chiusura
        return datetime.combine(
            day,
            self.market.end,
            tzinfo=self.tz
        )
        
    def isLiveZone(self) -> MarketZone:
        return self.getCurrentZone() == MarketZone.LIVE
    
    def getCurrentZone(self) -> MarketZone:
        return self.getZone(datetime.now(rome_zn) )

    def getZone(self, dt: datetime) -> MarketZone:
        """
        dt può essere naive o timezone-aware
        """
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=self.tz)
        else:
            dt = dt.astimezone(self.tz)

        #print("dt",tz,dt)

        now = dt.time()

        if self.premarket.contains(now):
            return MarketZone.PRE

        if self.market.contains(now):
            return MarketZone.LIVE

        if self.after.contains(now):
            return MarketZone.AFTER

        return MarketZone.CLOSED

def parse_time(t: str) -> datetime.time:
    h, m = map(int, t.split(":"))
    return _time(hour=h, minute=m)

########################################

class MarketService:
    def __init__(self,config):
        data = config["markets"]
        
        markets = {}

        for name, cfg in data.items():
            markets[name] = Market(
                name=name,
                exchanges=cfg["exchanges"],
                timezone=cfg["timezone"],
                premarket=Session(
                    parse_time(cfg["premarket"]["start"]),
                    parse_time(cfg["premarket"]["end"])
                ),
                market=Session(
                    parse_time(cfg["market"]["start"]),
                    parse_time(cfg["market"]["end"])
                ),
                after=Session(
                    parse_time(cfg["after"]["start"]),
                    parse_time(cfg["after"]["end"])
                )
            )
            markets[name].start()

        self.markets = markets
        self._exchange_map: dict[str, Market] = {}

        for market in markets.values():
            for ex in market.exchanges:
                self._exchange_map[ex.upper()] = market

    def getMarket(self, exchange: str) -> Market:
        ex = exchange.upper()

        if ex not in self._exchange_map:
            raise KeyError(f"Exchange '{exchange}' non associato ad alcun Market")

        return self._exchange_map[ex]

    def getCurrentMarketZone(self,exchange: str) -> MarketZone:
        return self.getMarket(exchange).getZone(datetime.now(ZoneInfo("Europe/Rome")))
    
    def compute_useRTH(self,exchange: str, dt: datetime) -> int:
        zone = self.getMarket(exchange).getZone(dt)

        if zone == MarketZone.LIVE:
            return 1

        if zone in (MarketZone.PRE, MarketZone.AFTER):
            return 0

        raise RuntimeError("Mercato chiuso: evitare chiamata IB")
    
###################

if __name__ =="__main__":
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        config = json.load(f)
    config = convert_json(config)

    ms = MarketService(config)
    print(ms.markets)

    now = datetime.now(ZoneInfo("Europe/Rome"))
    print("now",now)
    zone = ms.getMarket("AUTO").getZone(now)

    print(zone)

