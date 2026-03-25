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
       this.strategy=""
       this.params={}
  }
}

export const backTest = reactive({
    
    async load(){
        this.profiles = await send_get("/back/profiles")
        this.inData = new BacktestIn()
    },
    async save(){
        send_post("/back/profile/save", {"name": this.profileName,
             "data":this.inData  })
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
                this.inData.dt_from  = data.dt_from
                this.inData.date  = data.date
                this.inData.tf  = data.tf
                this.inData.strategy  = data.strategy

                 console.log("profile data",profileName,this.inData)


                send_get("/back/enabled",{"enable": true})
                send_get("/back/profile/select",{"name": name})
            }
    }
  
})
