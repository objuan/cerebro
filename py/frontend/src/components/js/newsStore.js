//import { reactive } from 'vue'

export const newsStore = {
  items: {},

  daysFromNowCalendar(unixSeconds) {
    const d1 = new Date(unixSeconds * 1000);
    const d2 = new Date();

    d1.setHours(0,0,0,0);
    d2.setHours(0,0,0,0);

    const diffMs = d2 - d1;
    return Math.floor(diffMs / (1000 * 60 * 60 * 24));
  },

  push(symbol,data) {
    if (!this.items[symbol]) {
      this.items[symbol] = []
    }
    data.items.forEach( (i)=>
    {
      const exists = this.items[symbol].some(
        n => n.guid === i.data.guid
      );
      if (!exists) 
      {
      //  console.log("add",symbol,i.data)
 
        i.data.days_passed = this.daysFromNowCalendar(i.data.published_at)

        this.items[symbol].push(i.data)
      }
    });
    //this.items[symbol].push(data)
  },

  del_symbol() {
   
  },

  clear() {
    // svuota l'oggetto mantenendo la reference reattiva
    Object.keys(this.items).forEach(k => delete this.items[k])
  },

  get_news(symbol){
    //console.log("get_news",symbol,this.items); 

    const list = this.items[symbol] || [];

    return [...list].sort((a, b) =>
      new Date(b.published_at) - new Date(a.published_at)
    );
  },
  get_news_rank(symbol){
      let list = this.get_news(symbol);
      if (list){
        if (list.length>0)
          return 1+list[0].days_passed;
        else
          return 0
      }
       else
          return 0
  },

}