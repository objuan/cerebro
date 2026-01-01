
export const formatUnixDate = (unixTime) => {
  if (!unixTime) return '...';
  
  // Se è in secondi (es. 1735654560), moltiplica per 1000
  // Se è già in millisecondi, usalo così com'è
  const date = new Date(unixTime < 10000000000 ? unixTime * 1000 : unixTime);
  
  return date.toLocaleString(); // Formato locale: dd/mm/yyyy, hh:mm:ss
};