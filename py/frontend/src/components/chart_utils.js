import {send_post,generateGUID, send_delete} from '@/components/utils.js';
import {pointToSegmentDistance} from '@/components/utils.js'; // Usa il percorso corretto
import { createTradingLine, LineSeries,LineStyle } from '@pipsend/charts';

export async function setTradeMarker(chart_context,tradeData) { 
    console.log("setTradeMarker", chart_context,tradeData);
    const currentSymbol = chart_context.currentSymbol;
    const currentTimeframe = chart_context.currentTimeframe;
    
    let ret = await send_post("/api/trade/marker",
        {
            symbol: currentSymbol.value,
            timeframe: currentTimeframe.value,
            data: tradeData
        });
    console.log("Trade marker set", ret);
    if (ret.status === "ok") {
        updateTradeMarker(chart_context,tradeData); 
    }
}

export function updateTradeMarker(chart_context,tradeData) { 
    console.log("updateTradeMarker",chart_context, tradeData);

    clearLineByGUID(chart_context,"TRADE_MARKER");
    clearLineByGUID(chart_context,"TRADE_STOP_LOSS");

    const charts = chart_context.charts;
    const series = chart_context.series;
    const drawSeries = chart_context.drawSeries;    
/*
      createTradingLine(series.main, charts.main, {
            price: price + price* 0.001,
            title: 'TP',
            color: '#00FF00',
            lineStyle: LineStyle.Dotted,
            onDragStart: (price) => console.log('Drag started',price),
            onDragMove: (price) => console.log('Moving:', price),
            onDragEnd: (price) => console.log('Final:', price)
        });
          createTradingLine(series.main, charts.main, {
            price: price - price* 0.001,
            title: 'SL',
             color: '#FF0000',
             lineStyle: LineStyle.Dotted,
            onDragStart: (price) => console.log('Drag started',price),
            onDragMove: (price) => console.log('Moving:', price),
            onDragEnd: (price) => console.log('Final:', price)
        });
        createTradingLine(series.main, charts.main, {
          price: price,
          title: 'BUY',
          color: '#0000FF',
          lineStyle: LineStyle.Dotted
         // onDragEnd: (price) => api.updateAlert(price)
      });
*/
    if (tradeData.price) 
    {
        const line =  createTradingLine(series.main, charts.main, {
          price: tradeData.price,
          title: 'BUY',
          color: '#0000FF',
          lineStyle: LineStyle.Dotted
         // onDragEnd: (price) => api.updateAlert(price)
       });
        line.price = tradeData.price
        line.guid = "TRADE_MARKER";
        //console.log(line);
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
                line.remove();
            }}) ;
    }
    if (tradeData.stop_loss) 
    {
        const line = series.main.createPriceLine({
            price: tradeData.stop_loss,
            color: '#ff4800ff',
            lineWidth: 1,
            lineStyle: 0, // solid
            axisLabelVisible: true,
            title: 'ST'
            });
        line.price = tradeData.stop_loss
        line.guid = "TRADE_STOP_LOSS";

         drawSeries.push({"line":line,
            "contains": (x,y)=> {
                //console.log("line",line.p1,line.p2);  
                const py = series.main.priceToCoordinate(line.stop_loss);
                if (!py) return false;
                const dist = Math.abs(py - y);
            // console.log("dist",x,y,dist);
                return dist < 10; // Tolleranza in pixel
            },
            "delete": (line)=> {
                line.remove();
            }}) ;
    }
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