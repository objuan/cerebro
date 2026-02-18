<template>
  <div class="home">

   <!-- Bottone menu contestuale -->
          <div class="dropdown top-menu">
            <button
              class="btn btn-sm btn-light border-0"
              type="button"
              data-bs-toggle="dropdown"
              aria-expanded="false"
              @click.stop
            >
              ⋮
            </button>

            <ul class="dropdown-menu dropdown-menu-end">
               <li>  
                <button @click="$router.push('/backtest')">
                  Vai al Backtest
                </button>
                </li>

               <li><a class="dropdown-item" href="#"
                  @click.prevent="setGrid(1,1)">
                   Grid 1x1
                </a></li>
                <li><a class="dropdown-item" href="#"
                  @click.prevent="setGrid(2,1)">
                   Grid 2x1
                </a></li>
                <li><a class="dropdown-item" href="#"
                  @click.prevent="setGrid(1,2)">
                   Grid 1x2
                </a></li>
                <li><a class="dropdown-item" href="#"
                  @click.prevent="setGrid(1,3)">
                   Grid 1x3
                </a></li>
                <li><a class="dropdown-item" href="#"
                  @click.prevent="setGrid(3,2)">
                   Grid 3x2
                </a></li>

            </ul>
          </div>

    <PageHeader title="Cerebro V0.1" style="margin-left: 30px;margin-right: 30px;"/>
 
    <div class="layout">
        <!-- Sidebar -->
        <aside class="sidebar">
          <button
            class="sidebar-btn"
            @click="portfolioRef?.toggle()"
            title="Portfolio"
          >
            📊
            <span>Portfolio</span>
          </button>

          <button class="sidebar-btn"
              @click="ordersRef.toggle()"
               title="Orders">📑 Orders</button>

          <button class="sidebar-btn"
              @click="reportsRef.toggle()"
               title="GAP">📑 GAP</button>

          <button class="sidebar-btn"
              @click="rankRef.toggle()"
               title="Rank">📑 Ranks</button>


          <button class="sidebar-btn"
              @click="tradeRef.toggle()"
               title="Trade">📑 Trades</button>

          <button class="sidebar-btn"
              @click="tradeConfigRef.toggle()"
               title="Trade">📑 Trade Config</button>

          <button class="sidebar-btn"
              @click="scanRef.toggle()"
               title="Scan">📑 Scaner</button>

        </aside>

        <!-- Main content 
        <main class="content">
          <router-view />
        </main>
        -->

        <!-- Side panel -->
        <SidePanel title="Portfolio" ref ="portfolioRef">
            <PortfolioWidget  />
        </SidePanel>

        <SidePanel title="Orders" ref ="ordersRef">
            <OrdersWidget/>
        </SidePanel>

        <SidePanel title="GAP" ref ="reportsRef" width="900px">
            <ReportPanel ></ReportPanel>
        </SidePanel>

         <SidePanel title="Ranks" ref ="rankRef" width="600px">
            <OrderChartWidget  ></OrderChartWidget>
         </SidePanel>
          
         <SidePanel title="Day Trade" ref ="tradeRef" width="400px">
             <TradeSideSummary></TradeSideSummary>
        </SidePanel>


         <SidePanel title="Trade Config" ref ="tradeConfigRef" width="800px">
             <trade-config></trade-config>
        </SidePanel>


        <SidePanel title="Scan Panel" ref ="scanRef" width="800px">
             <ScanPanel></ScanPanel>
        </SidePanel>


    </div>

    <main class="main-columns">
      
      
          <StrategyWidget></StrategyWidget>
      
          <TickersSummary ref="tickets_summary"></TickersSummary>
        
        <div class="charts-grid" :style="gridStyle">
          <MultiCandleChartWidget
              v-for="cell in cells"
              :key="cell.id"
              :ref="el => widgetRefs[cell.id] = el"
              :id="cell.id"
              :number = "cell.number"
              :symbol="cell.symbol"
              :plot_config="cell.plot_config"
              :class="{ selected: selectedId === cell.id }"
              @select="onSelect"
          />
        </div>

         <EventHistory />

    </main>
     <EventToast  />

  </div>
</template>

<script setup>
import { onMounted, onUnmounted, ref ,nextTick ,onBeforeUnmount,computed } from 'vue';

import { liveStore } from '@/components/js/liveStore.js';
import { staticStore } from '@/components/js/staticStore.js';
import OrdersWidget from "@/components/OrdersWidget.vue";
import PortfolioWidget from "@/components/PortfolioWidget.vue";
import ReportPanel from "@/components/ReportPanel.vue";
import TickersSummary from '@/components/TickersSummary.vue'
import PageHeader from '@/components/PageHeader.vue'
import TradeConfig from '@/components/TradeConfig.vue'
//import CandleChartWidget from '@/components/CandleChartWidget.vue';
import MultiCandleChartWidget from '@/components/MultiCandleChartWidget.vue';
import OrderChartWidget from '@/components/OrderChartWidget.vue';
import { send_get,send_post } from '@/components/js/utils';
import { eventBus } from "@/components/js/eventBus";
import ScanPanel from '@/components/ScanPanel.vue';
import SidePanel from '@/components/SidePanel.vue';
import EventToast from '@/components/EventToast.vue'
import EventHistory from '@/components/EventHistory.vue'
import StrategyWidget from '@/components/StrategyWidget.vue'
import TradeSideSummary from '@/components/TradeSideSummary.vue'
import { eventStore } from "@/components/js/eventStore";
import { strategyStore } from "@/components/js/strategyStore";
import { reportStore } from "@/components/js/reportStore";
import { tickerStore } from "@/components/js/tickerStore";
import { newsStore } from "@/components/js/newsStore";
import { initProps } from "@/components/js/common";


// --- STATO REATTIVO ---

const portfolioRef = ref(null);
const ordersRef = ref(null);
const reportsRef= ref(null);
const rankRef= ref(null);
const tradeRef= ref(null);
const tradeConfigRef= ref(null);
const scanRef = ref(null);
//const toastRef= ref(null);

const widgetRefs = ref({})
const tickets_summary = ref(null)
const selectedId = ref(null)

const rows = ref(2)
const cols = ref(2)
const cells = ref([])  // contiene i widget attivi
// --- LOGICA WEBSOCKET ---
let ws = null;

const gridStyle = computed(() => ({
  display: 'grid',
  width: '100%',
  height: '100%',
  gridTemplateColumns: `repeat(${cols.value}, 1fr)`,
  gridTemplateRows: `repeat(${rows.value}, 1fr)`,
  gap: '6px',
}))

function setGrid(r, c) {
  rows.value = r
  cols.value = c

  const total = r * c
  const newCells = []
  widgetRefs.value={}
  for (let i = 0; i < total; i++) {

    let symbol = staticStore.get("chart."+(i+1)+".symbol","")
    //console.log("<< ",i+1, symbol)

    newCells.push({
      id: crypto.randomUUID(),
      number: i+1,          // posizione nella griglia (0 → n-1)
      symbol: symbol,
      plot_config: {}
    })
  }

  cells.value = newCells
  
  send_post('/api/props/save', { path: 'home.grid', value: `${r}_${c}` });

  nextTick(resizeAllCharts)
}

function resizeAllCharts() {
  for (const id in widgetRefs.value) {
    const comp = widgetRefs.value[id]
    const el = comp?.$el
    if (!el) continue
    const rect = el.getBoundingClientRect()
    comp.resize(rect.width, rect.height)
  }
}
window.addEventListener('resize', resizeAllCharts)

function onSelect(id) {
  selectedId.value = id
}

function onChartSelect(data){
  if (selectedId.value)
  {
      console.log("onChartSelect", cells.value,selectedId.value)

      //const componentInstance = cells.value[selectedId.value];
       const comp = widgetRefs.value[selectedId.value]
      console.log("find",comp)

      comp.setSymbol(data["symbol"])  
  }
}


// =============================================

const initWebSocket_mulo = () => {
  ws = new WebSocket("ws://127.0.0.1:8000/ws/orders");
  ws.onmessage = (event) => {
   
    const msg = JSON.parse(event.data);
    let dataParsed=null;
    //console.log(msg)
    switch (msg.type) {
         case "UPDATE_PORTFOLIO":
          //portfolioRef.value?.handleMessage(msg);
          eventBus.emit("update-portfolio", msg);
          break
        case "POSITION":
          //portfolioRef.value?.handleMessage(msg);
          eventBus.emit("update-position", msg);
          break

        case "POSITION_TRADE":
          //console.log("POSITION_TRADE",msg)
          //portfolioRef.value?.handleMessage(msg);
          eventBus.emit("trade-position", msg.data);
          break

        case "ORDER":
          
          //#ordersRef.value?.handleMessage(msg);
          
          dataParsed =
              typeof msg.data === "string"
                ? JSON.parse(msg.data)
                : msg.data;
          dataParsed["source"] = "order"  
          dataParsed["timestamp"] = msg["timestamp"]
          dataParsed["ts"] = msg["ts"]
          dataParsed["event_type"] = msg["event_type"]

          //console.log("ORDER",dataParsed)

          eventBus.emit("order-received", dataParsed);
          break
        case "TASK_ORDER":
         
          
          //.value?.handleMessage(msg);
          //msg.data= JSON.parse(msg.data)
          msg.data["source"] = "task-order"  
          //msg.data["ts"] = msg["ts"]
          msg.data["ts"] = msg.data["timestamp"]*1000
          console.log("TASK_ORDER",msg)

          eventBus.emit("task-order-received", msg.data);
          break

        case "TASK_ORDER_MSG":
         
          //console.log("TASK_ORDER_MSG",msg)
          //.value?.handleMessage(msg);
          //msg.data= JSON.parse(msg.data)
          msg.data.msg = msg.msg
          //msg.data["source"] = "task-order"  
          eventBus.emit("task-order-msg-received", msg.data);
          break

        case "ERROR":
          
          //#ordersRef.value?.handleMessage(msg);
     
          dataParsed = msg
         
          dataParsed["source"] = "error"  
          dataParsed["color"] = "#FF000"
        
          //console.log("ERROR",msg)

          eventBus.emit("error-received",dataParsed);
          break

        case "MESSAGE":
          
          //#ordersRef.value?.handleMessage(msg);
     
          dataParsed = msg
         
          dataParsed["source"] = "message"  
          dataParsed["color"] = "#FF000"
        
          console.log("MESSAGE",msg)

          eventBus.emit("message-received",dataParsed);
          break
    }
  }
};

const initWebSocket = () => {
  ws = new WebSocket("ws://127.0.0.1:8000/ws/live");

  ws.onmessage = (event) => {
    //console.log(">>",event.data)
    try
    {
      const msg = JSON.parse(event.data);

      if (msg.path) {
        // Aggiornando liveData[path], Vue notifica tutti i componenti in ascolto
          liveStore.set(msg.path, msg.data);
      }

      switch (msg.type) {
      
        case "symbols":
        {
            console.log("update symbols",msg) 

            msg.del.forEach(symbol => {
               tickerStore.del_ticker(symbol)

               reportStore.del_symbol( symbol)

            })
            msg.add.forEach(symbol => {
               reportStore.resume_symbol( symbol)
            })
            //eventBus.emit("symbols-received",msg.del);

            break;
        }

        case "candle":
          {
            // console.log("WS CANDLE",msg) 

              for (const id in widgetRefs.value) {
                const comp = widgetRefs.value[id]
                if (comp)
                  comp.on_candle(msg.data)
              }
              //#componentInstance.on_candle(msg.data);  
          }
          break;
        case "ticker":
          {
           // console.log("WS TICKER",msg.data);
            tickerStore.push(msg.data)
            eventBus.emit("ticker-received", msg.data);
          } 
          break
        case "props":
          {
            console.log("WS props",msg);          
            liveStore.set(msg.path, msg.value);
          } 
          break
        case "report":
          {
           //console.log("Report",msg.data);
            
            reportStore.push( msg.data)
            eventBus.emit("report-received", msg.data);

        }
          break;
        case "event":
          {
           // console.log("event",msg);
            
            if (msg.source =="strategy" || msg.source =="mule")
                strategyStore.push(msg);
            else 
            {
              eventBus.emit("event-received",msg.data);
              console.log(">>>", msg) 
              eventStore.push(msg);
            }
         }
          break;
        case "events":
          {
            //let d = JSON.parse(msg.data)
          //  console.log("events",msg.data);
            msg.data.forEach( (v)=>
            {
                eventBus.emit("event-received",v);
            });
            
            //eventBus.emit("event-received",msg.data);
        }
          break;
        
        case "news":
          {
          //  console.log("news",msg);
            newsStore.push(msg["symbol"], msg["data"])
         }
          break;

        case "ticker_rank":
          {
            //console.log("ticker_order",msg);
            eventBus.emit("ticker-rank",msg);
           
        }
          break;
      }
      
  }
 
   
  catch(e){
      console.error(e)
      console.error("Error parsing WebSocket message:", event);  
      return
    }

  };

};

// ==================


// --- LIFECYCLE ---

onMounted( async () => {

  //console.log("main onMounted")

  initWebSocket();

  initWebSocket_mulo();

  try {

        // tutte le  props

        await initProps();
        /*
        let pdata = await send_get("/api/props/find", {path : ""})
        //console.log(pdata)
        pdata.forEach(  (val) =>{
          //  console.log("prop",val.path, val.value)
            if (val.path.startsWith("chart")  
            || val.path.startsWith("home")
          || val.path.startsWith("symbols")
            || val.path.startsWith("event") )
            {
              staticStore.load(val.path, val.value);
            }
            else
            {
              liveStore.set(val.path, val.value);
            } 
        });
        */

        let grid = staticStore.get("home.grid","")
        if (grid!="")
        {
            //console.log("home.grid", grid)
            const [r, c] = grid.split("_").map(Number);
            setGrid(r,c)
        }
        
        await send_get("/api/report/get")
        await send_get("/api/event/get",{"limit":50, "types":  ['order','error','message']})
        //await send_get("/api/event/get")
        await send_get("/api/news/current")

        
        // positions
        /*
        response = await fetch('http://127.0.0.1:2000/account/positions')
        if (!response.ok) throw new Error('Errore nel caricamento')
        const pos_list = await response.json();
        //console.log(pos_list)
        pos_list.forEach(  (val) =>{
            //console.log(val)
            val["type"] = "POSITION"
            portfolioRef.value?.handleMessage(val);
        });
        */

        // orders

        let order_list = await send_get('/order/list')
        order_list.data.forEach(  (msg) =>{
            //console.log(val)
            let dataParsed =
              typeof msg.data === "string"
                ? JSON.parse(msg.data)
                : msg.data;
              dataParsed["timestamp"] = msg["timestamp"]
            eventBus.emit("order-received", dataParsed);
            //portfolioRef.value?.handleMessage(val);
        });

        order_list = await send_get('/order/task/list?onlyReady=true')
        order_list.data.forEach(  (msg) =>{
            msg.data= JSON.parse(msg.data)
            msg["ts"] = msg["timestamp"]*1000
            eventBus.emit("task-order-received", msg);
        });
        
        eventBus.emit("on-start", {});

        console.log("STARTED")

    } catch (err) {
        //errore.value = err.message
        console.error(err)
    } finally {
        //caricamento.value = false
    }
  
  eventBus.on("chart-select", onChartSelect);
    
});

onBeforeUnmount(() => {
    eventBus.off("chart-select", onChartSelect);
});


onUnmounted(() => {
  if (ws) ws.close();
});

</script>

<style scoped>
.top-menu{
  position:absolute;
}
.sub-bar{
  padding-left: 250px;
  padding-right: 10px;
  width: 100%;
  display: flex;
  background-color: rgb(204, 248, 248);
}
.selected {
  outline: 5px solid #fbff00;
  outline-offset: -5px;
  border-radius: 8px;
}

.charts-grid {
  width: 100%;
 /* height: 100%;*/
  padding: 6px;
  box-sizing: border-box;
  background-color: azure;
  padding-right: 10px;
}
.charts-grid > * {
  min-width: 0;
  min-height: 0;
  overflow: hidden;
}

.layout {
  display: flex;
  height: 90vh;
  position: absolute;
  top: 40px;
}
/* Sidebar */
.sidebar {
  width: 64px;
  background: #0f172a; /* blu scuro */
  display: flex;
  flex-direction: column;
  align-items: center;
  padding-top: 1rem;
}

/* Button */
.sidebar-btn {
  background: none;
  border: none;
  color: #e5e7eb;
  cursor: pointer;
  font-size: 1.2rem;
  padding: 0.75rem;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.sidebar-btn span {
  font-size: 0.7rem;
}

.sidebar-btn:hover {
  background: #1e293b;
  border-radius: 8px;
}

/* Main */
.content {
  flex: 1;
  overflow: hidden;
}
.main-columns {
  display: grid;
   grid-template-columns: 160px 190px 1fr 180px ;
  gap: 1px;
  flex: 1;
  
  margin-left: 68px;
  height: 200px;
  overflow: hidden;
}

/* opzionale: scrolling indipendente */
.two-columns > * {
  min-height: 100px;
}

.home {
  height: 100vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>