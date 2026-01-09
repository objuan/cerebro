
export const formatUnixDate = (unixTime) => {
  if (!unixTime) return '...';
  
  // Se è in secondi (es. 1735654560), moltiplica per 1000
  // Se è già in millisecondi, usalo così com'è
  const date = new Date(unixTime < 10000000000 ? unixTime * 1000 : unixTime);
  
  return date.toLocaleString(); // Formato locale: dd/mm/yyyy, hh:mm:ss
};

export function lerp(a, b, f) {
    return a + (b - a) * f;
}

export  function interpolateColor(start, end, f) {
  
    const s = start.match(/\w\w/g).map(x => parseInt(x, 16));
    const e = end.match(/\w\w/g).map(x => parseInt(x, 16));

    const r = Math.round(lerp(s[0], e[0], f));
    const g = Math.round(lerp(s[1], e[1], f));
    const b = Math.round(lerp(s[2], e[2], f));

    return `rgb(${r}, ${g}, ${b})`;
}
export function formatValue(v) {
    v = parseFloat(v);
    if (isNaN(v)) return v;

    if (v >= 1_000_000) {
        return (v / 1_000_000).toFixed(1) + ' M';
    }
    if (v >= 1_000) {
        return (v / 1_000).toFixed(1) + ' K';
    }
    return v.toString();
}

