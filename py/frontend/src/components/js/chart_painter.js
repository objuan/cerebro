import { send_get } from '@/components/js/utils.js'; // Usa il percorso corretto
import { ref} from 'vue';
import {TradeBox,HLine,Box,Line } from '@/components/js/chart_primitives.js'


function cloneMouseEvent(e, type = e.type) {
  return new MouseEvent(type, {
    clientX: e.clientX,
    clientY: e.clientY,
    screenX: e.screenX,
    screenY: e.screenY,
    buttons: e.buttons,
    button: e.button,
    ctrlKey: e.ctrlKey,
    shiftKey: e.shiftKey,
    altKey: e.altKey,
    metaKey: e.metaKey,
    bubbles: true,
    cancelable: true,
  });
}  

function syncOverlaySize(overlay, topCanvas) {
      const rect = topCanvas.getBoundingClientRect();

      // dimensioni CSS
      if (overlay)
      {
      
        overlay.style.width = rect.width + 'px';
        overlay.style.height = rect.height + 'px';

        // dimensioni reali canvas (importantissimo)
        overlay.width = rect.width * devicePixelRatio;
        overlay.height = rect.height * devicePixelRatio;

        // scala per retina
        const ctx = overlay.getContext('2d');
        ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
      }
}

export function  createPainter(context,mainChart,overlay) 
{
  return {
    context,
    overlay , 
    mainChart,
    //active:false, 
    drawing : false, start : null ,hovered:null,
    canvas_ctx : overlay.value.getContext('2d'), 
    dragHandle: null,   // "p1" | "p2"
    dragLine: null,
    drawMode : ref(""),//"line",
    new_primitive:null,
    selected:null,
    edit:null,
    primitives : [],
    chartCanvas:null

    // ==================================
    
    ,_private__mouseEnterHandler(e){
       if (!this.isPaintEvent())
          this.chartCanvas.dispatchEvent(cloneMouseEvent(e));
    }
     ,_private__mouseLeaveHandler(e){
       if (!this.isPaintEvent())
          this.chartCanvas.dispatchEvent(cloneMouseEvent(e));
    }
    ,_private__mouseMoveHandler(e){
         if (!this.isPaintEvent())
          {
             const _new_selected = this.pick(this.getMouse(e));
             if (_new_selected != this.selected){
                this.selected = _new_selected
                 this.redraw()
                return
             }
             const evt = new MouseEvent('mousemove', {
                clientX: e.clientX,
                clientY: e.clientY,
                screenX: e.screenX,
                screenY: e.screenY,
                buttons: e.buttons,
                button: e.button,
                ctrlKey: e.ctrlKey,
                shiftKey: e.shiftKey,
                altKey: e.altKey,
                metaKey: e.metaKey,
                bubbles: true,
                cancelable: true,
              });

              this.chartCanvas.dispatchEvent(evt);
          }
          else
            this.onMouseMove(e);
      }
     ,_private__mouseDownHandler(e){
        if (!this.isPaintEvent())
          {
            if (this.selected) 
            {
                if (this.selected.isDraggable())
                {
                    this.edit = this.selected;
                    this.drawing=true;
                    this.drawMode.value="move"
                     this.onMouseDown(e);
                     return
                }
              }
            const evt = new MouseEvent('mousedown', e);
            this.chartCanvas.dispatchEvent(evt);
          }
          else
              this.onMouseDown(e);
    }
     ,_private__mouseUpHandler(e){
         if (!this.isPaintEvent())
          {    const evt = new MouseEvent('mouseup', e);
              this.chartCanvas.dispatchEvent(evt);
          }
          else
            this.onMouseUp(e);
    }
   ,_private__mouseWheelHandler(e){
        const evt = new WheelEvent('wheel', {
          deltaX: e.deltaX,
          deltaY: e.deltaY,
          deltaZ: e.deltaZ,
          clientX: e.clientX,
          clientY: e.clientY,
          ctrlKey: e.ctrlKey,
          shiftKey: e.shiftKey,
          altKey: e.altKey,
          metaKey: e.metaKey,
          bubbles: true,
          cancelable: true,
        });

         this.chartCanvas.dispatchEvent(evt);
    }
    ,_private__contextMenuHandler(e){
        e.preventDefault() // blocca menu browser
        console.log('right click', e)
        this.onRightClick(e)
      }

    // ==================================

    ,setMode(drawMode){
      this.drawMode.value=drawMode
    }
    ,clearMode(){
      this.drawMode.value=""
    }
    
    ,isPaintEvent(){
      return this.drawMode.value!= "" ;//|| this.selected!=null
    }

    // ==========================

    ,setChart(chart,series){
      this.chart=chart;
      this.series=series;
     
       this.overlay.value.style.pointerEvents = 'auto'

      // tv-lightweight-charts

      const chartContainer = this.mainChart.value.querySelector('.tv-lightweight-charts');
      const canvases = chartContainer.querySelectorAll('canvas');
      const topCanvas = [...canvases].find(c => {
        const z = parseInt(getComputedStyle(c).zIndex) || 0;
        return z === 2;
      });

      const ro = new ResizeObserver(() => {
        syncOverlaySize(this.overlay.value, topCanvas);
      });

      ro.observe(topCanvas);
      this.chartCanvas = topCanvas;
      // ===================

      this.overlay.value.addEventListener('mouseenter', this._private__mouseEnterHandler.bind(this));
      this.overlay.value.addEventListener('mouseleave', this._private__mouseLeaveHandler.bind(this));
      this.overlay.value.addEventListener('mousedown',this._private__mouseDownHandler.bind(this));
      this.overlay.value.addEventListener('mousemove',this._private__mouseMoveHandler.bind(this));
      this.overlay.value.addEventListener('mouseup',this._private__mouseUpHandler.bind(this));
      this.overlay.value.addEventListener('wheel',this._private__mouseWheelHandler.bind(this));
      this.mainChart.value.addEventListener('contextmenu',this._private__contextMenuHandler.bind(this));

      //this.begin()

    }
    ,unregister(){
       this.overlay.value.removeEventListener('mouseenter', this._private__mouseEnterHandler);
      this.overlay.value.removeEventListener('mouseleave', this._private__mouseLeaveHandler);
      this.overlay.value.removeEventListener('mousedown',this._private__mouseDownHandler);
      this.overlay.value.removeEventListener('mousemove',this._private__mouseMoveHandler)
      this.overlay.value.removeEventListener('mouseup',this._private__mouseUpHandler)
      this.overlay.value.removeEventListener('wheel',this._private__mouseWheelHandler);
      this.mainChart.value.removeEventListener('contextmenu',this._private__contextMenuHandler)

    }
    ,async load(){
       console.log( "load")
      try
      {
        const ind_response = await send_get(`/api/chart/read`,
          {"symbol":this.context.currentSymbol.value,"timeframe":this.context.currentTimeframe.value  });
          //ind_response.data = JSON.parse(ind_response.data)
        this.primitives.length=0;
        ind_response.map( data => {
              data.data = JSON.parse(data.data)
             console.log( "load",data)
              let prim = null
              if (data.data.type =="line")
                  prim = new Line(this)
               if (data.data.type =="box")
                  prim = new Box(this)
               if (data.data.type =="hline")
                  prim = new HLine(this)
                 if (data.data.type =="trade-box")
                  prim = new TradeBox(this)
              if (prim) 
              {
                  prim.fromSerial(data.data)
                  prim.guid = data.guid
                  this.primitives.push(prim)
              }
              
        })  
        this.redraw()
      }catch(e){
        console.error(e)
      }
    
    }
    ,clear(){
      this.primitives.forEach((p)=>{
          p.delete()
      })
      this.primitives.length=0;
      this.clearMode()
      this.redraw();
    }
    ,pixelToChart(pos){
      const logical = this.chart.timeScale().coordinateToLogical(pos.x)
      const price = this.series.coordinateToPrice(pos.y)
      return { x: logical, y: price }
    }
    ,chartToPixel(pos){
      if (!pos) return {x:0,y:0}

      const ts = this.chart.timeScale();
      let x = ts.logicalToCoordinate(pos.x);

      const vr = ts.getVisibleLogicalRange();

      const barSpacing = ts.options().barSpacing;
       x = ts.logicalToCoordinate(vr.from) + (pos.x-vr.from ) * barSpacing;
      const y = this.series.priceToCoordinate(pos.y);
      return { x, y };
    }
    ,begin(){
        //console.log("begin")
       // this.active = true
       // this.overlay.value.style.pointerEvents = 'auto'
    }
    ,end(){
      //this.active = false
      this.clearMode()
     // this.overlay.value.style.pointerEvents = 'none'
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
    ,pick(pos){
      let o_p = null;
        this.primitives.forEach((p)=>{
        if (p.pick(pos))
        {
           o_p=p.pick(pos);
        }
       });
       return o_p;
    }
    ,getPriceBand(){
       const rect = this.chartCanvas.getBoundingClientRect();
      const a =  {min: rect.width -40 ,      max : rect.width} 

      return a;
    }
    // =========================================

    ,onMouseDown(e){
      console.log("mousedown",e)

      if (this.edit)
        return

          
      this.drawing=true
      this.edit=null
      this.selected=null
      this.new_primitive=null;
      this.start =  this.pixelToChart(this.getMouse(e))
      
      if (this.drawMode.value == "line"){
          this.new_primitive = new Line(this)
      }
      if (this.drawMode.value == "hline"){
          this.new_primitive = new HLine(this)
      }
      if (this.drawMode.value == "box"){
          this.new_primitive = new Box(this)
      }
      if (this.drawMode.value =="trade-box"){
        // controllo se cè gia

          const exists = this.primitives.some(p => p.type === "trade-box");
          if (!exists)
            this.new_primitive = new TradeBox(this)
      }
      if (this.new_primitive)
      {
       this.new_primitive.begin(this.start)
       
       this.redraw()
      }
    }
    ,onMouseMove(e){
      if (!this.drawing) return

      if ( this.edit ){
        this.edit.drag( this.pixelToChart(this.getMouse(e)))
      }
      else{
          if (this.new_primitive) 
            this.new_primitive.drag( this.pixelToChart(this.getMouse(e)))
      }
       this.redraw()
    }
    ,onMouseUp(){
      this.drawing=false
      if (this.new_primitive) 
      {
        this.new_primitive.end()
        console.log("ADD")
        this.primitives.push(this.new_primitive)
      }
      this.new_primitive=null
      if (this.edit){
          this.edit.end()
      }
      this.edit =null
      this.end()
      this.redraw()
      this.redraw()
    
    }
    ,onDelete(guid){
      console.log( this.primitives)
      this.primitives = this.primitives.filter(p => p.guid !== guid);
      console.log( this.primitives)
      //this.redraw()
    }
    ,onRightClick(){
      if (this.selected){
        // console.log("remove")
          window.dispatchEvent(new CustomEvent("edit-object", {
              detail: this.selected
            }))
            return true;
          /*
          send_delete("/api/chart/delete", {"guid": this.hovered.guid});
          const i = this.lines.findIndex(l => l.guid === this.hovered.guid)
          if(i !== -1) this.lines.splice(i,1)
          this.hovered=null
          this.redraw()
          */
      }
    }
    ,redraw(){
     // console.log("redraw",this.overlay.value.width, this.primitives?.length)

      this.canvas_ctx.save();
      this.canvas_ctx.setTransform(1, 0, 0, 1, 0, 0);
      this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)
      this.canvas_ctx.restore();

      //this.canvas_ctx.clearRect(0,0,this.overlay.value.width,this.overlay.value.height)
      
    if (this.new_primitive) 
      this.new_primitive.draw(this.canvas_ctx)

      this.primitives.forEach((p)=>{
         p.draw(this.canvas_ctx)
      })
    },
  }
}