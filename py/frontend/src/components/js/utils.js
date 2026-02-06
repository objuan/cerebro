
export const formatUnixDate = (unixTime) => {
  if (!unixTime) return '...';
  
  // Se è in secondi (es. 1735654560), moltiplica per 1000
  // Se è già in millisecondi, usalo così com'è
  const date = new Date(unixTime < 10000000000 ? unixTime * 1000 : unixTime);
  
  return date.toLocaleString(); // Formato locale: dd/mm/yyyy, hh:mm:ss
};

export const formatUnixTimeOnly = (unixTime) => {
  if (!unixTime) return '...';
  
  // Gestione secondi vs millisecondi
  const date = new Date(unixTime < 10000000000 ? unixTime * 1000 : unixTime);
  
  // Restituisce solo l'ora nel formato locale (es. 14:30:15)
  return date.toLocaleTimeString([], { 
    hour: '2-digit', 
    minute: '2-digit', 
    second: '2-digit',
    hour12: false // Forza il formato 24 ore
  });
};

export function formatTime(t) {
  return new Date(t).toLocaleTimeString();
}


export function lerp(a, b, f) {
    return a + (b - a) * f;
}

export  function interpolateColor(start, end, f,a) {
  
    const s = start.match(/\w\w/g).map(x => parseInt(x, 16));
    const e = end.match(/\w\w/g).map(x => parseInt(x, 16));

    const r = Math.round(lerp(s[0], e[0], f));
    const g = Math.round(lerp(s[1], e[1], f));
    const b = Math.round(lerp(s[2], e[2], f));

    return `rgba(${r}, ${g}, ${b},${a})`;
}

export function scaleColor(value, min, max) {
  if (value === null || value === undefined) return {}

  const clamped = Math.min(Math.max(value, min), max)
  const t = (clamped - min) / (max - min || 1)

  // verde ↔ rosso
  const r = Math.round(255 * (1 - t))
  const g = Math.round(255 * t)

  return {
    backgroundColor: `rgba(${r}, ${g}, 0, 0.15)`
  }
}

export function formatNumber(value) {
  if (value === null || value === undefined) return '-'
  return new Intl.NumberFormat('en-US').format(value)
}
export function formatValue(v,decimals=1) {
    v = parseFloat(v);
    if (isNaN(v)) return v;

    if (v >= 1_000_000) {
        return (v / 1_000_000).toFixed(1) + ' M';
    }
    if (v >= 1_000) {
        return (v / 1_000).toFixed(1) + ' K';
    }
    return v.toFixed(decimals).toString();
}

export function pointToSegmentDistance(px, py, x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;

    if (dx === 0 && dy === 0) {
        return Math.hypot(px - x1, py - y1);
    }

    const t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy);
    const clamped = Math.max(0, Math.min(1, t));

    const cx = x1 + clamped * dx;
    const cy = y1 + clamped * dy;

    return Math.hypot(px - cx, py - cy);
}
export async function send_mulo_get(url, params = {}) {
    const query = new URLSearchParams(params).toString();

    const res = await fetch(
        "http://localhost:3000" + url + (query ? `?${query}` : ""),
        {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        }
    );

    if (!res.ok) {
        throw new Error("Errore nella GET");
    }

    return await res.json();
}


export async function send_mulo_post(url, payload) {

    let res = await fetch("http://localhost:3000"+url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        throw new Error("Errore nel salvataggio chart line");
    }
    return await res.json();
}

export async function send_post(url, payload) {

    let res = await fetch("http://localhost:8000"+url, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    if (!res.ok) {
        throw new Error("Errore nel salvataggio chart line");
    }

    return await res.json();
}
export async function send_delete(url, payload = null) {
    const options = {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
    };

    // opzionale: body (non tutti i backend lo usano)
    if (payload) {
        options.body = JSON.stringify(payload);
    }

    const res = await fetch("http://localhost:8000" + url, options);

    if (!res.ok) {
        throw new Error("Errore nella DELETE");
    }

    return await res.json();
}

export async function send_get(url, params = {}) {
    const query = new URLSearchParams(params).toString();

    const res = await fetch(
        "http://localhost:8000" + url + (query ? `?${query}` : ""),
        {
            method: "GET",
            headers: { "Content-Type": "application/json" },
        }
    );

    if (!res.ok) {
        throw new Error("Errore nella GET");
    }

    return await res.json();
}

// ========================================


export async function Translate(phrase)
{
    let ret = await send_post("/api/translate",{"phrase": phrase})
    //console.log(phrase,ret.data);
    return ret.data;
}

// ==========================================

export async function saveChartLine(symbol, timeframe, data) {

    let res = await fetch("http://localhost:8000/api/chart/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            symbol,
            timeframe,
            data,
        }),
    });
    if (!res.ok) {
        throw new Error("Errore nel salvataggio chart line");
    }

    return await res.json();
}

export function generateGUID() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, c => {
        const r = Math.random() * 16 | 0;
        const v = c === "x" ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}


export function formatForDatetimeLocal(date) {
  const pad = (n) => String(n).padStart(2, '0');

  return (
    date.getFullYear() + '-' +
    pad(date.getMonth() + 1) + '-' +
    pad(date.getDate()) + 'T' +
    pad(date.getHours()) + ':' +
    pad(date.getMinutes())
  );
}

export function formatForTimeInput(date) {
  const pad = (n) => String(n).padStart(2, '0');

  return `${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function mergeDateWithTime(baseUnix, timeStr) {
  // baseUnix in secondi
  const date = new Date(baseUnix * 1000);

  const [hours, minutes] = timeStr.split(':').map(Number);

  date.setHours(hours, minutes, 0, 0);

  return Math.floor(date.getTime() / 1000);
}

export function saveProp(path,value){
    send_post('/api/props/save', { path: path, value: value });
}

// =====================


const _newsColors = ["#FF0000","#BBBB00","#0000ff"];

export const newsColor = (days)=>
    {
      return   _newsColors[Math.min(2,days)];
    }

//const symbolList = ref([]);
export const priceColor = (v) => {
  // clamp sicurezza
  v = Math.max(0, Math.min(1, Number(v) || 0))

  // bianco → verde acceso
  const start = { r: 255, g: 255, b: 255 }   // bianco
  const end   = { r: 0,   g: 230, b: 118 }   // #00e676

  const r = Math.round(start.r + (end.r - start.r) * v)
  const g = Math.round(start.g + (end.g - start.g) * v)
  const b = Math.round(start.b + (end.b - start.b) * v)

  return `rgb(${r}, ${g}, ${b})`
}
export const volumeRelColor = (v) => {
  // clamp sicurezza
  v = Math.max(0, Math.min(5, Number(v) || 0))

  // bianco → verde acceso
  const start = { r: 255, g: 255, b: 255 }   // bianco
  const end   = { r: 0,   g: 230, b: 118 }   // #00e676

  const r = Math.round(start.r + (end.r - start.r) * v)
  const g = Math.round(start.g + (end.g - start.g) * v)
  const b = Math.round(start.b + (end.b - start.b) * v)

  return `rgb(${r}, ${g}, ${b})`
}
