import { reactive } from 'vue'
import { tickerStore as tickerList} from '@/components/js/tickerStore.js'
import { eventBus } from "@/components/js/eventBus";

export const tradeStore = reactive({
  items: {},

  push(data) {

      // console.log("incoming",data)
      if (!this.items[data.symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[data.symbol] = []
      }

      this.items[data.symbol].push(data)
      data.isOpen = this.isOpen(data)  
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
  isOpen(trade){
    if (!trade) return false
        return !trade.list.some(fill => fill.side === 'SELL')
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