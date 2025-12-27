import pandas as pd

class JobCache:
    def __init__(self):
        self.cacheMap = {}
        
    def getCache(self,key:str):
        if key in self.cacheMap:
            return self.cacheMap[key]
        else:
            return None
    
    def addCache_df(self,key:str,df : pd.DataFrame) :
        self.cacheMap[key] = df

    def addCache_str(self,key:str,value:str) :
        self.cacheMap[key] = value