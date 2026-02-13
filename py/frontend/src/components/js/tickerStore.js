import { reactive } from 'vue'

export const tickerStore = reactive({
  items: {},

  pushAll(incoming) {

 
    for (const [symbol, data] of Object.entries(incoming)) {
      if (!this.items[symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[symbol] = {}
      }

      Object.assign(this.items[symbol], data)
    }
  },

  push(data) {

    //  console.log("incoming",data)
      if (!this.items[data.symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[data.symbol] = {}
      }

      Object.assign(this.items[data.symbol], data)
    
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