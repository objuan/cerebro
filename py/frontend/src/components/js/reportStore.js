import { reactive } from 'vue'

export const reportStore = reactive({
  items: {},

  patchReport(incoming) {
    for (const [symbol, data] of Object.entries(incoming)) {
      if (!this.items[symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[symbol] = {}
        this.items[symbol].deleted = false
      }

      Object.assign(this.items[symbol], data)
    }
  },
  
  push(evt) {
    this.patchReport(evt)
  },
  resume_symbol(symbol) {
    if (this.items[symbol]) {
      this.items[symbol].deleted = false
    }
  },
  del_symbol(symbol) {
    if (this.items[symbol]) {
      this.items[symbol].deleted = true
    }
  },

  clear() {
    // svuota l'oggetto mantenendo la reference reattiva
    Object.keys(this.items).forEach(k => delete this.items[k])
  },
  get_report(symbol){
      return this.items[symbol]
  }
  
})