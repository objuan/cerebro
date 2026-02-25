<template>
    <div>
        <h2>Profiles</h2>

        <div
      v-for="profile in profiles"
      :key="profile.name"
      class="profile-card"
    >
      <div class="header" @click="toggle(profile.name)">
        <strong>{{ profile.name }}</strong>
        <span>{{ opened === profile.name ? '▲' : '▼' }}</span>
          <button
          class="btn btn-sm btn-primary"
          @click="forceScan(profile.name)"
        >
          Force Call
        </button>
      </div>

      <pre v-if="opened === profile.name">
{{ formatJson(profile) }}
      </pre>
    </div>

  </div>
</template>

<script setup>

import {onMounted,ref} from 'vue';
import {  send_get } from '@/components/js/utils.js'; // Usa il percorso corretto
const opened = ref(null)
const profiles = ref(null)


function toggle(name) {
  opened.value = opened.value === name ? null : name
}

function formatJson(obj) {
  return JSON.stringify(obj, null, 2)
}


function forceScan(profile_name){
  send_get("/api/admin/scan",{"profile_name":profile_name})
}
  

onMounted(async () => {
   profiles.value = await send_get("/api/admin/scan/profiles")
 //  console.log(profiles.value)
})


</script>


<style scoped>
.container {
  padding: 20px;
  max-width: 800px;
}

.profile-card {
  border: 1px solid #333;
  margin-bottom: 10px;
  border-radius: 6px;
  background: #111;
  color: #ddd;
}

.header {
  padding: 10px;
  cursor: pointer;
  display: flex;
  justify-content: space-between;
  background: #222;
}

pre {
  padding: 10px;
  margin: 0;
  background: #000;
  overflow-x: auto;
}
</style>