import { reactive } from 'vue'
import { newsStore } from "@/components/js/newsStore";

export class Rank{
   //  type = 'perc', 'range'
    constructor(name,type, value, good_range, map_range, best_value=-1 ){
      this.name=name
      this.type=type
      this.value=value
      this.good_range=good_range
      this.map_range=map_range
      this.best_value=best_value
      this.rank = this.compute()
    }
    compute() {
        const [goodMin, goodMax] = this.good_range
        const [mapMin, mapMax] = this.map_range

        // fuori dal good range
        if (this.value < goodMin || this.value > goodMax) {
          return 0
        }

        // 🔹 Caso 1: mapping lineare normale
        if (this.best_value === -1) {
          let mapped = ((this.value - mapMin) / (mapMax - mapMin)) * 100
          mapped = Math.max(0, Math.min(100, mapped))
          return Math.round(mapped)
        }

         // 🔹 Caso 2: mapping centrato su best_value
        // distanza massima possibile dal best_value dentro good_range
        const maxDistance = Math.max(
          Math.abs(this.best_value - goodMin),
          Math.abs(this.best_value - goodMax)
        )

        const distance = Math.abs(this.value - this.best_value)

        // 100 quando distance = 0
        // 0 quando distance = maxDistance
        let mapped = (1 - distance / maxDistance) * 100

        mapped = Math.max(0, Math.min(100, mapped))

        return Math.round(mapped)
  }
}
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
  gain_map(val, min,max){
    if (val < min) return 0;
    val = Math.min(val,max)
    return 0.5 + (val -max )*0.5
  },
  get_sum_rank(symbol){
        
       if (this.items[symbol]) {
         let rep = this.items[symbol]

         let news_rank = newsStore.get_news_rank(symbol);

         //console.log("rep",rep)
          return {
            "day_volume": new Rank("day_volume", "vol", rep.day_volume,[500000,9999999999], [500000,2_000_000]),//this.gain_map(rep.rel_vol_24,5,10), //rep.rel_vol_24 > 5, // 1)	Volume scambio > 500% alla media (5 volte) a 50 giorni
            "gap" :  new Rank("gap", "perc", rep.gain,[5,9999], [5,100]),//this.gain_map(rep.gap,2,10), // rep.gap > 2, // 2)	Gain > 2% nel trading pre mercato
            "rel_vol_24": new Rank("rel_vol_24", "vol", rep.rel_vol_24,[5,9999], [5,20]),//this.gain_map(rep.rel_vol_24,5,10), //rep.rel_vol_24 > 5, // 1)	Volume scambio > 500% alla media (5 volte) a 50 giorni
            "gain" :  new Rank("gain", "perc", rep.gain,[5,9999], [5,100]), //this.gain_map(rep.gain,10,20) , // rep.gain > 10 , 
            "last" : new Rank("last", "price", rep.last,[0.5,5], [0.5,2]),// this.value_map(rep.last, 1, 20, 3, 8),//rep.last>=1 &&  rep.last < 20, 
            "float":  new Rank("price", "vol", rep.float,[1000000,50000000], [1000000,10000000]),//this.value_map(rep.float, 1000000, 10000000, 1000000, 10000000), // rep.float < 10000000, 
            "news" :  news_rank
          }
       }
       else
       {
          return {"day_volume": 0 , "gain" : 0, "rel_vol_24": 0, "gap" : 0 , "price" : 0 , "float": 0, "news" : 0}
      }
  }
})