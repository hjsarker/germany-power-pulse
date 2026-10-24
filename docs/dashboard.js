const $=s=>document.querySelector(s),cols=['biomass','hydro','wind_offshore','wind_onshore','solar','other_renewable','lignite','hard_coal','gas','pumped_storage','other_conventional'],renew=cols.slice(0,6),labels={biomass:'Biomass',hydro:'Hydropower',wind_offshore:'Offshore wind',wind_onshore:'Onshore wind',solar:'Solar',other_renewable:'Other renewables',lignite:'Lignite',hard_coal:'Hard coal',gas:'Natural gas',pumped_storage:'Pumped storage',other_conventional:'Other conventional',grid_load:'Grid load',price:'Day-ahead price'};
let raw=null,selected=[];const layout=(x,y)=>({paper_bgcolor:'#16253a',plot_bgcolor:'#16253a',font:{color:'#a9bdd2',size:11},margin:{l:65,r:18,t:14,b:55},xaxis:{title:x,gridcolor:'#2c4058'},yaxis:{title:y,gridcolor:'#2c4058'},legend:{orientation:'h',y:-.25},autosize:true});
const plot=(id,data,lay)=>Plotly.react(id,data,{...lay,height:365},{responsive:true,displaylogo:false});
const fmt=n=>n==null?'N/A':new Intl.NumberFormat('en-US',{maximumFractionDigits:1}).format(n);
function update(){if(!raw)return;const days=Number($('#days').value),records=raw.records;const end=new Date(records.at(-1).ts).getTime(),start=end-(days*24-1)*3600000;selected=records.filter(r=>new Date(r.ts).getTime()>=start);const valid=k=>selected.filter(r=>r[k]!=null),p=valid('price'),load=valid('grid_load'),good=selected.filter(r=>cols.every(k=>r[k]!=null));
$('#price').textContent=p.length?'€'+fmt(p.reduce((a,r)=>a+r.price,0)/p.length):'N/A';$('#negative').textContent=p.length?p.filter(r=>r.price<0).length:'N/A';let total=good.reduce((a,r)=>a+cols.reduce((n,k)=>n+r[k],0),0),rtotal=good.reduce((a,r)=>a+renew.reduce((n,k)=>n+r[k],0),0);
$('#renewable').textContent=total>0?fmt(100*rtotal/total)+'%':'N/A';$('#load').textContent=load.length?fmt(load.reduce((a,r)=>a+r.grid_load,0)/1000)+' GWh':'N/A';
$('#coverage').textContent=selected.length+' observed hourly timestamps · '+p.length+' price observations';
const x=selected.map(r=>r.ts),pvals=selected.map(r=>r.price);
plot('priceChart',[{x,y:pvals,type:'scatter',mode:'lines',name:'Wholesale price',line:{color:'#b699ff',width:2},connectgaps:false}],layout('UTC timestamp','€/MWh'));
const points=selected.filter(r=>r.price!=null&&r.solar!=null&&r.wind_onshore!=null&&r.wind_offshore!=null&&r.grid_load!=null);
plot('scatterChart',[{x:points.map(r=>(r.solar+r.wind_onshore+r.wind_offshore)/1000),y:points.map(r=>r.price),type:'scatter',mode:'markers',name:'Hourly observation',marker:{size:6,color:points.map(r=>r.grid_load/1000),colorscale:'Viridis',showscale:true,colorbar:{title:'Grid GWh'}},text:points.map(r=>r.ts),hovertemplate:'%{text}<br>Wind + solar %{x:.1f} GWh<br>Price %{y:.1f} €/MWh<extra></extra>'}],layout('Wind and solar output (GWh)','Price (€/MWh)'));
const colors=['#41b98b','#42c4cb','#477ce0','#5aa9f4','#f1c65e','#9bd77a','#9e7972','#67778c','#a2a4b8','#667c90','#647489'];
plot('mixChart',cols.map((k,i)=>({x,y:selected.map(r=>r[k]==null?null:r[k]/1000),stackgroup:'one',type:'scatter',mode:'lines',name:labels[k],line:{width:0.5,color:colors[i]},connectgaps:false})),layout('UTC timestamp','Generation (GWh per hour)'));
const rows=new Map();for(const r of p){const d=new Date(r.ts),day=d.toLocaleDateString('en-CA',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit'}),hour=Number(d.toLocaleString('en-GB',{timeZone:'Europe/Berlin',hour:'2-digit',hourCycle:'h23'}));if(!rows.has(day))rows.set(day,Array.from({length:24},()=>[]));rows.get(day)[hour].push(r.price);}
const daysArr=[...rows.keys()].sort(),z=daysArr.map(d=>rows.get(d).map(v=>v.length?v.reduce((a,b)=>a+b,0)/v.length:null));
plot('calendarChart',[{type:'heatmap',z,x:Array.from({length:24},(_,i)=>i),y:daysArr,colorscale:'RdBu',reversescale:true,hovertemplate:'%{y} · %{x}:00<br>%{z:.1f} €/MWh<extra></extra>',colorbar:{title:'€/MWh'}}],{...layout('Berlin local hour','Date'),height:Math.max(380,daysArr.length*20),yaxis:{autorange:'reversed',type:'category'},xaxis:{dtick:2}});
$('#qualityRows').innerHTML=Object.entries(labels).map(([k,label])=>{const num=valid(k).length;return '<tr><td>'+label+'</td><td>'+num+'/'+selected.length+'</td><td>'+fmt(selected.length?100*num/selected.length:0)+'%</td></tr>'}).join('');
$('#failureNotes').textContent=Object.keys(raw.failed_series||{}).length?'Some API series failed to load; incomplete measurements are visible in the table.':'API series completed without reported ingestion errors.';
}
document.querySelectorAll('[data-tab]').forEach(b=>b.addEventListener('click',()=>{document.querySelectorAll('[data-tab]').forEach(t=>t.classList.toggle('active',t===b));document.querySelectorAll('.panel').forEach(p=>p.classList.toggle('active',p.id===b.dataset.tab));if(raw){setTimeout(()=>{document.querySelectorAll('.panel.active .plot').forEach(el=>Plotly.Plots.resize(el))},10)}}));
$('#days').addEventListener('change',update);$('#download').addEventListener('click',()=>{if(!selected.length)return;const keys=['ts',...Object.keys(labels)],data=[keys.join(','),...selected.map(r=>keys.map(k=>r[k]??'').join(','))].join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([data],{type:'text/csv'}));a.download='germany-power-pulse.csv';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)});

const berlinTime=value=>new Intl.DateTimeFormat('en-GB',{
  timeZone:'Europe/Berlin',year:'numeric',month:'short',day:'numeric',
  hour:'2-digit',minute:'2-digit',timeZoneName:'short'
}).format(new Date(value));
let checkingUpdates=false;

/** GitHub Pages serves a static JSON snapshot. This checks for a newer published
 * snapshot; only the scheduled GitHub Actions workflow fetches fresh SMARD data. */
async function checkPublishedData(initial=false){
  if(checkingUpdates)return;
  checkingUpdates=true;
  const button=$('#checkUpdates');
  button.disabled=true;
  button.textContent='Checking…';
  $('#refreshStatus').classList.remove('error');
  $('#refreshStatus').textContent='Checking the latest published dataset...';
  try{
    if(typeof Plotly==='undefined')throw Error('Charts library did not load');
    const url='data/market.json?check='+Date.now();
    const res=await fetch(url,{cache:'no-store'});
    if(!res.ok)throw Error('Published dataset unavailable (HTTP '+res.status+')');
    const payload=await res.json();
    if(!Array.isArray(payload.records)||!payload.records.length)throw Error('No verified market observations in published snapshot');
    const generatedAt=Date.parse(payload.generated_at_utc);
    if(!Number.isFinite(generatedAt))throw Error('Dataset refresh timestamp is missing or invalid');
    payload.records.sort((a,b)=>a.ts.localeCompare(b.ts));
    const previous=raw?Date.parse(raw.generated_at_utc):null;
    if(raw && generatedAt<=previous){
      $('#refreshStatus').textContent='Checked '+berlinTime(new Date())+'. No newer published dataset yet.';
      return;
    }
    raw=payload;
    const lastPrice=[...raw.records].reverse().find(r=>r.price!=null);
    $('#lastRefresh').dateTime=payload.generated_at_utc;
    $('#lastRefresh').textContent=berlinTime(payload.generated_at_utc);
    $('#latestObservation').textContent=lastPrice?berlinTime(lastPrice.ts):'Unavailable';
    if(lastPrice)$('#latestObservation').dateTime=lastPrice.ts;
    $('#status').textContent='● Official historical observations loaded';
    $('#status').classList.remove('error');
    $('#updated').textContent='Source: Bundesnetzagentur | SMARD.de · CC BY 4.0 · Last published snapshot '+berlinTime(payload.generated_at_utc);
    $('#refreshStatus').textContent=initial
      ?'Daily automatic updates. This button checks published data only, not SMARD.'
      :'Newer published data loaded. Checked '+berlinTime(new Date())+'.';
    update();
  }catch(err){
    $('#refreshStatus').textContent='Could not check for updates: '+err.message;
    $('#refreshStatus').classList.add('error');
    if(!raw){
      $('#status').textContent='Data temporarily unavailable: '+err.message;
      $('#status').classList.add('error');
      $('#coverage').textContent='No synthetic fallback data used';
    }
    console.error(err);
  }finally{
    checkingUpdates=false;
    button.disabled=false;
    button.textContent='↻ Check for new data';
  }
}
$('#checkUpdates').addEventListener('click',()=>checkPublishedData(false));
checkPublishedData(true);
