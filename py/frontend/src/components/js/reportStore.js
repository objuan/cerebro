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
  },
  value_map(val, min ,max, ok_min, ok_max){
    if (val < min) return 0;
    if (val > max) return 0;
    if (val>= ok_min && val <= ok_max) return 1
    else if (val < ok_min ) return (val - min) / (ok_min-min)
    else if (val > ok_max ) return (val - ok_max) / (max-ok_max)
    else
    return 0;
  },
  gap_map(val, min,max){
    if (val < min) return 0;
    val = Math.min(val,max)
    return 0.5 + (val -max )*0.5
  },
  get_sum_rank(symbol){
        
       if (this.items[symbol]) {
         let rep = this.items[symbol]
         //console.log("rep",rep)
          return {
            "gap" :  this.gap_map(rep.gap,2,10), // rep.gap > 2, // 2)	Gain > 2% nel trading pre mercato
            "volume": this.gap_map(rep.rel_vol_24,5,10), //rep.rel_vol_24 > 5, // 1)	Volume scambio > 500% alla media (5 volte) a 50 giorni
            "gain" :  this.gap_map(rep.gap,10,20) , // rep.gain > 10 , 
            "price" : this.value_map(rep.last, 1, 20, 3, 8),//rep.last>=1 &&  rep.last < 20, 
            "float":  this.value_map(rep.float, 1000000, 10000000, 1000000, 10000000), // rep.float < 10000000, 
            "news" : 0}
       }
       else
       {
          return {"gain" : 0, "volume": 0, "up" : 0 , "price" : 0 , "float": 0, "news" : 0}
      }
  }
})