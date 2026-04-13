import {send_get,send_post} from  "@/components/js/utils";
import { reactive } from 'vue'

export class BacktestIn {
  constructor(){
       this.badgetUSD=1000
       this.symbols = []
       this.date=""
       this.tf=""
       this.dt_from=""
       this.dt_to =""
       this.module=""
       this.class=""
       this.params={}
  }
}

export const backTest = reactive({
    
    selectedHistory : "",

    async load(){
        this.profiles = await send_get("/back/profiles")
        console.log("profiles",this.profiles)   
        this.inData = new BacktestIn()
    },
    async save(){
       await  send_post("/back/profile/save", {"name": this.profileName,
             "data":this.inData  })
    },
    async pre_scan(){
        await send_get("/back/profile/pre_scan")
    },

    async execute(){
        await send_get("/back/profile/execute")
        await this.updateHistoryList()
    },

    async select(profileName){
        this.profileName=profileName
        const profile = this.profiles.find(
                p => p.name ===profileName
                )
        let profile_data = profile ? profile.data : null
        if (profile_data!=null)
         {
                let data = JSON.parse(profile_data)
               
                this.inData.badgetUSD  = data.badgetUSD
                this.inData.symbols  = data.symbols
                this.inData.dt_to  = data.dt_to
                this.inData.dt_from  = data.dt_from
                this.inData.date  = data.date
                this.inData.tf  = data.tf
                this.inData.class  = data.class
                this.inData.module  = data.module
                this.inData.params  = data.params

                 console.log("profile data",profileName,this.inData)


                send_get("/back/enabled",{"enable": true})
                send_get("/back/profile/select",{"name": name})
            }
    },
    async updateHistoryList(){
        this.setHistoryList(await send_get("/back/history/get",
            {"strategy": this.inData.module+"."+this.inData.class,
                "date": this.inData.date}))

    },
  
    setHistoryList(history){
        console.log("history Llist",history)    
        this.history_list = history.sort(
             (a, b) => b.ds_timestamp.localeCompare(a.ds_timestamp)
            )
        this.history_list.forEach(h => {
           /// console.log("history trades",h.trades)  
            h.trades = JSON.parse(h.trades)
            h.trades = JSON.parse(h.trades)

            h.totalGain = 0
            h.win=0
            h.loss=0
            h.trades.forEach(trade => {
                const entry_price = trade.entry_price
                const exit_price = trade.exit_price
                const gain = (exit_price-entry_price)/entry_price*100
                trade.gain = gain
                if (gain>0)
                    h.win++
                else
                    h.loss++    
                h.totalGain += gain
             });    

           // console.log("history trades",h.trades)  
        })
    },
    selectHistory(history){
       // console.log("history",history.trades)    
        this.history = history
        this.in_data = JSON.parse(history.in_data)
        this.trades =history.trades
        self.script =null;

        //this.in_params = JSON.parse(history.in_data)
     

       // console.log("history", this.trades)    

        /*
        this.trades = []
       // console.log("results",this.results)    
         this.results.trades.forEach(element => {
            const trades =  JSON.parse(element)

            //console.log("trades",trades) 
            trades.forEach(trade => {
                //console.log("trade",trade) 
                this.trades.push(trade) 
            });
         });
         */

    },
    getTradeCount(symbol){
        let count = 0
        this.trades.forEach(trade => {
            if (trade.symbol == symbol)
                count++
        }); 
        return count    
    },

     getTrades(symbol){
        let arr=[]
        this.trades.forEach(trade => {
            if (trade.symbol == symbol)
                arr.push(trade) 
        }); 
        return arr    
    },
    async getStrategyScript(){  
        if (!self.script )
        {
            self.script = await send_get("/back/trade/strategy/get",
                {"history_id": this.history.id})
        }
        return self.script
    }

})
