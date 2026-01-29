import { reactive } from 'vue'

export const reportStore = reactive({
  items: {},

  patchReport(incoming) {
    for (const [symbol, data] of Object.entries(incoming)) {
      if (!this.items[symbol]) {
        // crea oggetto reattivo per il symbol
        this.items[symbol] = {}
      }

      Object.assign(this.items[symbol], data)
    }
  },

  push(evt) {
    this.patchReport(evt)
  },

  clear() {
    // svuota l'oggetto mantenendo la reference reattiva
    Object.keys(this.items).forEach(k => delete this.items[k])
  }
})