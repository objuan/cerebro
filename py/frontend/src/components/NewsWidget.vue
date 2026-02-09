<template>
  <div class="overlay" @click.self="$emit('close')">

  <div class="div-modal">
    <button class="close" @click="$emit('close')">✖</button>
     

        <div class="language-bar">
            <h3>{{ symbol }}</h3>

          <button
            :class="{ active: language === 'en' }"
            @click="language = 'en'"
          >
            English
          </button>

          <button
            :class="{ active: language === 'it' }"
            @click="language = 'it'"
          >
            Italiano
          </button>

      </div>
      
      <div class="news-wrapper" v-if="news_list">

        <div class="modal-scroll">
       
          <div
                v-for="news in news_list"
                :key="news"
                class="cell"
         >

            <!-- MAIN NEWS -->
            <div class="main-news">
              <img :src="proxyImage(news.image)" class="main-image" />

              <div class="content">

                 <p class="meta">
                  {{ formatDate(news.published_at) }} · {{ news.source }}
                </p>

                <h5 class="title">
                  <a
                    :href="news.url"
                    target="_other"
                    :title="news.url"
                  >
                   ({{ news.days_passed }}) {{ t(news.title) }}
                  </a>
                </h5>

                 <p class="desc">{{ t(news.summary) }}</p>

  
              </div>
            </div>

            <!-- SIMILAR NEWS -->
            <div v-if="news.similar && news.similar.length" class="similar-section">
              <h3>Similar News</h3>

              <div
                v-for="item in news.similar"
                :key="item.uuid"
                class="similar-card"
              >
                <img :src="item.image_url" class="thumb" />

                <div class="similar-content">
                  <a :href="item.url" target="_blank" class="similar-title">
                    {{ item.title }}
                  </a>

                  <p class="similar-meta">
                    {{ formatDate(item.published_at) }} · {{ item.source }}
                  </p>
                </div>
              </div>

            </div>
            </div>
        </div>
      </div>
  </div>
   </div>
  
</template>

<script setup>

import {  ref ,watch, toRef ,reactive  } from 'vue';
import { newsStore } from "@/components/js/newsStore";
import { Translate }from "@/components/js/utils";

const props = defineProps({
  symbol: { type: String, default: '' },
});

const symbol = toRef(props, 'symbol');

const news_list = ref(null)

const language = ref("en")
const translations = reactive({});

function load(){
  
  let list = newsStore.get_news(symbol.value)
   console.log("load",symbol.value,list)
   news_list.value=null
  if (list)
  {
    if (list.length>0)
    
      news_list.value=list
  }
}
function proxyImage(url){
  return `http://localhost:8000/img-proxy?WHERE=${encodeURIComponent(url)}`
}

function  formatDate(unixSeconds) {
     return new Date(unixSeconds * 1000).toLocaleString();
}
    

async function getText(txt) {
  if (language.value !== "it") return txt;

  // Se già tradotto, usa cache
  if (translations[txt]) return translations[txt];

  // Altrimenti traduci e salva
  translations[txt] = await Translate(txt);
  return translations[txt];
}

function t(txt) {
   if (language.value !== "it") return txt;
   
  if (!translations[txt]) {
    getText(txt); // parte async in background
    return txt;
  }
  return translations[txt];
}

watch(symbol, load, { immediate: true });

</script>

<style scoped>

.language-bar{
  display:flex;
  align-items:center;
  gap:2px;
  padding:2px 2px;
  font-size:13px;
  background:#747474;
  color:white;
  border-bottom:2px solid #333;
}

.language-bar button{
  border:1px solid #555;
  background:#0f1185;
  color:#ccc;
  padding:3px 2px;
  border-radius:4px;
  cursor:pointer;
}
.language-bar button.active{
  background:#00e676;
  color:#000;
  font-weight:700;
}


.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0,0,0,0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 9999;
}

.div-modal {
  background: white;
  width: 900px;
  
  max-height: 700px;        
  border-radius: 10px;
  padding: 20px;
  position: relative;
  display: flex;
  flex-direction: column;
}

.modal-scroll {
 
  height: 90%;
  margin-top: 10px;
  padding-right: 10px;
  flex: 1;               /* prende tutto lo spazio */
}

.close {
  position: absolute;
  top: 10px;
  right: 10px;
  border: none;
  background: none;
  font-size: 20px;
  cursor: pointer;
}

.news-wrapper {
  max-width: 900px;
   overflow-y: auto;
  height: 100%;
  margin: auto;
  font-family: Arial, sans-serif;
}

.main-news {
  display: flex;
  gap: 10px;
  margin-bottom: 10px;
}

.main-image {
  width: 200px;
  /*height: 10px;*/
  object-fit: cover;
  border-radius: 8px;
}

.content {
  flex: 1;
}

.title {
  margin: 0 0 10px;
}

.title a {
  text-decoration: none;
  color: #222;
}

.meta {
  font-size: 0.9em;
  color: #777;
  margin-bottom: 10px;
}

.snippet {
  color: #444;
}
.snippet {
  color: #131313;
}

.similar-section h3 {
  margin-bottom: 15px;
}

.similar-card {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 6px;
}

.thumb {
  width: 90px;
  height: 60px;
  object-fit: cover;
  border-radius: 4px;
}

.similar-title {
  font-weight: bold;
  color: #333;
  text-decoration: none;
}

.similar-meta {
  font-size: 0.8em;
  color: #888;
}
</style>
