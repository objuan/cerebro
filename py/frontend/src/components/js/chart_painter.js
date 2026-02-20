import { send_get,send_delete, send_post,generateGUID } from '@/components/js/utils.js'; // Usa il percorso corretto


export function  createPainter(context,mainChart,overlay) 
{
  return {
    context,
    overlay , 
    mainChart,
    active:false, drawing : false, start : null ,hovered:null,
    canvas_ctx : overlay.value.getContext('2d'), 
    lines : [],
    handleSize: 6,
    dragHandle: null,   // "p1" | "p2"
    dragLine: null

    ,async load(){
      //  console.log( "load")
      
      const ind_response = await send_get(`/api/chart/read`,
        {"symbol":this.context.currentSymbol.value,"timeframe":this.context.currentTimeframe.value  });
        //ind_response.data = JSON.parse(ind_response.data)
      this.lines.length=0;
      ind_response.map( data => {
            data.data = JSON.parse(data.data)
        //   console.log( data.data)

            if (data.data.type =="line"){

              const line =  { 
                  guid : data.guid,
                  p1 : data.data.p1,
                  p2: data.data.p2
                }
              //console.log( "load",line)
              this.lines.push(line)
            }
      })  
    }
    ,setChart(chart,series){
      this.chart=chart;
      this.series=series;

      this.overlay.value.addEventListener('mousedown', e => {
        this.onMouseDown(e);
      })

      this.overlay.value.addEventListener('mousemove', e => {
        this.onMouseMove(e);
      })

      this.overlay.value.addEventListener('mouseup', e => {
        this.onMouseUp(e);
      })

      this.mainChart.value.addEventListener('contextmenu', e=>{
        e.preventDefault() // blocca menu browser
        console.log('right click', e)
        this.onRightClick(e)
      })

    }
    ,save(line){
      send_post("/api/chart/save",
      {
          symbol: this.context.currentSymbol.value,
          timeframe: this.context.currentTimeframe.value,
          guid: line.guid,
          data: 
          {  
              "type": "line",
              "p1": line.p1,
              "p2":  line.p2,
              "color": '#ffcc00',
          }
        });
    }
    ,clear(){
      this.lines.length=0;
      this.redraw();
    }
    ,pixelToChart(pos){
      const logical = this.chart.timeScale().coordinateToLogical(pos.x)
      const price = this.series.coordinateToPrice(pos.y)
      return { x: logical, y: price }
    }
    ,pixelToChart1(pos){
      const xx = this.chart.timeScale().coordinateToTime(pos.x)
      const yy = this.series.coordinateToPrice(pos.y)
      return {x:xx, y:yy}
    }
    ,chartToPixel1(pos){
      const xx = this.chart.timeScale().timeToCoordinate(pos.x)
      const yy =  this.series.priceToCoordinate(pos.y)
      return {x:xx, y:yy}
    },
    chartToPixel(pos){
      const x = this.chart.timeScale().logicalToCoordinate(pos.x)
      const y = this.series.priceToCoordinate(pos.y)
      return { x, y }
    }
    ,begin(){
      //console.log("begin")
        this.active = true
        this.overlay.value.style.pointerEvents = 'auto'
    }
    ,end(){
      this.active = false
      this.overlay.value.style.pointerEvents = 'none'
    }
    ,getMouse(e){
      const rect = this.overlay.value.getBoundingClientRect()
      return { x: e.clientX - rect.left, y: e.clientY - rect.top }
    }
    ,resizeOverlay(){
      this.overlay.value.width = this.mainChart.value.clientWidth
      this.overlay.value.height = this.mainChart.value.clientHeight
      this.redraw()
    }
    ,onMouseDown(e){
    // console.log("mousedown",e)
      this.drawing=true
      this.start =  this.getMouse(e)
    }
    ,onMouseMove(e){
      if (!this.drawing) return
    // console.log("onMouseMove",e)
      if (this.dragHandle){
          //console.log("drag",e)

          const chartPos = this.pixelToChart( this.getMouse(e))
          this.dragLine[this.dragHandle] = chartPos
          //this.save(this.dragLine);
          this.redraw()
          return
      }
      else
          this.drawPreview(this.start, this.getMouse(e))
    }
    ,onMouseUp(e){
      this.drawing=false

      if (this.dragHandle){
        this.save(this.dragLine);
      }
      else{
      console.log("onMouseUp",e)
      // console.log("t",this.pixelToChart(this.getMouse(e)))

        const guid = generateGUID()
        const line =  { 
            guid : guid,
            p1 : this.pixelToChart(this.start),
            p2: this.pixelToChart(this.getMouse(e))
          }
          
        this.lines.push(line)
      
        this.save(line);
      }
      this.end()
      this.redraw()
    }
    ,onMouseClick_disabled(){
      if ( this.dragHandle){
        this.begin()
        this.drawing=true;
        return true;
      }
      else
        return false;
    }
    ,onMouseMove_disabled(mouse){

      this.hovered = null
      this.dragHandle=null
      
    //console.log("onMouseMove_disabled",mouse)

      this.lines.forEach(line=>{
        const a = this.chartToPixel(line.p1)
        const b = this.chartToPixel(line.p2)
      
        if(this.hitLine(mouse,a,b)){
          this.hovered = line
        }
      })

      if(this.hovered){
          const a = this.chartToPixel(this.hovered.p1)
          const b = this.chartToPixel(this.hovered.p2)

        if(this.hitHandle(mouse,a)){
          this.dragHandle = 'p1'
          this.dragLine = this.hovered
          //console.log("p1")
          return
        }
        if(this.hitHandle(mouse,b)){
          this.dragHandle = 'p2'
          this.dragLine = this.hovered
        // console.log("p2")
          return
        }
      }
    },
    onRightClick(){
      if (this.hovered){
        // console.log("remove")
          
          send_delete("/api/chart/delete", {"guid": this.hovered.guid});
          const i = this.lines.findIndex(l => l.guid === this.hovered.guid)
          if(i !== -1) this.lines.splice(i,1)
          this.hovered=null
          this.redraw()
      }
    }
    ,drawPreview(a,b){
      this.redraw()
      this.drawLine(a,b)
    }
    ,redraw(){
      this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)

      this.lines.forEach(line=>{
        const a = this.chartToPixel(line.p1)
        const b = this.chartToPixel(line.p2)

        const hover = line === this.hovered
        this.drawLine(a,b,hover)

        if(hover){
          this.drawHandle(a)
          this.drawHandle(b)
        }
      })
    }
    ,drawLine(a,b,hover=false){
      this.canvas_ctx.beginPath()
      this.canvas_ctx.moveTo(a.x,a.y)
      this.canvas_ctx.lineTo(b.x,b.y)
      this.canvas_ctx.strokeStyle = hover ? 'yellow' : 'white'
      this.canvas_ctx.lineWidth = hover ? 2 : 1
      this.canvas_ctx.stroke()
    },
    drawHandle(p){
      this.canvas_ctx.beginPath()
      this.canvas_ctx.arc(p.x, p.y, this.handleSize, 0, Math.PI*2)
      this.canvas_ctx.fillStyle = 'yellow'
      this.canvas_ctx.fill()
    },
    hitHandle(mouse,p){
      return Math.hypot(mouse.x-p.x, mouse.y-p.y) <= this.handleSize+2
    }
    ,hitLine(mouse, a, b, tolerance = 6){
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
  }
}