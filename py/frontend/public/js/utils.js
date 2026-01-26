function PopupList(list,current, onclose)
{
    const sel = $('#choice').empty();
    $.each(list, function (_, v) {
          $('<option>').val(v).text(v)
            .prop('selected', v === current).appendTo(sel);
    });
    $('#popup').show();

    $('#cancel').on('click', function () {
        $('#popup').hide();
    });

    $('#ok').on('click', function () {
       // alert('Hai scelto: ' + $('#choice').val());
        onclose($('#choice').val())
        $('#popup').hide();
    });


}

function bind_get(id , variable, formatFun)
{
    
}

function lerp(a, b, f) {
    return a + (b - a) * f;
}

function interpolateColor(start, end, f) {
  
    const s = start.match(/\w\w/g).map(x => parseInt(x, 16));
    const e = end.match(/\w\w/g).map(x => parseInt(x, 16));

    const r = Math.round(lerp(s[0], e[0], f));
    const g = Math.round(lerp(s[1], e[1], f));
    const b = Math.round(lerp(s[2], e[2], f));

    return `rgb(${r}, ${g}, ${b})`;
}
function formatValue(v) {
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

function db_localTime(data)
{
     const seconds = new Date(data).getTime() / 1000;
    const offsetSeconds = 60*60;//-date.getTimezoneOffset() * 6000;
    return Math.floor(seconds + offsetSeconds);
}
