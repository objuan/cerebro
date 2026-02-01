import 'bootstrap/dist/css/bootstrap.min.css'
import 'bootstrap/dist/js/bootstrap.bundle.min.js'

import { createApp } from 'vue'
import axios from 'axios';

import App from './App.vue'
import router from './router'


const app = createApp(App);

axios.defaults.withCredentials = false;
axios.defaults.baseURL = 'http://localhost:3000/';  // the FastAPI backend

app.use(router);
app.mount("#app");

//createApp(App).use(router).mount('#app')
//https://testdriven.io/blog/developing-a-single-page-app-with-fastapi-and-vuejs/