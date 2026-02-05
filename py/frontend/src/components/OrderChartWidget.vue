<template>
  <div ref="container" class="" style="overflow: hidden;" >
    
      <LineChart title="Gain 1m" ref="gain_1" />
      <LineChart title="Gain 5m" ref="gain_5" />
      <LineChart title="Gain 1h" ref="gain_1h" />
  </div>

  
</template>


<script setup>
import {  onMounted, onBeforeUnmount ,ref } from 'vue';
import { eventBus } from "@/components/js/eventBus";
import LineChart from "@/components/LineChart.vue";

let gain_1=ref(null)
let gain_5=ref(null)
let gain_1h=ref(null)


function onTickerOrderReceived(msg){
 // console.log("onTickerOrderReceived", msg)

  gain_1.value.update_data(msg.data.gain_1);
  gain_5.value.update_data(msg.data.gain_5);
  gain_1h.value.update_data(msg.data.gain_1h);

 // console.log("onTickerOrderReceived", gain_1)

}

onMounted(  () => {
  eventBus.on("ticker-order", onTickerOrderReceived);

});

onBeforeUnmount(() => {
  eventBus.off("ticker-order", onTickerOrderReceived);
});


</script>