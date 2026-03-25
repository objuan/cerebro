import {saveProp} from '@/components/js/utils.js'

const state = {};
const listeners = {};   // 👈 eventi

const emit = (event, payload) => {
  if (!listeners[event]) return;
  listeners[event].forEach(cb => cb(payload));
};

const on = (event, cb) => {
  if (!listeners[event]) listeners[event] = [];
  listeners[event].push(cb);
};

const off = (event, cb) => {
  if (!listeners[event]) return;
  listeners[event] = listeners[event].filter(l => l !== cb);
};

const get = (path, defaultValue = null) => {
  const value = state[path];
  return value !== undefined ? value : defaultValue;
};

const set = (path, data) => {
  state[path] = data;

  saveProp(path, data);

  emit(path, data);       // 👈 evento specifico per key
  emit("change", {path, data}); // 👈 evento globale
};

const load = (path, data) => {
  state[path] = data;
  //console.log("load",path,data)
  emit(path, data);       // 👈 evento specifico per key
  emit("change", {path, data}); // 👈 evento globale
};

export const staticStore = {
  set,
  get,
  load,
  on,
  off
};