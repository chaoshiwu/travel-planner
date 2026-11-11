
const tripData = __TRIPDATA__;
const overview = __OVERVIEW__;

/* ---------- 坐标换算（GCJ-02 ⇄ BD-09 / WGS-84） ---------- */
const XPI = Math.PI*3000/180;
function gcjToBd(lng,lat){const z=Math.sqrt(lng*lng+lat*lat)+.00002*Math.sin(lat*XPI),t=Math.atan2(lat,lng)+.000003*Math.cos(lng*XPI);return{lng:z*Math.cos(t)+.0065,lat:z*Math.sin(t)+.006}}
function tLat(x,y){let r=-100+2*x+3*y+.2*y*y+.1*x*y+.2*Math.sqrt(Math.abs(x));r+=(20*Math.sin(6*x*Math.PI)+20*Math.sin(2*x*Math.PI))*.6667;r+=(20*Math.sin(y*Math.PI)+40*Math.sin(y/3*Math.PI))*.6667;r+=(160*Math.sin(y/12*Math.PI)+320*Math.sin(y*Math.PI/30))*.6667;return r}
function tLng(x,y){let r=300+x+2*y+.1*x*x+.1*x*y+.1*Math.sqrt(Math.abs(x));r+=(20*Math.sin(6*x*Math.PI)+20*Math.sin(2*x*Math.PI))*.6667;r+=(20*Math.sin(x*Math.PI)+40*Math.sin(x/3*Math.PI))*.6667;r+=(150*Math.sin(x/12*Math.PI)+300*Math.sin(x/30*Math.PI))*.6667;return r}
function gcjToWgs(lng,lat){let dLat=tLat(lng-105,lat-35),dLng=tLng(lng-105,lat-35);const rl=lat/180*Math.PI,magic=1-.00669342162296594623*Math.sin(rl)**2,sq=Math.sqrt(magic);dLat=(dLat*180)/((6378245*(1-.00669342162296594623))/(magic*sq)*Math.PI);dLng=(dLng*180)/(6378245/sq*Math.cos(rl)*Math.PI);return{lng:lng-dLng,lat:lat-dLat}}

/* ---------- 导航链接（免 key，自驾模式） ---------- */
const enc = encodeURIComponent;
function amapNav(p){return `https://uri.amap.com/navigation?to=${p.lng},${p.lat},${enc(p.name)}&mode=car&src=travel-planner&coordinate=gaode&callnative=1`}
function amapMark(p){return `https://uri.amap.com/marker?position=${p.lng},${p.lat}&name=${enc(p.name)}&src=travel-planner&callnative=1`}
function baiduMark(p){const b=gcjToBd(p.lng,p.lat);return `https://api.map.baidu.com/marker?location=${b.lat},${b.lng}&title=${enc(p.name)}&content=${enc(p.time)}&output=html&src=travel-planner`}
function appleMap(p){const w=gcjToWgs(p.lng,p.lat);return `https://maps.apple.com/?q=${enc(p.name)}&ll=${w.lat.toFixed(6)},${w.lng.toFixed(6)}`}
const TAGCLS={"免费":"tag-free","需预约":"tag-book","拍照圣地":"tag-photo","亲子友好":"tag-kid","推荐":"tag-free"};

/* ---------- 地图（Leaflet + 高德瓦片；GCJ-02 直接使用即与瓦片对齐） ---------- */
const map=L.map("map",{zoomControl:true,attributionControl:false});
L.tileLayer("https://webrd0{s}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x={x}&y={y}&z={z}",{subdomains:"1234",maxZoom:18}).addTo(map);

const groups={};
tripData.days.forEach((d,di)=>{
  const g=L.layerGroup();
  groups[di]=g;
  (d.routes||[]).forEach(r=>{
    L.polyline(r.pts.map(p=>[p[0],p[1]]),{color:r.color,weight:4,opacity:.82,dashArray:r.dash||null}).addTo(g);
  });
  if(!d.noLine && !(d.routes&&d.routes.length)){
    L.polyline(d.places.map(p=>[p.lat,p.lng]),{color:d.color,weight:3,opacity:.7,dashArray:"6 6"}).addTo(g);
  }
  d.places.forEach((p,i)=>{
    L.circleMarker([p.lat,p.lng],{radius:9,color:"#fff",weight:2,fillColor:d.color,fillOpacity:1})
     .addTo(g).bindPopup(`<b>${i+1}. ${p.name}</b><br><span style="font-size:12px;color:#888">${p.time} · ${p.ticket}</span>
      <div class="nav-btns"><a class="nav-amap" href="${amapNav(p)}">高德导航</a><a class="nav-baidu" href="${baiduMark(p)}">百度</a><a class="nav-apple" href="${appleMap(p)}">苹果</a></div>`)
     .bindTooltip(`${i+1}. ${p.name}`,{permanent:false});
  });
});

/* dayIdx：-1 = 全部；0/1/2/3 = Day1/Day2/Day3/备选 */
function boundsOf(dayIdx){
  const pts=[];
  tripData.days.forEach((d,di)=>{
    if(dayIdx>=0 && di!==dayIdx) return;
    (d.routes||[]).forEach(r=>r.pts.forEach(p=>pts.push([p[0],p[1]])));
    d.places.forEach(p=>pts.push([p.lat,p.lng]));
  });
  return L.latLngBounds(pts);
}
function showAll(){ Object.values(groups).forEach(g=>map.addLayer(g)); map.fitBounds(boundsOf(-1),{padding:[24,24]}); }
function showDay(n){
  Object.keys(groups).forEach(k=>{ const di=+k; if(di===n-1) map.addLayer(groups[k]); else map.removeLayer(groups[k]); });
  map.fitBounds(boundsOf(n-1),{padding:[24,24]});
}
const tabs=document.getElementById("mapTabs");
[["全部",0],["D1 去程",1],["D2 景区内",2],["D3 返程",3],["备选",4]].forEach(([t,n],i)=>{
  const b=document.createElement("button"); b.textContent=t; if(i===0) b.className="on";
  b.onclick=()=>{ [...tabs.children].forEach(c=>c.className=""); b.className="on"; n?showDay(n):showAll(); };
  tabs.appendChild(b);
});
showAll();
window.addEventListener("load",()=>{map.invalidateSize();showAll()});
window.addEventListener("resize",()=>map.invalidateSize());

/* ---------- 每日行程卡片 ---------- */
const daysBox=document.getElementById("daysBox");
tripData.days.forEach(d=>{
  const card=document.createElement("div");card.className="day-card";
  card.innerHTML=`<div class="day-head" style="background:${d.color}"><b>${d.name}</b><span>${d.date} · ${d.km} · ${d.places.length} 个点位</span></div>
  <div class="day-body"><div class="day-main">${d.places.map((p,i)=>`
    <div class="tl-item"><div class="tl-time">${p.time}</div>
      <h3>${i+1}. ${p.name}
        ${p.tags.map(t=>`<span class="tag ${TAGCLS[t]||"tag-book"}">${t}</span>`).join("")}
        <a class="tl-go" href="${amapNav(p)}" target="_blank">导航</a>
        <a class="tl-go" style="color:#8B6914;border-color:#f0e0bc;background:#fdf8ef" href="${amapMark(p)}" target="_blank">标点</a></h3>
      <p class="tl-desc">${p.desc}</p><p class="tl-meta">🎫 ${p.ticket}</p></div>`).join("")}
  </div><div class="day-side"><h4>✨ 今日亮点</h4><ul>${d.highlights.map(h=>`<li>${h}</li>`).join("")}</ul>
  <h4 style="margin-top:12px">⚠️ 重要提醒</h4><ul>${d.warns.map(w=>`<li>${w}</li>`).join("")}</ul></div></div>`;
  daysBox.appendChild(card);
});

/* ---------- 路线总览（线性图） ---------- */
const rl=document.getElementById("routeLine");
rl.innerHTML=overview.map((n,i)=>`<div class="rnode"><div class="dot"></div><b>${n}</b></div>${i<overview.length-1?'<div class="rlink"></div>':''}`).join("");

/* ---------- KML 导出（WGS-84，奥维/两步路/Google Earth 通用） ----------
   注意：<a download> + Blob 在部分环境会被**静默忽略**（微信内置浏览器、预览面板 /
   沙箱 webview 都这样——点了既不下载也不报错）。所以做成「先自动试一次 + 面板兜底」：
   面板里能重试保存，也能复制全文自己另存，任何环境都有确定出路。 */
function esc(s){return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;")}
let KML_CACHE="";
function kmlFileName(){return (tripData.kmlName||"travel")+"_route.kml";}
function kmlBuild(){
  let kml='<?xml version="1.0" encoding="UTF-8"?><kml xmlns="http://www.opengis.net/kml/2.2"><Document>';
  tripData.days.forEach((d,di)=>{
    const sid="s"+di;
    kml+=`<Style id="${sid}"><LineStyle><color>ff40a8d4</color><width>3</width></LineStyle></Style>`;
    d.places.forEach((p,i)=>{const w=gcjToWgs(p.lng,p.lat);
      kml+=`<Placemark><name>${esc(i+1+". "+p.name)}</name><description>${esc(p.time+" · "+p.ticket)}</description>
        <Point><coordinates>${w.lng.toFixed(6)},${w.lat.toFixed(6)},0</coordinates></Point></Placemark>`});
    const gs=[...(d.routes||[]),...(d.altRoutes||[])];
    gs.forEach((r,ri)=>{
      const coords=r.pts.map(p=>{const w=gcjToWgs(p[1],p[0]);return `${w.lng.toFixed(6)},${w.lat.toFixed(6)},0`}).join(" ");
      kml+=`<Placemark><name>${esc(d.name+" 行车线"+(gs.length>1?(" "+(ri+1)):""))}</name><styleUrl>#${sid}</styleUrl>
        <LineString><coordinates>${coords}</coordinates></LineString></Placemark>`;
    });
    if(!d.noLine && !gs.length){
      const coords=d.places.map(p=>{const w=gcjToWgs(p.lng,p.lat);return `${w.lng.toFixed(6)},${w.lat.toFixed(6)},0`}).join(" ");
      kml+=`<Placemark><name>${esc(d.name)}</name><styleUrl>#${sid}</styleUrl><LineString><coordinates>${coords}</coordinates></LineString></Placemark>`;
    }
  });
  kml+='</Document></kml>';
  return kml;
}
function setKmlSt(msg,color){
  try{const e=document.getElementById("kmlSt");e.textContent=msg;e.style.color=color||"#7a6b4f"}catch(err){}
}
function _kmlTrigger(href,name,revoke){
  try{
    const a=document.createElement("a");
    a.href=href;a.download=name;a.rel="noopener";
    a.style.cssText="position:fixed;left:-9999px;top:0;width:1px;height:1px";
    if(a.setAttribute)a.setAttribute("download",name);
    document.body.appendChild(a);          /* 不挂进文档，部分浏览器会忽略 click() */
    a.click();
    setTimeout(()=>{try{document.body.removeChild(a)}catch(e){}
                    if(revoke)try{URL.revokeObjectURL(href)}catch(e){}},4000);
    return true;
  }catch(e){return false}
}
function kmlSaveFile(){
  if(!KML_CACHE)KML_CACHE=kmlBuild();
  const name=kmlFileName();
  let ok=false;
  if(typeof Blob==="function"&&typeof URL!=="undefined"&&URL.createObjectURL){
    try{ok=_kmlTrigger(URL.createObjectURL(new Blob([KML_CACHE],
      {type:"application/vnd.google-earth.kml+xml;charset=utf-8"})),name,true)}catch(e){ok=false}
  }
  if(!ok){ /* 兜底：data: 链接（沙箱里 Blob 也可能被拦） */
    try{ok=_kmlTrigger("data:application/vnd.google-earth.kml+xml;charset=utf-8,"
      +encodeURIComponent(KML_CACHE),name,false)}catch(e){ok=false}
  }
  setKmlSt(ok?"已触发下载 ✓ 若 3 秒内没出现保存提示，就点「复制全部内容」。"
              :"这个浏览器不允许下载，请点「复制全部内容」。",
           ok?"#2e7d32":"#c62828");
}
function kmlCopy(){
  if(!KML_CACHE)KML_CACHE=kmlBuild();
  const okMsg="已复制 ✓ 粘到备忘录 / 记事本，存为 "+kmlFileName();
  const badMsg="这个环境不能自动复制 —— 请长按下面文本 → 全选 → 复制。";
  const done=()=>setKmlSt(okMsg,"#2e7d32");
  const legacy=()=>{
    try{
      const ta=document.getElementById("kmlText");
      ta.value=KML_CACHE;ta.removeAttribute("readonly");
      ta.focus();ta.select();
      if(ta.setSelectionRange)ta.setSelectionRange(0,KML_CACHE.length);
      const ok=document.execCommand&&document.execCommand("copy");
      ta.setAttribute("readonly","readonly");
      setKmlSt(ok?okMsg:badMsg,ok?"#2e7d32":"#c62828");
    }catch(e){setKmlSt(badMsg,"#c62828")}
  };
  if(typeof navigator!=="undefined"&&navigator.clipboard&&navigator.clipboard.writeText){
    navigator.clipboard.writeText(KML_CACHE).then(done).catch(legacy);
  }else legacy();
}
function openKml(){
  try{
    document.getElementById("kmlFile").textContent=kmlFileName();
    document.getElementById("kmlText").value=KML_CACHE;
    document.getElementById("kmlMask").classList.add("on");
  }catch(e){}
}
function closeKml(){try{document.getElementById("kmlMask").classList.remove("on")}catch(e){}}
function downloadKML(){
  KML_CACHE=kmlBuild();
  openKml();        /* 先给确定性出口，避免"点了没反应" */
  kmlSaveFile();    /* 再自动试一次下载 */
}
