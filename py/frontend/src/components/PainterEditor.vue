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

       
          <!-- TEXT OBJECT (collapsible) -->
          <div v-else-if="p==='text'" class="text-block">
            <div class="text-header" @click="textOpen = !textOpen">
              <span>Text settings</span>
              <span>{{ textOpen ? '▾' : '▸' }}</span>
            </div>

            <div v-show="textOpen" class="text-body">
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
          </div>

          <!-- ALARMS -->
           
          <div v-else-if="p==='alarms'" class="text-block">
            <div class="text-header" @click="alarmsOpen = !alarmsOpen">
              <span>Alarms</span>
              <span>{{ alarmsOpen ? '▾' : '▸' }}</span>
            </div>

            <div v-show="alarmsOpen" class="text-body">
              <div class="row-field">
                <label class="field-label">Source</label>
                <div class="field-editor">
                  <select v-model="newAlarm.source">
                    <option value="last">last</option>
                    <option value="close">close</option>
                    <option value="low">low</option>
                    <option value="high">high</option>
                    
                    
                  </select>
                </div>
              </div>
              
              <div class="row-field">
                <label class="field-label">Type</label>
                <div class="field-editor">
                  <select v-model="newAlarm.type">
                    <option value="above">above</option>
                    <option value="below">below</option>
                  </select>
                </div>
              </div>

              <button class="btn btn-sm btn-warning" @click="addAlarm">Add alarm</button>
              
              <table style="width: 100%">
                <tr v-for="(a,i) in obj.alarms" :key="i" >
                  <td>
                    <label class="field-editor">on</label>
                  </td>
                  <td>
                  <div class="field-editor">
                    <span>{{ a.source }}</span>
                  </div>
                  </td>
                  <td>
                  <label class="field-label">{{ a.type }}</label>
                  </td>
                  <td>
                  <button class="btn btn-sm btn-danger ms-2" @click="obj.alarms.splice(i,1)">x</button>
                  </td>
                </tr>
              
            </table>
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
        <button class="btn btn-success" @click="close">OK</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from "vue"

const obj = ref(null)
const textOpen = ref(false)
const alarmsOpen = ref(true)

const newAlarm = ref({
  type: "above",
  source: "close"
})

function addAlarm(){
  if(!obj.value.alarms) obj.value.alarms = []
  obj.value.alarms.push({...newAlarm.value})
}

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
  align-items:begin;
  gap:8px;
  margin:6px 0;
}

.field-label{
  color : white;
  font-size:16px;
  opacity:1;
}

.field-editor{
color:white;
}
.field-editor input,
.field-editor select{
  width:100%;
    
}

.text-block{
  width:100%;
}

.text-header{
  display:flex;
  justify-content:space-between;
  cursor:pointer;
  background:rgba(199, 195, 195, 0.459);
  padding:6px;
  border-radius:6px;
}

.text-body{
  margin-top:6px;
  padding-left:6px;
  border-left:2px solid rgba(255,255,255,.2);
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
  background:rgba(0,0,0,.8);
    color:white;
  width: 400px;
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