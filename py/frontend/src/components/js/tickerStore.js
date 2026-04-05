import { reactive } from 'vue'

export const strategyStore = reactive({
    items: {},
    push(prop){
        
       // console.log("strategyStore",prop)
        const key =  `${prop.symbol}.${prop.timeframe}.${prop.source}`

        if (!this.items[key]) 
          this.items[key]={}
        Object.assign( this.items[key], prop.data)
    },
    get(symbol, timeframe, source){
        const key =  `${symbol}.${timeframe}.${source}`
        //console.log(this.items)
        return this.items[key]
    }
})


// =====================

export const tickerStore = reactive({
  items: {},

  pushAll(incoming) {

 
    for (const [symbol, data] of Object.entries(incoming)) {
      if (!this.items[symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[symbol] = {}
        this.items[symbol].strategy = strategyStore
      }

      Object.assign(this.items[symbol], data)
    }
  },

  push(data) {

    //  console.log("incoming",data)
      if (!this.items[data.symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[data.symbol] = {}
        this.items[data.symbol].strategy = strategyStore
      }

      Object.assign(this.items[data.symbol], data)
    
  },
  pushStrategy(prop){
    if (this.items[prop.symbol]) {
        this.items[prop.symbol].strategy.push(prop)
    }
  },

  clear() {
    // svuota l'oggetto mantenendo la reference reattiva
    Object.keys(this.items).forEach(k => delete this.items[k])
  },

  get_ticker(symbol){
      return this.items[symbol]
  },
  del_ticker(symbol) {
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
  get_sorted() {
      let list = this.get_list() || {}
    
      return [...list].sort((a, b) =>
      b.gain-a.gain
    );
  }
})