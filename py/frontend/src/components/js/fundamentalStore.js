import { reactive } from 'vue'
import { send_get } from  '@/components/js/utils.js'; 
export const fundamentalStore = reactive({
  items: {},

  clear() {
    // svuota l'oggetto mantenendo la reference reattiva
    Object.keys(this.items).forEach(k => delete this.items[k])
  },

  async get(symbol){
     if (this.items[symbol]) {
        return this.items[symbol]
    }
    else{
        let list = await send_get("/api/fundamental/get",{"symbol":symbol })
        this.items[symbol] = list
        return list;
    }
  }
  

})