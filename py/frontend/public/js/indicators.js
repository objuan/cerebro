function db_localTime(data)
{
     const seconds = new Date(data).getTime() / 1000;
    const offsetSeconds = 60*60;//-date.getTimezoneOffset() * 6000;
    return Math.floor(seconds + offsetSeconds);
}


function calculateEMA(data, period) {
    const k = 2 / (period + 1);
    let ema = null;

    return data.map((bar, i) => {
        if (ema === null) {
            ema = bar.c; // primo valore
        } else {
            ema = bar.c * k + ema * (1 - k);
        }
        return {
            time:  db_localTime(bar.t),
            value: ema,
        };
    });
}

function calculateMovingAverageSeriesData(candleData, maLength) {
    const maData = [];

    for (let i = 0; i < candleData.length; i++) {
        if (i < maLength) {
            // Provide whitespace data points until the MA can be calculated
            maData.push({ time: candleData[i].time });
        } else {
            // Calculate the moving average, slow but simple way
            let sum = 0;
            for (let j = 0; j < maLength; j++) {
                sum += candleData[i - j].close;
            }
            const maValue = sum / maLength;
            maData.push({ time: candleData[i].time, value: maValue });
        }
    }

    return maData;
}