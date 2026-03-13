
import {  Primitive} from '@/components/js/chart_primitives.js'; // Usa il percorso corretto
import { drawLine, drawRect, drawTextOnLine } from './chart_draw';
//import {  drawHandle,hitHandle,drawTextOnLine,hitLine,handleSize,drawLine,drawRect} from '@/components/js/chart_draw.js'; // Usa il percorso corretto


export  class MarketZoneBand  extends Primitive{

   constructor(painter,data){
    super(painter)
    this.data=data
    this.type = "market-zone"
    this.isHover = false
    this.color = '#ea00ff'
    this.zoneIndex = []
    this.onDataChanged()
    this.colors = {"close" : "#ff0000","pre" : "#e99269","open" : "#ffffff","after" : "#2963ad"}
    this.colors = {
        close: "rgba(255, 0, 0, 0.5)",
        pre: "rgba(248, 115, 5, 0.5)",
        open: "rgba(103, 212, 0, 0.92)",
        after: "rgba(41, 99, 173, 0.5)"
      };
  }
  onDataChanged() {


try{
      if (!this.data || this.data.length === 0)
      return
    
    const TIME_ZONE_OFFSET = 0
    const DAY_MINUTES = 1440

    const min_open = 15* 60 + 30
    const min_close = 22 * 60

    let zone = ""
    let old_zone = "close"
    let idx = -1
    let old_idx = -1

    this.zoneIndex = []
    this.lastClose = null
    this.lastOpen = null

    for (let i = 0; i < this.data.length; i++) {

      const t = this.data[i].time 

      if (!t) continue

     
      idx++

      // minuti UTC senza Date()
      let minutes = Math.floor(t / 60) % DAY_MINUTES
      minutes -= TIME_ZONE_OFFSET

      // console.log(minutes,minutes/60)


      if (minutes < 0)
        minutes += DAY_MINUTES

      if (minutes < min_open)
        zone = "pre"
      else if (minutes < min_close)
        zone = "open"
      else
        zone = "after"

      if (zone !== old_zone) {

        if (old_idx !== -1) {

          if (old_zone === "after")
            this.lastClose = old_idx

          if (old_zone === "open")
            this.lastOpen = old_idx

          this.zoneIndex.push({
            from: old_idx,
            to: idx,
            zone: old_zone
          })
        }

        old_zone = zone
        old_idx = idx
      }
    }

    if (old_zone === "pre")
      this.lastOpen = idx - 1
    else if (old_zone === "open" && this.zoneIndex.length > 0)
      this.lastOpen = this.zoneIndex[this.zoneIndex.length - 1].to

    this.zoneIndex.push({
      from: old_idx,
      to: idx,
      zone: old_zone
    })

    console.log("zoneIndex",this.zoneIndex)
  }
     catch (ex){
        console.error(ex)
    }
  }


    draw(ctx){
        //console.log(this.data)
      const from = {x:0, y: this.painter.geHeight()-10}
      const to = {x:this.painter.getPriceBand().max, y: this.painter.geHeight()}

      this.zoneIndex.forEach( (zone)=>{
      //  console.log("zone",zone)

          const f = this.painter.chartToPixel({x: zone.from, y:0})
          const t = this.painter.chartToPixel({x: zone.to, y:0})
          const p1 = {x:f.x, y: from.y}
          const p2 = {x:t.x, y: to.y}
          
      //   console.log(".:",zone.from,zone.to,p1,p2)

          drawRect(ctx,p1,p2, this.colors[zone.zone],
            this.colors[zone.zone],false,"solid"
          )
      });
    
      //console.log(from,to, log_from,log_to)
    }
    rebuild(){

    }
}

// =========================================

export  class GapZone  extends MarketZoneBand{
  
   constructor(painter,data){
    super(painter,data)
    this.type = "gap-zone"
    this.color =  "rgba(170, 145, 6, 0.9)"
   }
   onDataChanged(){
      super.onDataChanged()

      let m = 99999999
      let M = -99999999
      if (this.lastClose)
      {
        for (var i = this.lastClose ; i<= this.lastOpen;i++)
        {
            m = Math.min(m, this.data[i].low)
            M = Math.max(M, this.data[i].high)
        }
        self.low = m
        self.hi = M
        self.middle = self.low + (self.hi-self.low)/2 
    }

  }

  draw(ctx){
      if (!this.lastClose) return
      const _lastClose = this.data[this.lastClose].close
      const _lastOpen = this.data[this.lastOpen].close
      
      const gapH = 100 * ( self.hi - self.low) /self.low ;
      const gap = 100 * ( _lastOpen - _lastClose) /_lastClose ;

      //const p1 = {x:0, y: _lastClose}
     // const p2 = {x:20, y: _lastOpen}

      const c = this.painter.chartToPixel({x: this.lastClose, y:_lastClose})
      const o = this.painter.chartToPixel({x: this.lastOpen, y:_lastOpen})
      const l = this.painter.chartToPixel({x: this.lastOpen, y:self.low })
      const h = this.painter.chartToPixel({x: this.lastOpen, y:self.hi })
      const m = this.painter.chartToPixel({x: this.lastOpen, y:self.middle })
      
       const p1 = {x:0, y: c.y}
       const p2 = {x:20, y: o.y}

    //  console.log("zone " , "l",self.low , "h", self.hi ,"c", _lastClose,"o",_lastOpen)
      //console.log(p1,p2,c,o,  l, h)

       drawRect(ctx,p1,p2,this.color ,this.color ,false,"solid")
       drawLine(ctx,  {x:10, y: l.y}, {x:10, y:  Math.max(o.y,c.y)}, this.color)
       drawLine(ctx,  {x:10, y: h.y}, {x:10, y: Math.min(o.y,c.y)},this.color)

       drawLine(ctx,  {x:20, y: m.y}, {x:30, y: m.y},"black")
       drawTextOnLine(ctx,{x:10, y: p2.y}, {x:10, y: p1.y}, `${gap.toFixed(0)} (${gapH.toFixed(0)}) %`, "black" , 0 )
    
  }
}
