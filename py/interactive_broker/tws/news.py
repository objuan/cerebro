from ib_insync import *
import asyncio
from datetime import datetime, timedelta
util.startLoop()   # 🔑 IMPORTANTISSIMO

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=1)

contract = Stock('AAPL', 'SMART', 'USD')
ib.qualifyContracts(contract)


print("-----------")

newsProviders = ib.reqNewsProviders()
for p in newsProviders:
    print(p.code, '-', p.name)

#exit()

#codes = 'BRFG'  # Use Briefing for full articles
codes = '+'.join(np.code for np in newsProviders)

amd = Stock('NVDA', 'SMART', 'USD')
ib.qualifyContracts(amd)

# Calcola la data di ieri in modo procedurale
yesterday = datetime.now() - timedelta(minutes=60)
startDateTime = yesterday.strftime('%Y%m%d %H:%M:%S'),

headlines = ib.reqHistoricalNews(amd.conId, "BRFG+BRFUPDN+FLY", startDateTime, '', 10)
for new in headlines:
    print("Headline:", new.headline)
    article = ib.reqNewsArticle(new.providerCode, new.articleId)
    print("Article length:", len(article))
    #print("Article start:", article[:200])  # Print first 200 chars
    #print("Full article:", repr(article))  # To see if it's truncated


print("-----------")


# Subscribe to news bulletins
ib.reqNewsBulletins(allMessages=True)

#print(ib.newsBulletins())


def on_news_bulletin(newsBulletin):
    print(f"NEWS BULLETIN {newsBulletin}")
   
def on_news_events(newsBulletin):
    print(f"NEWS EVT {newsBulletin}")
   

ib.newsBulletinEvent += on_news_bulletin
ib.tickNewsEvent += on_news_events


ib.run()

print("---- DONE -------")