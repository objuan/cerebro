import { reactive } from 'vue'
import { tickerStore as tickerList} from '@/components/js/tickerStore.js'
import { eventBus } from "@/components/js/eventBus";

export const tradeStore = reactive({
  items: {},
  day_PNL: 0,
  win: 0,
  loss: 0,
  total: 0,

  push(data) {

    const symbol = data.symbol;
    const newTime = data.list?.[0]?.time;
    data.pos = newTime;
    data.isOpen = this._isOpen(data)  

     if (!this.items[symbol]) {
        this.items[symbol] = [];
      }

      if (newTime) {
        const index = this.items[symbol].findIndex(
          item => item.list?.[0]?.time === newTime
        );

        if (index !== -1) {
          // aggiorna il vecchio mantenendo eventuali campi non presenti nel nuovo
          this.items[symbol][index] = {
            ...this.items[symbol][index],
            ...data
          };
        } else {
          this.items[symbol].push(data);
        }
      }
      

      //console.log("trade",data)     

      this._day_pnl()
      
      eventBus.emit("trade-last-changed",data)
      //Object.assign(this.items[data.symbol], data)
    
  },
  
  clear() {
    Object.keys(this.items).forEach(k => delete this.items[k])
  },

  get_trades(symbol){
    if (this.items[symbol])
        return this.items[symbol].slice().reverse()
    else
      return []
  },
  get_all_trades() {
  return Object.values(this.items)          // prende tutti gli array
    .flat()                                 // li unisce in uno solo
    .slice()                                // copia di sicurezza
    .sort((a, b) => b.pos -a.pos);         // ordina per pos crescente
  },
  lastTrade(symbol) {
    //if (tradeList.value.length === 0) return null
    const trades = this.get_trades(symbol)
    if (!trades || trades.length === 0) return null
    return trades[0]
  },
  del(symbol) {
    if (this.items[symbol]) {
      delete this.items[symbol]
    }
  },

  get_list() {
    return Object.entries(this.items).map(([symbol, data]) => ({
      symbol,
      ...data
    }))
  },
   _day_pnl(){
    this.day_PNL=0;
    this.win=0;
    this.loss=0;
    this.total=0; 
    this.get_all_trades().forEach( (trade) => {  
       if (!trade.isOpen){
        //if (!trade.isOpen)
         // console.log("trade",trade.value) 
          this.day_PNL = this.day_PNL +trade.pnl
          this.total = this.total +1  
          if (trade.pnl >= 0) {
            this.win = this.win +1
          } else {
            this.loss = this.loss +1
          } 
       } 
    })

  },
  _isOpen(trade){
    if (!trade) return false
    return !trade.list.some(fill => fill.side === 'SELL')
  },
  buyPrice(trade){
    if (!trade) return null
    const buyPrices = trade.list
      .filter(f => f.side === 'BUY')
      .map(f => f.price)  
      return buyPrices[0] || null 
  },
  
  computeGain(trade)
  { // console.log("computeGain",trade) 

    const ticker = tickerList.get_ticker(trade.symbol)
    if (!ticker) return null;
    
    let _lastPrice = ticker.last
    if (_lastPrice){
          //console.log("lastPrice",_lastPrice) 

          const buyTotal = trade.list
            .filter(fill => fill.side === 'BUY')
            .reduce((sum, fill) => sum + fill.price * fill.size, 0)

          const buySize = trade.list
            .filter(fill => fill.side === 'BUY')
            .reduce((sum, fill) => sum + fill.size, 0)

            const buyPrices = trade.list
              .filter(f => f.side === 'BUY')
              .map(f => f.price)
              
          const avgPrice =
            buyPrices.length
              ? buyPrices.reduce((s, p) => s + p, 0) / buyPrices.length
              : 0

          const sellTotal = trade.list
            .filter(fill => fill.side === 'SELL')
            .reduce((sum, fill) => sum + fill.price * fill.size, 0)
          

          const sellSize= trade.list
            .filter(fill => fill.side === 'SELL')
            .reduce((sum, fill) => sum + fill.size, 0)

          const remain = buySize-sellSize

          const actualSell =remain * _lastPrice
          
          //console.log("cpu",buyTotal,sellTotal,remain,actualSell) 

          const pnl = actualSell-buyTotal;
          
          const gain =  ((actualSell-buyTotal) / buyTotal) * 100
      
         // console.log("pnl",pnl,"gain",gain)

          return {buyTotal,avgPrice,sellTotal,actualSell,buySize,sellSize,pnl, gain}
      }
      return null
  }
/*
  get_sorted() {
      let list = this.get_list() || {}
      return [...list].sort((a, b) =>
      b.gain-a.gain
    );
  }
    */
})