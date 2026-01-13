<template>
  <div class="home">
    <PageHeader title="Cerebro V0.1"/>

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
        </aside>

        <!-- Main content -->
        <main class="content">
          <router-view />
        </main>

        <!-- Side panel -->
        <PortfolioWidget ref="portfolioRef" />

        <OrdersWidget ref="ordersRef" />

      </div>

    <main class="container">

      <trade-config></trade-config>
      <TickersSummary ref="tickets_summary"></TickersSummary>

    
      <div class="grid-stack">
        <div 
          v-for="w in widgetList" 
          :key="w.id" 
          class="grid-stack-item"
          :data-gs-id="w.id"
          :data-gs-x="w.rect.x"
          :data-gs-y="w.rect.y"
          :data-gs-w="w.rect.w"
          :data-gs-h="w.rect.h"
        >
          <component 
            :is="getWidgetComponent(w.type)"
            :id="w.id"
            :ref="el => widgetRefs[w.id] = el"
            :symbol="w.data.symbol"
            :plot_config="w.data.plot_config"
            @initialized="registerChart"
            @close="removeWidget"
          />
        </div>
      </div>

      <div v-if="showPopup" class="custom-popup">
        <select v-model="selectedSymbolChoice">
          <option v-for="s in symbolsList" :key="s" :value="s">{{ s }}</option>
        </select>
        <br><br>
        <button @click="confirmPopup" class="btn btn-primary">OK</button>
        <button @click="showPopup = false" class="btn btn-secondary">Annulla</button>
      </div>

    </main>
  </div>
</template>

<script setup>
import { liveStore } from '@/components/js/liveStore.js';
import OrdersWidget from "@/components/OrdersWidget.vue";
import PortfolioWidget from "@/components/PortfolioWidget.vue";

import { onMounted, onUnmounted, ref ,nextTick } from 'vue';

import TickersSummary from '@/components/TickersSummary.vue'
import PageHeader from '@/components/PageHeader.vue'
import TradeConfig from '@/components/TradeConfig.vue'
import CandleChartWidget from '@/components/CandleChartWidget.vue';
import MultiCandleChartWidget from '@/components/MultiCandleChartWidget.vue';
import { send_get } from '@/components/js/utils';
import { eventBus } from "@/components/js/eventBus";

// --- STATO REATTIVO ---

const portfolioRef = ref(null);
const ordersRef = ref(null);

const showPopup = ref(false);
const symbolsList = ref([]);
const selectedSymbolChoice = ref('');
const widgetList = ref([]); // Array di oggetti { id, rect, data }
const widgetRefs = ref({})
const tickets_summary = ref(null)

// Riferimenti non reattivi (istanze tecniche)
let grid = null;
// --- LOGICA WEBSOCKET ---
let ws = null;

// crea un nuovo widget
const getWidgetComponent = (type) => {
  //console.log("crate" , type)
  switch (type) {
    case 'chart':
      return CandleChartWidget
    case 'multi_chart':
      return MultiCandleChartWidget
    default:
      return CandleChartWidget // fallback sicuro
  }
}

const initWebSocket_mulo = () => {
  ws = new WebSocket("ws://127.0.0.1:2000/ws/orders");
  ws.onmessage = (event) => {
   
    const msg = JSON.parse(event.data);
    //console.log(msg)
    switch (msg.type) {
         case "UPDATE_PORTFOLIO":
          portfolioRef.value?.handleMessage(msg);
          break
        case "POSITION":
          portfolioRef.value?.handleMessage(msg);
          break
        case "ORDER":
          ordersRef.value?.handleMessage(msg);
          break
    }
  }
};

const initWebSocket = () => {
  ws = new WebSocket("ws://127.0.0.1:8000/ws/live");

  ws.onmessage = (event) => {
    //console.log(event.data)
    const msg = JSON.parse(event.data);

    if (msg.path) {
      // Aggiornando liveData[path], Vue notifica tutti i componenti in ascolto
        liveStore.updatePathData(msg.path, msg.data);
    }

    switch (msg.type) {
    
      case "candle":
        {
          const componentInstance = widgetRefs.value[msg.id];
          if (componentInstance)
          {
            //console.log("WS CANDLE",msg.id,componentInstance) 
            componentInstance.on_candle(msg.data);  
          }
        }
        break;
      case "ticker":
        {
          //console.log("WS TICKER",msg.data);
          //for x in widgetRefs.value 
          
          for(var i=0;i<widgetList.value.length;i++)
          {
              const componentInstance = widgetRefs.value[widgetList.value[i].id];
              if (componentInstance!=null)
                  componentInstance.on_ticker(msg.data);  
          }
          eventBus.emit("ticker-received", msg.data);


        } 
        break
       case "props":
        {
          console.log("WS props",msg);
          //for x in widgetRefs.value 
          
           liveStore.updatePathData(msg.path, msg.value);

        } 
        break
      case "del":
        {
          /*
          const target = chart_list[msg.id];
          if (target) {
            grid.removeWidget(target.widget_ele);
            delete chart_list[msg.id];
          }
            */
       }
        break;
    }
  };
};

// --- FUNZIONI WIDGET (INTERFACCIA GRIDSTACK) ---

// Funzione chiamata quando un widget viene aggiunto via WS o caricamento iniziale
const addWidgetToDashboard = (id, rect, data,type) => {

 // console.log("addWidgetToDashboard",id,rect,data,type)

  widgetList.value.push({ id, rect, data ,type});
  
  // Aspettiamo che Vue renderizzi il componente nel DOM
  nextTick(() => {
    const el = document.querySelector(`[data-gs-id="${id}"]`);
    const componentInstance = widgetRefs.value[id];
    //console.log("el",componentInstance)
    
    if (el) {
      //grid.makeWidget(el);
      if (rect==null)  rect =  { w: 6, h: 5 }
      grid.addWidget(el, rect  );
      
      requestAnimationFrame(() => {
       // const h = el.clientHeight;
       // console.log('clientHeight:', h);
        //const container = el.querySelector(".chart-container");
       // const container = el.querySelector(".multi-chart-container");
        //console.log("container",coneltainer.clientWidth,el.clientHeight,container)
       // componentInstance.resize(container.clientWidth, container.clientHeight);
    });
     setTimeout(() => {
        const container = el.querySelector(".multi-chart-container");
        componentInstance.resize(container.clientWidth, container.clientHeight);
        // const h = container.clientHeight;
        //console.log('clientHeight1:', h);
        //chartObj.titleElement = document.getElementById(id+"_symbol");
      }, 1000);
    
    }
  });
};

const removeWidget = (id) => {
  const el = document.querySelector(`[data-gs-id="${id}"]`);
  if (el) {
    grid.removeWidget(el); // Rimuove da GridStack
    widgetList.value = widgetList.value.filter(w => w.id !== id); // Rimuove da Vue
  }
};

// Funzione chiamata dal componente quando il grafico è pronto
const registerChart = (chartInstance) => {

  console.debug(chartInstance);
  // Salviamo l'istanza (mainSeries, refresh, etc.) nella nostra mappa globale
  // Questo ci permette di fare: chart_map[symbol].mainSeries.update(...)
  //window.chart_list[chartInstance.id] = chartInstance;
  //window.chart_map[chartInstance.symbol] = chartInstance;
};

const addCandleWidget = (id, symbol, timeframe, plot_config, rect) => {

 addWidgetToDashboard(id,rect,{"symbol" : symbol,"timeframe":timeframe,"plot_config": plot_config} ,"chart");
};

const addMultiCandleWidget = (id, symbol,  plot_config, rect) => {

 addWidgetToDashboard(id,rect,{"symbol" : symbol,"plot_config": plot_config},"multi_chart");
};

const addReportWidget = (id, rect, data) => {
  const el = document.createElement("div");
  el.classList.add("grid-stack-item");
  
  el.innerHTML = `
    <div class="grid-stack-item-content">
      <div class="header grid-stack-handle d-flex justify-content-between p-1 bg-light border-bottom">
        <div class="header-title">
           📊 <span>${data.title || 'Report'}</span>
        </div>
        <button class="btn btn-sm btn-outline-danger border-0 close-btn" title="Chiudi">✕</button>
      </div>
      <div class="report-container p-2" style="overflow: auto; height: calc(100% - 40px);">
        <table id="${id}" class="table table-sm table-hover">
          </table>
      </div>
    </div>
  `;

  // Aggiungi alla griglia
  grid.addWidget(el, rect || { w: 4, h: 4 });

  // Inizializzazione logica report (funzione esterna in report.js)
  setTimeout(() => {
    /*
    if (window.createReport) {
      const reportObj = window.createReport(el, id, data);
      // Salviamo il riferimento nella nostra mappa per aggiornamenti futuri via WS
      report_map[id] = reportObj;
      
      // Listener per la chiusura
      el.querySelector('.close-btn').onclick = () => layout_closeWidget(id);
    } else {
      console.error("Funzione window.createReport non trovata!");
    }
      */
  }, 0);
};

// --- LIFECYCLE ---

onMounted(() => {

  //console.log("main onMounted")

  // Inizializza GridStack
  grid = window.GridStack.init({
    draggable: { handle: '.grid-stack-handle' },
    resizable: { handles: "e, se, s" },
    float: true
  });

  grid.on("resizestop", (e, el) => {
    //const container = el.querySelector(".chart-container");
    const container = el.querySelector(".multi-chart-container");
    let id = el.getAttribute("data-gs-id")
    const componentInstance = widgetRefs.value[id];
    //console.log("resizestop",container,id,".:",componentInstance,"..");
    if (container && componentInstance) {
      componentInstance.resize(container.clientWidth, container.clientHeight);
      //const obj = chart_list[container.id];
      //obj.charts[0].resize(container.clientWidth, container.clientHeight);
    }
  });

  initWebSocket();

  initWebSocket_mulo();

  const loadLayout = async () => {
  try {
      //console.log("LOAD LAYOUT")
      let response = await fetch('http://127.0.0.1:8000/api/layout/select')
      if (!response.ok) throw new Error('Errore nel caricamento')
        const data = await response.json();
        const msgs = JSON.parse(data["data"]);

        //console.log("LOAD LAYOUT OK",msgs)
        msgs.forEach(msg => {
            if (msg.widget.type === "chart") {
              addCandleWidget(msg.id, msg.widget.symbol, msg.widget.timeframe, msg.widget.plot_config, msg.rect);
              
            } 
            else if (msg.widget.type === "multi_chart") {
              addMultiCandleWidget(msg.id, msg.widget.symbol,  msg.widget.plot_config, msg.rect);
              
            } else if (msg.widget.type === "report") {
              addReportWidget(msg.id, msg.rect, msg.widget);
            }
        });

        // tutte le  props
        let pdata = await send_get("/api/props/find", {path : ""})
        //console.log(pdata)
        pdata.forEach(  (val) =>{
            //console.log(val.path, val.value)
            liveStore.updatePathData(val.path, val.value);
        });
        
        // positions

        response = await fetch('http://127.0.0.1:2000/account/positions')
        if (!response.ok) throw new Error('Errore nel caricamento')
        const pos_list = await response.json();
        //console.log(pos_list)
        pos_list.forEach(  (val) =>{
            //console.log(val)
            val["type"] = "POSITION"
            portfolioRef.value?.handleMessage(val);
        });

        // orders

        response = await fetch('http://127.0.0.1:2000/order/list')
        if (!response.ok) throw new Error('Errore nel caricamento')
        const order_list = await response.json();
        order_list.data.forEach(  (val) =>{
            //console.log(val)
            val["type"] = "ORDER"
            ordersRef.value?.handleMessage(val);
            //portfolioRef.value?.handleMessage(val);
        });

    } catch (err) {
        //errore.value = err.message
        console.error(err)
    } finally {
        //caricamento.value = false
    }
  }

  loadLayout();
  
  
  function saveLayout() {
    const layout = grid.save(false); // false = senza DOM
    //console.log("saveLayout",layout)
    if (layout.length !=widgetList.value.length )
    {
      alert("ATTENZIONE LEN WINDGET");
        return;
    }

    
    //alert(widget_list.length);
    let save=[]
    for(var i=0;i<widgetList.value.length;i++)
    {
      const componentInstance = widgetRefs.value[widgetList.value[i].id];
      //console.log("save",componentInstance.save())
      save.push({"id": widgetList.value[i].id, "rect": layout[i],"type" : widgetList.value[i].type, "data": componentInstance.save()}) 
      
    }

    //console.log(save)
    fetch(`http://127.0.0.1:8000/api/layout/save`,
    {
      method: 'POST', 
      headers: { 'Content-Type': 'application/json'},
      body:  JSON.stringify(save)
    }).then(response => {
          if (!response.ok) {
              throw new Error(`Errore HTTP! Stato: ${response.status}`);
          }
      });
    
    //localStorage.setItem("grid-layout", JSON.stringify(layout));
  }
  grid.on("change", saveLayout);
  /*
  grid.on('added', (event, items) => {
      items.forEach(item => {
        const el = item.el;
        const h = el.clientHeight;
        console.log('added height:', h);
      });
  
  });    */
    
});

onUnmounted(() => {
  //console.log("main onUnmounted")
  if (ws) ws.close();
});
</script>

<style scoped>
.dashboard-container { position: relative; width: 100%; height: 100vh; }
.custom-popup {
  position: fixed; top: 50%; left: 50%;
  transform: translate(-50%, -50%);
  border: 1px solid #ccc; padding: 20px;
  z-index: 1000; background: white;
  box-shadow: 0 4px 15px rgba(0,0,0,0.2);
}
.grid-stack { background: #f4f4f4; min-height: 500px; }
:deep(.grid-stack-item-content) { background: white; border: 1px solid #ddd; }


.layout {
  display: flex;
  height: 100vh;
  position: absolute;
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
  overflow: auto;
}

</style>