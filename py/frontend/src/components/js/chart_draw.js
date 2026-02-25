//import {  send_post,generateGUID ,send_delete} from '@/components/js/utils.js'; // Usa il percorso corretto

export const handleSize=6

function parseColoredText(text, defaultColor){
  const regex = /<color:(#[0-9a-fA-F]{3,6}|[a-zA-Z]+)>|<\/color>/g;
  let result = [];
  let lastIndex = 0;
  let colorStack = [defaultColor];
  let match;

  while((match = regex.exec(text))){
    if(match.index > lastIndex){
      result.push({
        text: text.slice(lastIndex, match.index),
        color: colorStack[colorStack.length-1]
      });
    }

    if(match[0].startsWith("</color>")){
      if(colorStack.length > 1) colorStack.pop();
    } else {
      colorStack.push(match[1]);
    }

    lastIndex = regex.lastIndex;
  }

  if(lastIndex < text.length){
    result.push({
      text: text.slice(lastIndex),
      color: colorStack[colorStack.length-1]
    });
  }

  return result;
}

export function drawTextOnLine(
  ctx,
  a,
  b,
  text,
  color = "white",
  offset = 10,
  anchor = "center",
  bgColor = null,
  padding = 4,
  font = "15px Arial"
){
    if (!text) return
  const angle = Math.atan2(b.y - a.y, b.x - a.x);

  let origin;
  if(anchor === "left") origin = a;
  else if(anchor === "right") origin = b;
  else origin = { x:(a.x+b.x)/2, y:(a.y+b.y)/2 };

  ctx.save();
  ctx.translate(origin.x, origin.y);
  ctx.rotate(angle);

  ctx.font = font;
  ctx.textBaseline = "middle";

  // ⭐ parse colori
  const segments = parseColoredText(text, color);

  //console.log(text,segments)
  
  // ⭐ misura larghezza totale
  let totalWidth = 0;
  segments.forEach(s => {
    totalWidth += ctx.measureText(s.text).width;
  });

  const metrics = ctx.measureText("Mg");
  const height =
    (metrics.actualBoundingBoxAscent || 8) +
    (metrics.actualBoundingBoxDescent || 4);

  const y = -offset;

  let startX;
  if(anchor === "left"){
    ctx.textAlign = "left";
    startX = padding;
  }
  else if(anchor === "right"){
    ctx.textAlign = "left";
    startX = -totalWidth - padding;
  }
  else{
    ctx.textAlign = "left";
    startX = -totalWidth/2;
  }

  // ⭐ background unico
  if(bgColor){
    ctx.fillStyle = bgColor;
    ctx.fillRect(
      startX - padding,
      y - height/2 - padding,
      totalWidth + padding*2,
      height + padding*2
    );
  }

  // ⭐ draw segmenti
  let x = startX;
  segments.forEach(seg => {
    ctx.fillStyle = seg.color;
    ctx.fillText(seg.text, x, y);
    x += ctx.measureText(seg.text).width;
  });

  ctx.restore();
}
export function  drawLine(ctx, a,b,color, hover=false, size=1, style = "solid"   ){
      ctx.beginPath()
      if (style === "dotted") ctx.setLineDash([2, 4]);
      else if (style === "dashed") ctx.setLineDash([8, 6]);
      else ctx.setLineDash([]);

      ctx.moveTo(a.x,a.y)
      ctx.lineTo(b.x,b.y)
      ctx.strokeStyle = hover ? 'yellow' : color
      ctx.lineWidth = hover ? 2 : size
      ctx.stroke()
}
export function drawRect(ctx, a, b,color, fillColor,hover=false){
    const x = Math.min(a.x, b.x)
    const y = Math.min(a.y, b.y)
    const w = Math.abs(b.x - a.x)
    const h = Math.abs(b.y - a.y)

    ctx.beginPath()
    ctx.rect(x, y, w, h)

    // riempimento
    ctx.fillStyle = fillColor
    ctx.fill()

    // bordo
    ctx.strokeStyle = hover ? 'yellow' : color
    ctx.lineWidth = hover ? 2 : 1
    ctx.stroke()
}

export function drawHandle(ctx,p,hover=false){
      ctx.beginPath()
      ctx.arc(p.x, p.y, handleSize, 0, Math.PI*2)
      ctx.fillStyle = hover ? 'green' : 'yellow'
      ctx.fill()
  }

export function hitLine(mouse, a, b, tolerance = 6){
      // lunghezza segmento
      const dx = b.x - a.x
      const dy = b.y - a.y

      const lenSq = dx*dx + dy*dy
      if(lenSq === 0) return false

      // proiezione del mouse sul segmento
      let t = ((mouse.x - a.x)*dx + (mouse.y - a.y)*dy) / lenSq

    
      // clamp sul segmento
      t = Math.max(0, Math.min(1, t))

      // punto più vicino sulla linea
      const px = a.x + t*dx
      const py = a.y + t*dy

      // distanza mouse → linea
      const dist = Math.hypot(mouse.x - px, mouse.y - py)

      return dist <= tolerance
    }

  export function hitHandle(mouse,p){
      return Math.hypot(mouse.x-p.x, mouse.y-p.y) <= handleSize+2
    }
