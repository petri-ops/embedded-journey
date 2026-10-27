import json
import socket

from .config import STATION_TITLE, WEB_PORT


UI_HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
body{font-family:system-ui,sans-serif;margin:0;background:#0f172a;color:#e2e8f0}
h1{font-size:20px;margin:16px}
h2{font-size:15px;margin:20px 16px 8px}
#conn{margin:0 16px 10px;color:#22c55e;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;padding:0 16px}
.card{background:#1e293b;border-radius:10px;padding:12px;cursor:pointer}
.card h3{font-size:14px;margin:0 0 8px;color:#93c5fd}
.card .v{font-size:13px;color:#e2e8f0;margin-top:4px}
.card .u{color:#94a3b8}
.acts{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
button{background:#2563eb;color:#fff;border:0;border-radius:8px;padding:6px 10px;font-size:12px}
input[type=range]{width:110px}
.modal{position:fixed;inset:0;background:rgba(2,6,23,.72);display:none;align-items:center;justify-content:center;padding:16px;z-index:9}
.panel{background:#1e293b;border-radius:12px;padding:16px;max-width:520px;width:100%;max-height:80vh;overflow:auto}
.head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.row{font-size:13px;margin-top:6px}
.sub{font-size:13px;color:#93c5fd;margin-top:12px}
.section{padding:0 16px}
table{border-collapse:collapse;width:100%;font-size:12px;margin-top:8px}
td,th{border-bottom:1px solid #334155;padding:6px;text-align:left}
canvas{background:#1e293b;border-radius:10px;margin-top:8px;max-width:100%}
a{color:#93c5fd}
</style></head><body>
<h1>__TITLE__</h1>
<div id="conn">在线</div>
<div id="grid" class="grid"></div>
<div class="section"><h2>日志</h2>
<canvas id="chart" width="600" height="150"></canvas>
<table><thead><tr><th>时间</th><th>MCU</th><th>RSSI</th><th>天气</th><th>湿度</th><th>灯</th></tr></thead><tbody id="lrows"></tbody></table>
<a href="/download">下载 CSV</a>
</div>
<div id="modal" class="modal"><div class="panel">
<div class="head"><b id="mtitle">详情</b><button onclick="closeModal()">关闭</button></div>
<div id="mbody"></div>
</div></div>
<script>
let FEATURES=[];
let openDetailId=null;
function fmt(v){return (v===null||v===undefined||v==='')?'--':v}
function field(f,k){return (f.fields||[]).find(x=>x.key===k)||{key:k,label:k}}
function cardValue(f,k){const d=field(f,k);return fmt((f.status||{})[k])+(d.unit||'')}
function actionEl(f,a){
  if(a.type==='range'){
    const wrap=document.createElement('div'); wrap.className='acts';
    const r=document.createElement('input'); r.type='range'; r.min=a.min; r.max=a.max; r.value=(f.status&&f.status[a.value_key])||a.min;
    r.onclick=(e)=>e.stopPropagation();
    const b=document.createElement('button'); b.textContent=a.label||'应用';
    b.onclick=(e)=>{e.stopPropagation();command(f.id,a.action,r.value)};
    wrap.appendChild(r); wrap.appendChild(b); return wrap;
  }
  const b=document.createElement('button'); b.textContent=a.label||a.action;
  b.onclick=(e)=>{e.stopPropagation();command(f.id,a.action)};
  return b;
}
function render(){
  const grid=document.getElementById('grid'); grid.innerHTML='';
  FEATURES.slice().sort((a,b)=>a.order-b.order).forEach(f=>{
    const c=document.createElement('div'); c.className='card'; c.onclick=()=>detail(f.id);
    const t=document.createElement('h3'); t.textContent=f.title; c.appendChild(t);
    (f.card_fields||[]).forEach(k=>{const d=document.createElement('div'); d.className='v'; d.textContent=(field(f,k).label||k)+': '+cardValue(f,k); c.appendChild(d)});
    const cardActions=(f.actions||[]).filter(a=>a.on_card!==false);
    if(cardActions.length){
      const ac=document.createElement('div'); ac.className='acts';
      cardActions.forEach(a=>ac.appendChild(actionEl(f,a)));
      c.appendChild(ac);
    }
    grid.appendChild(c);
  });
}
function renderDetail(){
  const f=FEATURES.find(x=>x.id===openDetailId); if(!f)return;
  document.getElementById('mtitle').textContent=f.title;
  const body=document.getElementById('mbody'); body.innerHTML='';
  (f.fields||[]).forEach(d=>{const row=document.createElement('div'); row.className='row'; row.textContent=(d.label||d.key)+': '+fmt((f.status||{})[d.key])+(d.unit||''); body.appendChild(row)});
  if(f.list_key && (f.status||{})[f.list_key]){
    const h=document.createElement('div'); h.className='sub'; h.textContent=f.list_label||f.list_key; body.appendChild(h);
    (f.status[f.list_key]||[]).forEach(x=>{const d=document.createElement('div'); d.className='row'; d.textContent=x; body.appendChild(d)});
  }
  const detailActions=(f.actions||[]).filter(a=>!a.auto_open);
  if(detailActions.length){
    const ac=document.createElement('div'); ac.className='acts';
    detailActions.forEach(a=>ac.appendChild(actionEl(f,a)));
    body.appendChild(ac);
  }
}
function detail(id){
  const f=FEATURES.find(x=>x.id===id); if(!f)return;
  openDetailId=id;
  const auto=(f.actions||[]).find(a=>a.auto_open);
  if(auto) command(f.id,auto.action);
  renderDetail();
  document.getElementById('modal').style.display='flex';
}
function closeModal(){openDetailId=null;document.getElementById('modal').style.display='none'}
function command(fid,action,value){
  let url='/api/cmd?feature='+encodeURIComponent(fid)+'&action='+encodeURIComponent(action);
  if(value!==undefined&&value!==null) url+='&value='+encodeURIComponent(value);
  fetch(url).then(r=>r.json()).then(()=>setTimeout(load,300)).catch(()=>{});
}
function draw(logs){
  const c=document.getElementById('chart'), x=c.getContext('2d');
  x.clearRect(0,0,c.width,c.height);
  const rows=logs.slice(1).map(r=>r.split(','));
  if(rows.length<2)return;
  const mcu=rows.map(r=>parseFloat(r[1]));
  const w=rows.map(r=>parseFloat(r[3]));
  const all=mcu.concat(w).filter(v=>!isNaN(v));
  if(all.length<2)return;
  const min=Math.min(...all), max=Math.max(...all);
  function line(vals,color){
    x.strokeStyle=color; x.beginPath(); let started=false;
    vals.forEach((v,i)=>{
      if(isNaN(v))return;
      const px=10+i*(c.width-20)/(vals.length-1);
      const py=c.height-10-(v-min)/(max-min||1)*(c.height-20);
      if(started)x.lineTo(px,py); else {x.moveTo(px,py);started=true}
    });
    x.stroke();
  }
  line(w,'#38bdf8'); line(mcu,'#f59e0b');
  x.fillStyle='#94a3b8'; x.fillText('MCU(橙) / 天气(蓝)  '+min.toFixed(1)+'~'+max.toFixed(1)+' °C',10,14);
}
async function load(){
  try{
    const data=await (await fetch('/api/features')).json();
    FEATURES=data.features||[];
    render();
    if(openDetailId) renderDetail();
    const logs=await (await fetch('/api/logs?n=30')).json();
    draw(logs);
    const tb=document.getElementById('lrows'); tb.innerHTML='';
    logs.slice(1).slice(-8).reverse().forEach(r=>{
      const c=r.split(','); const tr=document.createElement('tr');
      c.slice(0,6).forEach(v=>{const td=document.createElement('td');td.textContent=v;tr.appendChild(td)});
      tb.appendChild(tr);
    });
    document.getElementById('conn').textContent='在线 · '+new Date().toLocaleTimeString();
    document.getElementById('conn').style.color='#22c55e';
  }catch(e){
    document.getElementById('conn').textContent='连接中断，自动重试中...';
    document.getElementById('conn').style.color='#f87171';
  }
}
setInterval(load,3000); load();
</script></body></html>""".replace("__TITLE__", STATION_TITLE)


def _parse_query(query):
    qs = {}
    for kv in query.split("&"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            qs[k] = v
    return qs


def web_response(station, path, query):
    qs = _parse_query(query)
    if path == "/":
        return "200 OK", "text/html; charset=utf-8", UI_HTML, ""
    if path == "/api/features":
        return "200 OK", "application/json", json.dumps(station.features_json()), ""
    if path == "/api/status":
        return "200 OK", "application/json", json.dumps(station.status()), ""
    if path == "/api/cmd":
        fid = qs.get("feature", "")
        action = qs.get("action", "")
        value = qs.get("value")
        ack = station.command(fid, action, value)
        return "200 OK", "application/json", json.dumps(ack), ""
    if path == "/api/logs":
        try:
            n = int(qs.get("n", "30"))
        except ValueError:
            n = 30
        return "200 OK", "application/json", json.dumps(station.read_log(n)), ""
    if path == "/download":
        body = "\n".join(station.read_log(0))
        return "200 OK", "text/csv", body, "Content-Disposition: attachment; filename=log.csv\r\n"
    return "404 Not Found", "text/plain", "not found", ""


def _send(conn, status, ctype, body, extra=""):
    if isinstance(body, str):
        body = body.encode()
    head = "HTTP/1.1 %s\r\nContent-Type: %s\r\nContent-Length: %d\r\nConnection: close\r\n%s\r\n" % (
        status,
        ctype,
        len(body),
        extra,
    )
    conn.sendall(head.encode() + body)


def web_thread(station):
    global WEB_PORT
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(("0.0.0.0", WEB_PORT))
    except OSError:
        WEB_PORT = 8080
        s.bind(("0.0.0.0", WEB_PORT))
    s.listen(5)
    print("WEB http://%s:%d/" % (station.state["ip"], WEB_PORT))
    while True:
        conn = None
        try:
            conn, _ = s.accept()
            conn.settimeout(3)
            req = b""
            while b"\r\n\r\n" not in req and len(req) < 2048:
                chunk = conn.recv(512)
                if not chunk:
                    break
                req += chunk
            if not req:
                continue
            line = req.split(b"\r\n", 1)[0].decode()
            parts = line.split()
            if len(parts) < 2:
                continue
            path = parts[1]
            query = ""
            if "?" in path:
                path, query = path.split("?", 1)
            _send(conn, *web_response(station, path, query))
        except Exception as e:
            print("web err", e)
        finally:
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass
