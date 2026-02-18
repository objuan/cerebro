import { liveStore } from '@/components/js/liveStore.js';
import { staticStore } from '@/components/js/staticStore.js';
import { send_get } from '@/components/js/utils';

let propInitialized = false;

export async function initProps() {
    if (propInitialized)
        return

    console.log("PROP INIT")
    propInitialized=true;

  let pdata = await send_get("/api/props/find", {path : ""})
        //console.log(pdata)
        pdata.forEach(  (val) =>{
          //  console.log("prop",val.path, val.value)
            if (val.path.startsWith("chart")  
            || val.path.startsWith("home")
          || val.path.startsWith("symbols")
            || val.path.startsWith("event") 
         || val.path.startsWith("back") )
            {
              staticStore.load(val.path, val.value);
            }
            else
            {
              liveStore.set(val.path, val.value);
            } 
        });
}
