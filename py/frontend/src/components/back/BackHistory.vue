<template>
  <div v-if="backTest.history_list">
      <table style="width: 100%;">
        <tr>
          <td style="width: 50%;">
            <table style="width: 100%;">
                    <tr>
                      <td>
                          Run At
                      </td>
                      <td>
                          Strategy
                      </td>
                      <td>
                          From
                      </td>
                      <td>
                          To
                      </td>
                      <td>
                          Win/Loss
                      </td>
                      <td>
                          Gain
                      </td>
                    </tr>
                    <tr v-for="item in backTest.history_list"
                      @click="select(item)"
                      :key="item.id" 
                      >
                      <td>
                        {{ item.ds_timestamp }} 
                      </td>
                      <td>
                        {{ item.strategy }} 
                      </td>
                      <td>
                          {{ item.dt_from }}
                      </td>
                      <td>
                          {{ item.dt_to }}
                      </td>
                        <td>
                          {{ item.win }}/{{ item.loss }}
                      </td>
                        <td>
                          {{ Math.trunc(item.totalGain) }}%
                      </td>
                    </tr>

                  </table>
          </td>
          <td>
                <div v-if="selectedTrade && symbol" style="background-color: aquamarine;">
                   {{selectedTrade.ds_timestamp}} {{symbol}}  <button @click="open_script()">Script</button>
<br>
                   {{ backTest.in_data.params }}

                   <table style="width: 100%;">
                    <tr>
                      <td>
                          Symbol
                      </td>
                      <td>
                          Quantity
                      </td>
                      <td>
                          Buy
                      </td>
                      <td>
                          Sell
                      </td>
                      <td>
                          Gain
                      </td>
                    </tr>
                   <tr v-for="item in backTest.trades.filter(t => t.symbol === props.symbol)"
                      :key="item.id" 
                      >
                      <td>
                        {{ item.symbol }} 
                      </td>
                       <td>
                          {{ item.quantity }}
                      </td>
                      <td>
                          <b>{{ item.entry_price }}</b> {{ new Date(item.entry_datetime).toLocaleTimeString('it-IT', {
  hour: '2-digit',
  minute: '2-digit'
})}}
                      </td>
                      <td>
                          <b>{{ item.exit_price }}</b>
                           {{ new Date(item.exit_datetime).toLocaleTimeString('it-IT', {
  hour: '2-digit',
  minute: '2-digit'
})}}
                      </td>
                        <td>
                          {{ item.gain }}
                      </td>

                    </tr>
                   </table>

                </div> 
          </td>
        </tr>
      </table>
     

  </div>
</template>

<script setup>

import {backTest} from "@/components/back/backtest";
import { ref } from "vue"


const props = defineProps({

  symbol : { type: String, required: true, default: null },
});


const selectedTrade = ref(null) 


const emit = defineEmits(["select"])

function open_script()
{
 backTest.getStrategyScript().then(script => {
  const w = window.open(
    "",
    "strategyPopup",
    "width=2048,height=800,resizable=yes,scrollbars=yes"
  );

  if (!w) {
    alert("Popup bloccato dal browser");
    return;
  }

  w.document.write(`
    <html>
      <head>
        <title>Strategy Script</title>
        <style>
          body {
            font-family: monospace;
            padding: 10px;
            background: #111;
            color: #EEE;
          }
          pre {
            white-space: pre-wrap;
            word-wrap: break-word;
          }
        </style>
      </head>
      <body>
        <pre>${script}</pre>
      </body>
    </html>
  `);

  w.document.close();
});
}

function select(item){
    selectedTrade.value = item
    emit('select', item)  
}
</script>


<style scoped>

</style>
