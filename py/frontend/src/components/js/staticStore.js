
const state = {}

const get = (path, defaultValue = null) => {
  const value = state[path]
  return value !== undefined ? value : defaultValue
}
const set = (path, data) => {
  
  state[path] = data;
  //console.log(state,path,data)
};
// Esponiamo i dati come readonly per evitare modifiche accidentali dai componenti
export const staticStore = {
  set,
  get
};