import {send_post,generateGUID, send_delete} from '@/components/js/utils.js';
import {pointToSegmentDistance} from '@/components/js/utils.js'; // Usa il percorso corretto
import { createTradingLine, LineSeries,LineStyle } from '@pipsend/charts';


function update_marker_pos(chart_context,price_marker,price ){
    if (chart_context.gfx_canvas.value.width==0) return;
    
    //console.log(chart_context.gfx_canvas.value.width)

    //const timeScale = chart_context.charts.main.timeScale();
   // const range = timeScale.getVisibleLogicalRange();
    // ultimo indice logico visibile
  //  const logicalIndex = Math.floor(range.to);
    const x =chart_context.gfx_canvas.value.width-22;// timeScale.logicalToCoordinate(logicalIndex);
    let y = chart_context.series.main.priceToCoordinate(price); // nel centro

   // console.log("X,Y", x,y);

    if (price_marker&&  price_marker.value!=null){
       // console.log("X,Y", x,y);

        price_marker.value.style.top = `${y - price_marker.value.offsetHeight / 2}px`;
        price_marker.value.style.left = `${x}px`; // asse sinistro
        price_marker.value.style.display ="block"
    }
}
    

export function updateTaskMarker(chart_context,tradeMarkers) { 
    //console.log("updateTradeMarker",tradeMarkers);


    Object.entries(tradeMarkers).forEach(([, value]) => {
        
        //console.log(value.task)
        let ref = value.ref
        update_marker_pos(chart_context,ref,value.task.price);
    });
    /*

     taskData.forEach( (task)=>
      {
        console.log("ADD TASK", task);
        task.data = JSON.parse(task.data)

        update_marker_pos(chart_context,price_marker,task)
    });
    */

   
}

// ============================================================

export async function setTradeMarker(chart_context,tradeData) { 
    console.log("setTradeMarker", chart_context,tradeData);
    const currentSymbol = chart_context.currentSymbol;
    const currentTimeframe = chart_context.currentTimeframe;
    
    let ret = await send_post("/api/trade/marker/add",
        {
            symbol: currentSymbol.value,
            timeframe: currentTimeframe.value,
            data: tradeData,
        });
    console.log("Trade marker set", ret);
    if (ret.status === "ok") {
        tradeData = ret.data
        chart_context.liveStore.updatePathData('trade.tradeData.'+chart_context.currentSymbol.value, tradeData);

        updateTradeMarker(chart_context,tradeData); 
    }
}

function calc_percent(price,base)
{
    return ((price - base) / base) * 100
}

function addTradeLine(chart_context,tradeData,price,title, color,guid){
    const charts = chart_context.charts;
    const series = chart_context.series;
    const drawSeries = chart_context.drawSeries;    

    function get_label()
    {
        let label = title
        if (title== "SL")
            label +=   " " +calc_percent(price,tradeData.price).toFixed(2)     +"%"
        if (title== "TP")
            label +=   " " +calc_percent(price,tradeData.price).toFixed(2)     +"%"
        return label+"    "
    }

    const line =  createTradingLine(series.main, charts.main, {
          price: price,
          title: get_label(),
          color:  color,
          lineStyle: LineStyle.Dotted,
          onDragEnd: async  (price) => 
          {
            console.log("SET PRICE" ,title,price )
            if (title== "BUY")
                tradeData.price = price;
            if (title== "SL")
                tradeData.stop_loss = price;
            if (title== "TP")
                tradeData.take_profit = price;

            let ret = await send_post("/api/trade/marker/update",
                {
                    symbol: chart_context.currentSymbol.value,
                    timeframe: chart_context.currentTimeframe.value,
                    data: tradeData,
                });
          
            if (ret.status === "ok") {
                tradeData = ret.data
                console.log("Trade marker set price", tradeData);

                if (title!= "BUY")
                {
                    clearLineByGUID(chart_context,guid);
                    addTradeLine(chart_context,tradeData,price,title,color,guid )
                }
                chart_context.liveStore.updatePathData('trade.tradeData.'+chart_context.currentSymbol.value, tradeData);
                
                //console.log("UPDATE ", chart_context.liveStore,'trade.tradeData.'+chart_context.currentSymbol.value,tradeData);

                //updateTradeMarker(chart_context,tradeData); 
            }
          }
       });
        line.price = price
        line.guid = guid;
        //console.log(line);
         drawSeries.push({"line":line,
            "contains": (x,y)=> {
                const py = series.main.priceToCoordinate(line.price);
                if (!py) return false;
                const dist = Math.abs(py - y);
                return dist < 10; // Tolleranza in pixel
            },
            "delete": (line)=> {
                line.remove();
            }}) ;
}

export function updateTradeMarker(chart_context,tradeData) { 
    //console.log("updateTradeMarker",chart_context, tradeData);

    clearLineByGUID(chart_context,"TRADE_MARKER");
    clearLineByGUID(chart_context,"TRADE_STOP_LOSS");
    clearLineByGUID(chart_context,"TRADE_TAKE_PROFIT");

    if (tradeData.take_profit)
        addTradeLine(chart_context,tradeData,tradeData.take_profit,"TP","#01ff2b","TRADE_TAKE_PROFIT" )
   
    if (tradeData.price)
        addTradeLine(chart_context,tradeData,tradeData.price,"BUY","#2b07ce","TRADE_MARKER" )

    if (tradeData.stop_loss)
        addTradeLine(chart_context,tradeData,tradeData.stop_loss,"SL","#da0606","TRADE_STOP_LOSS" )

}

// ==========================================================

export function drawHorizontalLine(chart_context,price,guid=null) {
 //console.log("Draw HLine at", price);
  const series = chart_context.series;
  const currentSymbol = chart_context.currentSymbol;
  const currentTimeframe = chart_context.currentTimeframe;
  const drawSeries = chart_context.drawSeries;    

  const line = series.main.createPriceLine({
      price: price,
      color: '#ffcc00',
      lineWidth: 1,
      lineStyle: LineStyle.SparseDotted, // oppure Dashed
      axisLabelVisible: true,
      title: ''
    });
    
  line.price=  price
  if (!guid)
    line.guid = generateGUID();  
  else
    line.guid = guid;

  if (!guid)
    send_post("/api/chart/save",
    {
        symbol: currentSymbol.value,
        timeframe: currentTimeframe.value,
        guid: line.guid,
        data: 
        {  
            "type": "price_line",
            "price": price,
            "color": '#ffcc00',
        }
        });

  drawSeries.push({"line":line,
    "contains": (x,y)=> {
        //console.log("line",line.p1,line.p2);  
        const py = series.main.priceToCoordinate(line.price);
        if (!py) return false;
        const dist = Math.abs(py - y);
       // console.log("dist",x,y,dist);
        return dist < 10; // Tolleranza in pixel
    },
    "delete": (line)=> {
      series.main.removePriceLine(line);
    }}) ;
  //console.log("HLine drawn",drawSeries );
}


export function drawTrendLine(chart_context,p1, p2,guid=null) {
  //  console.log("drawTrendLine",p1,p2,guid);    
    const charts = chart_context.charts;
    const series = chart_context.series;
    const currentSymbol = chart_context.currentSymbol;
    const currentTimeframe = chart_context.currentTimeframe;
    const drawSeries = chart_context.drawSeries;    

    //console.log("drawTrendLine",charts,series,currentSymbol,currentTimeframe,drawSeries); 

  const line = charts.main.addSeries(LineSeries, {
    color: '#00ffff',
    lineWidth: 1,
    lastValueVisible: false,
    priceLineVisible: false
  });
  if (p1.time > p2.time) {
    const temp = p1;
    p1 = p2;
    p2 = temp;
  }
  line.setData([
    { time: p1.time, value: p1.value },
    { time: p2.time, value: p2.value }
  ]);
  line.p1 = p1;
  line.p2 = p2;
  if (!guid)
    line.guid = generateGUID();  
  else
    line.guid = guid;
  
if (!guid)
    send_post("/api/chart/save",
    {
        symbol: currentSymbol.value,
        timeframe: currentTimeframe.value,
        guid: line.guid,
        data: 
        {  
            "type": "trend",
            "p1": { "time": p1.time, "value": p1.value  },
            "p2": { "time": p2.time, "value": p2.value  },
            "color": '#00ffff',
        }
        });

  drawSeries.push({"line":line, 
    "contains": (x,y)=> {
       // console.log("contains check",x,y);  
       // console.log("line",line.p1,line.p2);  
        const x1 = charts.main.timeScale().timeToCoordinate(line.p1.time);
        const y1 = series.main.priceToCoordinate(line.p1.value);
        const x2 = charts.main.timeScale().timeToCoordinate(line.p2.time);
        const y2 = series.main.priceToCoordinate(line.p2.value);

      //  console.log("line",x1,y1,x2,y2);

         if ([x1, y1, x2, y2].includes(null)) return false;

        const dist = pointToSegmentDistance(
            x,
            y,
            x1,
            y1,
            x2,
            y2
        );
        //console.log("dist",x,y,dist);
        return dist < 10; // Tolleranza in pixel
    },
    "delete": (line)=> {
      charts.main.removeSeries(line);
  }}) ;
}



export function findLineAt(chart_context,time,price){
  
    const mouseX = chart_context.charts.main.timeScale().timeToCoordinate(time);
    if (mouseX === null) return;
    const mouseY = chart_context.series.main.priceToCoordinate(price);

    //console.log("findLineAt",mouseX,mouseY); 

    for (const line of chart_context.drawSeries ) {
        if (line["contains"](mouseX, mouseY)) {
            return line;
        } 
    }
    return null
}


export function clearLine(chart_context,time,price) {
  if (!chart_context.charts.main) return;

    let line = findLineAt(chart_context,time,price); 
    if (line) {
         line["delete"](line["line"]);
         const index = chart_context.drawSeries.indexOf(line);
         chart_context.drawSeries.splice(index, 1);
        // console.log("Line deleted",chart_context.drawSeries.length ); 

         send_delete("/api/chart/delete", {"guid": line["line"].guid});
    } 
}

function clearLineByGUID(chart_context,guid) {
   if (!chart_context.charts.main) return;
   chart_context.drawSeries.forEach( lineObj => {
        if (lineObj["line"].guid === guid) {
             lineObj["delete"](lineObj["line"]);
             const index = chart_context.drawSeries.indexOf(lineObj);
             chart_context.drawSeries.splice(index, 1);
        }
    } );
}

export function clearDrawings(chart_context,clearDB=false) {
  if (!chart_context.charts.main) return;
  chart_context.drawSeries.forEach(s => {
    s["delete"](s["line"]);
  });
  chart_context.drawSeries.length = 0;
  if (clearDB)
    send_delete("/api/chart/delete/all", {"symbol": chart_context.currentSymbol.value, "timeframe": chart_context.currentTimeframe.value } );
}


export function getChartCoords(chart_context,e) {
    const rect = chart_context.container.getBoundingClientRect();

    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    const time = chart_context.chart.timeScale().coordinateToTime(x);
    const price = chart_context.series.main.coordinateToPrice(y);

    return { x, y, time, price };
}

export function onMouseDown(chart_context,e) {
    console.debug("onMouseDown",chart_context,e);
    //const coords = getChartCoords(chart_context,e);
    //const line = findLineAt(chart_context,coords.time,coords.price);    
}

export function onMouseMove(chart_context,e) {
    console.debug("onMouseMove",chart_context,e);
}
export function onMouseUp(chart_context,e) {
     console.debug("onMouseUp",chart_context,e);
}