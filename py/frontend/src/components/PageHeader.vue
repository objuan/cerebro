<template>
  <header class="py-1 mb-1 border-bottom bg-light">
    <div class=" d-flex align-items-center justify-content-between">


      <h1 class="h3 mb-0 text-primary">
        <router-link to="/">
    {{ title }}
    </router-link>

    
      </h1>
      
       <div>
       DAY PNL  <strong>{{ tradeStore.day_PNL.toFixed(2) }} $</strong> 
        (# {{ tradeStore.total }} )
      </div>
      <div>WIN/LOSS <strong>{{ tradeStore.win  }}/{{ tradeStore.loss  }}</strong></div>

      <span>
        Ultimo aggiornamento:
         {{ liveData['root.clock'] ? formatUnixDate(liveData['root.clock']) : '...' }}
      </span>
      
      <div class="text-end">
          <span :class="['badge rounded-pill', marketStatus.color]">
          <i class="bi bi-circle-fill me-1 small"></i> {{ marketStatus.label }}
        </span>
      </div>

      <div class="text-end">
             <span :class="['badge rounded-pill', symStatus.color]">
                <i class="bi bi-circle-fill me-1 small"></i> {{ symStatus.label }}
              </span>
      </div>

      <div class="ms-3 d-flex align-items-center gap-2">
        <span class="fw-semibold small">Start</span>

        <input
          type="time"
          class="form-control form-control-sm"
          v-model="selectedSymTime"
          :disabled="!selectedSymTime"
          style="width: 110px"
        />

        <button
          class="btn btn-sm btn-primary"
          @click="onSetSymTime"
          :disabled="!selectedSymTime"
        >
          Set
        </button>
        <input
            type="range"
            class="form-range"
            min="0"
            max="20"
            step="1"
            v-model.number="symSpeed"
            @change="onSetSymSpeed"
            style="width: 140px"
          />

          <span class="badge bg-secondary" style="min-width: 32px">
            {{ symSpeed }}
          </span>
        <span class="fw-semibold small">Speed</span>
      </div>
    </div>
  </header>
</template>

<script setup>
import { computed,ref,onMounted,watch } from 'vue';
import { liveStore } from '@/components/js/liveStore.js'; // Assicurati che il percorso sia corretto
import { formatUnixDate ,formatForTimeInput,mergeDateWithTime, send_get } from '@/components/js/utils.js'; // Usa il percorso corretto
import { tradeStore } from "@/components/js/tradeStore";

const selectedSymTime = ref(null);
const symSpeed = ref(null)

// Esponiamo i dati dello store al template
const liveData = computed(() => liveStore.state.dataByPath);

const marketStatus = computed(() => {
  const tz = liveStore.state.dataByPath['root.tz'];
  
  // Mappatura degli stati
  switch (tz) {
    case 0:
      return { label: 'Chiuso', color: 'bg-danger' };
    case 1:
      return { label: 'Pre-Market', color: 'bg-warning text-dark' };
    case 2:
      return { label: 'Aperto', color: 'bg-success' };
    case 3:
      return { label: 'After-Hours', color: 'bg-info text-dark' };
    default:
      return { label: 'Offline', color: 'bg-secondary' };
  }
});

const symStatus = computed(() => {
   const sym_mode = liveStore.state.dataByPath['root.sym_mode'];
   //console.log("sym_mode",sym_mode)
   if (sym_mode)
      return { label: 'Sym', color: 'bg-danger' };
  else
      return { label: 'Live', color: 'bg-success' };
})



function onSetSymTime() {
  if (!selectedSymTime.value) return;
  
  const baseUnix = liveData.value['root.sym_start_time'];
  if (!baseUnix) {
    console.warn('root.sym_start_time mancante');
   
    return;
  }

  const unixTime = mergeDateWithTime(baseUnix, selectedSymTime.value);
  if (unixTime !== baseUnix) {
      liveStore.set('root.sym_start_time', unixTime);
    
      console.log('Set SYM start time:', unixTime);

      send_get("/sym/time/set",{"time" : unixTime*1000})
  }
  
}

function onSetSymSpeed() {
  //console.log('SYM speed:', symSpeed.value);
  //liveStore.set('root.sym_speed', symSpeed.value);

   send_get("/sym/speed/set",{"value" : symSpeed.value})
}

defineProps({
  title: {
    type: String,
    default: 'Dashboard Cerebro'
  }
})

onMounted(() => {

});

watch(
  () => 
  {
    return liveData.value['root.sym_start_time']
  },
  v => {
     
     const date = new Date(v * 1000);
     // console.log("sym_start_time",date)
    if (v != null) selectedSymTime.value = formatForTimeInput(date);
  },  { immediate: true }
);

watch(
  () => liveData.value['root.sym_start_speed'],
  v => {
      //console.log("sym_speed",v)
      symSpeed.value= v;
  }, { immediate: true }
);

</script>


<style scoped>
/* Aggiungi qui eventuali personalizzazioni extra */
.text-primary {
  font-weight: 700;
}
</style>

<script>
import axios from 'axios';

export default {
  name: 'PageHeader',
  data() {
    return {
      msg: '',
    };
  },
  methods: {
    getMessage() {
      axios.get('/')
        .then((res) => {
          this.msg = res.data;
        })
        .catch((error) => {
          console.error(error);
        });
    },
  },
  created() {
    //this.getMessage();
  },
};
</script>