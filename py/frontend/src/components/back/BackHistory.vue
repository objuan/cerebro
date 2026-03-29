<template>
  <div v-if="backTest.history_list">

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
          @click="emit('select', item)"
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

  </div>
</template>

<script setup>

import {backTest} from "@/components/back/backtest";
const emit = defineEmits(["select"])

</script>


<style scoped>

</style>
