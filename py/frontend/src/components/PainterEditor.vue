:::writing{variant="standard" id="48291"}
<template>
  <div v-if="obj" class="painter-overlay" @click.self="close">
    <div class="painter-modal">
      <h3>Edit {{ obj.type }}</h3>

      <div v-for="p in obj.props()" :key="p" class="row-field">

  <label class="field-label">{{ p }}</label>

  <div class="field-editor">

    <!-- COLOR -->
    <input
      v-if="p==='color'"
      type="color"
      v-model="obj[p]"
    />

    <!-- TEXT OBJECT -->
    <div v-else-if="p==='text'">
      <div v-for="tp in obj.text.props()" :key="tp" class="row-field">

        <label class="field-label">{{ tp }}</label>

        <div class="field-editor">

          <input
            v-if="tp==='color' || tp==='bgColor'"
            type="color"
            v-model="obj.text[tp]"
          />
          <input
              v-if="tp==='color' || tp==='bgColor'"
              type="range"
              min="0"
              max="1"
              step="0.01"
              v-model="obj.text[tp + 'Alpha']"
            />
          <select v-else-if="tp==='align'" v-model="obj.text.align">
            <option>left</option>
            <option>center</option>
            <option>right</option>
          </select>

          <input
            v-else
            type="text"
            v-model="obj.text[tp]"
          />

        </div>
      </div>
    </div>

    <!-- DEFAULT -->
    <input
      v-else
      v-model="obj[p]"
    />

  </div>
</div>

      <div class="buttons">
        <button class="btn btn-danger" @click="del">Delete</button>
        <button class="btn btn-success" @click="close">Save</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue"

const obj = ref(null)

function open(e){
  obj.value = e.detail
}
function del(){
  obj.value.delete()
  obj.value = null
}
function close(){
  obj.value.save()
  obj.value = null
}

function esc(e){
  if(e.key === "Escape") close()
}

onMounted(()=>{
  window.addEventListener("edit-object", open)
  window.addEventListener("keydown", esc)
})

onUnmounted(()=>{
  window.removeEventListener("edit-object", open)
  window.removeEventListener("keydown", esc)
})
</script>

<style scoped>

.row-field{
  display:grid;
  grid-template-columns: 90px 1fr;
  align-items:center;
  gap:8px;
  margin:6px 0;
}

.field-label{
  font-size:12px;
  opacity:.8;
}

.field-editor input,
.field-editor select{
  width:100%;
}

.painter-overlay{
  position:fixed;
  inset:0;
  background:rgba(0, 0, 0, 0.01);
  display:flex;
  align-items:center;
  justify-content:center;
  z-index:9999;
}

.painter-modal{
  background:#1e1e1e;
  color:white;
  padding:20px;
  border-radius:10px;
  border-color: white;
  border-style: solid;
  min-width:280px;
  max-width:90vw;
  box-shadow:0 20px 60px rgba(0,0,0,.1);
  position:relative;
  z-index:10000;
}

.field{
  margin:10px 0;
  display:flex;
  flex-direction:column;
}

.buttons{
  margin-top:15px;
  display:flex;
  justify-content:flex-end;
}
</style>
:::