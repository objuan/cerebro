<template>
  <div class="home">

    <PageHeader title="Cerebro V0.1" style="margin-left: 30px;margin-right: 30px;"/>
 
    <div class="d-flex flex-wrap gap-1 items-container">

      <div
        v-for="item in sortedTickers"
        :key="item.symbol"
        class="card ticket-card"
      >
        <div class="card-body p-2 d-flex justify-content-between align-items-center">
          
         
            <div class="fw-bold">
                <a href="#" class="text-blue-600 hover:underline" @click.prevent="onSymbolClick(item.symbol)">
                      {{ item.symbol }}
                    </a>

            </div>
          </div>
      </div>

    </div>

  </div>
</template>

<script setup>
import { computed} from 'vue';
import PageHeader from '@/components/PageHeader.vue'
import { tickerStore as tickerList } from "@/components/js/tickerStore";

const sortedTickers = computed(() => {
  const list = tickerList.get_sorted();

  return [...list].sort((a, b) => {
    const av = a.report?.["symbol"] ?? 0;
    const bv = b.report?.["symbol"] ?? 0;
    return bv - av; // decrescente
  });
});


</script>

<style scoped>

</style>