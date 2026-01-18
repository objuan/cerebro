import { reactive } from 'vue';
//import { readonly } from 'vue';

// Stato privato reattivo
const state = reactive({
  dataByPath: {} // Chiave: path, Valore: dati del messaggio
});

// Funzione helper per aggiornare i dati (chiamata dal WebSocket)
const updatePathData = (path, data) => {
  
  state.dataByPath[path] = data;
  //console.log(state,path,data)
};
const set = (path, data) => {
  
  state.dataByPath[path] = data;
  //console.log(state,path,data)
};
// Esponiamo i dati come readonly per evitare modifiche accidentali dai componenti
export const liveStore = {
  state,//state: readonly(state),
  updatePathData,
  set
};