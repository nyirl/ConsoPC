#!/usr/bin/env python3
"""
HWiNFO -> tableau dynamique en temps réel (consommation d'énergie)

Lit la mémoire partagée de HWiNFO (Windows) et affiche les capteurs dans une
page web locale qui se rafraîchit toute seule.

Prérequis (côté HWiNFO) :
  1. Lancer HWiNFO en mode "Sensors" (capteurs).
  2. Paramètres > cocher "Shared Memory Support".
     (La version gratuite limite la mémoire partagée à 12 h, puis il faut
      la réactiver.)

Utilisation :
  python hwinfo_live_v1.py            # puis ouvrir http://localhost:8085
  python hwinfo_live_v1.py --port 9000
  python hwinfo_live_v1.py --demo     # données factices (test sans HWiNFO)

Aucune dépendance externe (bibliothèque standard uniquement).
"""
import argparse
import ctypes
import json
import math
import random
import struct
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

SHM_NAME = "Global\\HWiNFO_SENS_SM2"
HEADER_FMT = "<III q IIIIII"          # 44 octets, structure "packed"
HEADER_SIZE = struct.calcsize(HEADER_FMT)
READING_TYPES = {0: "none", 1: "temp", 2: "volt", 3: "fan", 4: "current",
                 5: "power", 6: "clock", 7: "usage", 8: "other"}


# --------------------------------------------------------------------------
# Lecture de la mémoire partagée HWiNFO
# --------------------------------------------------------------------------
class HWiNFOReader:
    FILE_MAP_READ = 0x0004

    def __init__(self):
        if sys.platform != "win32":
            raise RuntimeError("La mémoire partagée HWiNFO n'existe que sous Windows "
                               "(utilisez --demo pour tester ailleurs).")
        k32 = ctypes.windll.kernel32
        k32.OpenFileMappingW.argtypes = [ctypes.c_uint32, ctypes.c_int, ctypes.c_wchar_p]
        k32.OpenFileMappingW.restype = ctypes.c_void_p
        k32.MapViewOfFile.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32,
                                      ctypes.c_uint32, ctypes.c_size_t]
        k32.MapViewOfFile.restype = ctypes.c_void_p
        self.k32 = k32
        self.view = None

    def _open(self):
        h = self.k32.OpenFileMappingW(self.FILE_MAP_READ, False, SHM_NAME)
        if not h:
            raise RuntimeError("Mémoire partagée introuvable : HWiNFO est-il lancé, "
                               "capteurs ouverts, avec 'Shared Memory Support' activé ?")
        view = self.k32.MapViewOfFile(h, self.FILE_MAP_READ, 0, 0, 0)
        if not view:
            raise RuntimeError("Impossible de mapper la mémoire partagée HWiNFO.")
        self.view = view

    @staticmethod
    def _text(raw):
        return raw.split(b"\x00", 1)[0].decode("latin-1", errors="replace")

    def read(self):
        if self.view is None:
            self._open()
        head = ctypes.string_at(self.view, HEADER_SIZE)
        (sig, ver, rev, poll_time,
         off_s, size_s, n_s, off_r, size_r, n_r) = struct.unpack(HEADER_FMT, head)
        if sig != 0x53695748:  # "HWiS" ; 0xDEADBEEF = HWiNFO fermé
            self.view = None
            raise RuntimeError("HWiNFO est fermé ou la mémoire partagée est désactivée.")

        total = max(off_s + size_s * n_s, off_r + size_r * n_r)
        blob = ctypes.string_at(self.view, total)

        sensors = []
        for i in range(n_s):
            b = off_s + i * size_s
            label_orig = self._text(blob[b + 8:b + 136])
            label_user = self._text(blob[b + 136:b + 264])
            sensors.append(label_user or label_orig)

        readings = []
        for i in range(n_r):
            b = off_r + i * size_r
            rtype, sidx, rid = struct.unpack_from("<III", blob, b)
            label_orig = self._text(blob[b + 12:b + 140])
            label_user = self._text(blob[b + 140:b + 268])
            unit = self._text(blob[b + 268:b + 284])
            val, vmin, vmax, vavg = struct.unpack_from("<dddd", blob, b + 284)
            readings.append({
                "id": f"{sidx}:{rid}",
                "sensor": sensors[sidx] if sidx < len(sensors) else "?",
                "label": label_user or label_orig,
                "type": READING_TYPES.get(rtype, "other"),
                "unit": unit,
                "value": val, "min": vmin, "max": vmax, "avg": vavg,
            })
        return {"time": time.time(), "readings": readings}


# --------------------------------------------------------------------------
# Mode démo (pour tester sans HWiNFO)
# --------------------------------------------------------------------------
class DemoReader:
    ITEMS = [
        ("CPU [#0]: Demo CPU", "CPU Package Power", "power", "W", 65, 45),
        ("CPU [#0]: Demo CPU", "IA Cores Power", "power", "W", 50, 35),
        ("CPU [#0]: Demo CPU", "Core 0 Clock", "clock", "MHz", 4200, 400),
        ("GPU [#0]: Demo GPU", "GPU Power", "power", "W", 120, 100),
        ("GPU [#0]: Demo GPU", "GPU Temperature", "temp", "°C", 62, 12),
        ("Système", "Total System Power", "power", "W", 210, 90),
    ]

    def __init__(self):
        self.stats = {}

    def read(self):
        now = time.time()
        out = []
        for n, (sensor, label, typ, unit, base, amp) in enumerate(self.ITEMS):
            v = max(0.0, base + amp * 0.5 * math.sin(now / (2 + n)) + random.uniform(-3, 3))
            s = self.stats.setdefault(n, {"min": v, "max": v, "sum": 0.0, "n": 0})
            s["min"], s["max"] = min(s["min"], v), max(s["max"], v)
            s["sum"] += v
            s["n"] += 1
            out.append({"id": f"0:{n}", "sensor": sensor, "label": label, "type": typ,
                        "unit": unit, "value": v, "min": s["min"], "max": s["max"],
                        "avg": s["sum"] / s["n"]})
        return {"time": now, "readings": out}


# --------------------------------------------------------------------------
# Serveur web
# --------------------------------------------------------------------------
PAGE = r"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<title>HWiNFO – Consommation en direct</title>
<style>
 :root{color-scheme:light dark;font-family:system-ui,Segoe UI,Calibri,sans-serif}
 body{margin:0;padding:20px;background:#f4f4f5;color:#18181b}
 @media(prefers-color-scheme:dark){body{background:#18181b;color:#e4e4e7}
   table{background:#27272a}th{background:#3f3f46}tr:hover td{background:#3f3f46}}
 h1{font-size:20px;margin:0 0 12px}
 .bar{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
 .total{font-size:28px;font-weight:700}
 .muted{opacity:.65;font-size:13px}
 select,input{padding:6px 8px;font-size:14px}
 table{border-collapse:collapse;width:100%;background:#fff;font-size:14px}
 th,td{padding:6px 10px;border-bottom:1px solid #8884;text-align:left}
 th{background:#e4e4e7;cursor:default;position:sticky;top:0}
 td.num{text-align:right;font-variant-numeric:tabular-nums}
 tr.sel td{outline:0;background:#2563eb22}
 tr{cursor:pointer}
 .meter{height:6px;background:#8883;border-radius:3px;min-width:80px}
 .meter i{display:block;height:100%;background:#2563eb;border-radius:3px}
 canvas{width:100%;height:220px;background:#8881;border-radius:6px;margin:12px 0}
 .err{color:#dc2626;font-weight:600}
</style></head><body>
<h1>HWiNFO – Consommation en direct</h1>
<div class="bar">
  <div>Total puissance sélectionnée<div class="total" id="total">– W</div></div>
  <label>Afficher
    <select id="filter">
      <option value="power">Puissance (W)</option>
      <option value="all">Tous les capteurs</option>
      <option value="temp">Températures</option>
      <option value="clock">Fréquences</option>
      <option value="usage">Charges (%)</option>
    </select></label>
  <input id="q" placeholder="Rechercher…">
  <span class="muted" id="status">connexion…</span>
</div>
<canvas id="chart" width="1200" height="220"></canvas>
<div class="muted">Clic sur une ligne = l'ajouter/retirer du graphique et du total.</div>
<table><thead><tr><th>Capteur</th><th>Mesure</th><th>Actuel</th><th>Min</th><th>Moy</th><th>Max</th><th></th></tr></thead>
<tbody id="rows"></tbody></table>
<script>
const sel=new Set(), hist={}; const MAXPTS=300;
let data=[], first=true;
const $=id=>document.getElementById(id);
const fmt=(v,u)=>(Math.abs(v)>=100?v.toFixed(0):v.toFixed(2))+" "+u;
const colors=["#2563eb","#dc2626","#16a34a","#d97706","#9333ea","#0891b2","#be185d","#4d7c0f"];

async function tick(){
  try{
    const r=await fetch("/data",{cache:"no-store"}); const j=await r.json();
    if(j.error){$("status").innerHTML='<span class="err">'+j.error+'</span>';return;}
    data=j.readings;
    if(first){ // présélection : tout ce qui est puissance en W
      data.filter(d=>d.type==="power").forEach(d=>sel.add(d.id)); first=false;}
    data.forEach(d=>{ if(sel.has(d.id)){ (hist[d.id]??=[]).push(d.value);
        if(hist[d.id].length>MAXPTS) hist[d.id].shift(); }});
    $("status").textContent="mis à jour "+new Date(j.time*1000).toLocaleTimeString();
    render();
  }catch(e){$("status").innerHTML='<span class="err">serveur injoignable</span>';}
}
function render(){
  const f=$("filter").value, q=$("q").value.toLowerCase();
  const rows=data.filter(d=>(f==="all"||d.type===f)&&
      (d.sensor+" "+d.label).toLowerCase().includes(q));
  const maxByUnit={}; rows.forEach(d=>maxByUnit[d.unit]=Math.max(maxByUnit[d.unit]||0,d.max,d.value));
  $("rows").innerHTML=rows.map(d=>{
    const pct=maxByUnit[d.unit]?Math.min(100,d.value/maxByUnit[d.unit]*100):0;
    return `<tr data-id="${d.id}" class="${sel.has(d.id)?"sel":""}">
      <td>${d.sensor}</td><td>${d.label}</td>
      <td class="num"><b>${fmt(d.value,d.unit)}</b></td>
      <td class="num">${fmt(d.min,d.unit)}</td><td class="num">${fmt(d.avg,d.unit)}</td>
      <td class="num">${fmt(d.max,d.unit)}</td>
      <td><div class="meter"><i style="width:${pct}%"></i></div></td></tr>`}).join("");
  const tot=data.filter(d=>sel.has(d.id)&&d.unit==="W").reduce((a,d)=>a+d.value,0);
  $("total").textContent=tot.toFixed(1)+" W";
  draw();
}
$("rows").addEventListener("click",e=>{
  const tr=e.target.closest("tr"); if(!tr) return; const id=tr.dataset.id;
  sel.has(id)?(sel.delete(id),delete hist[id]):sel.add(id); render();});
$("filter").onchange=$("q").oninput=render;

function draw(){
  const c=$("chart"), g=c.getContext("2d"), W=c.width, H=c.height;
  g.clearRect(0,0,W,H);
  const ids=[...sel].filter(id=>hist[id]&&hist[id].length>1);
  if(!ids.length) return;
  let max=0; ids.forEach(id=>hist[id].forEach(v=>max=Math.max(max,v))); max=max*1.1||1;
  g.strokeStyle="#8884"; g.fillStyle="#888"; g.font="12px sans-serif"; g.lineWidth=1;
  for(let i=0;i<=4;i++){const y=H-20-(H-30)*i/4; g.beginPath();g.moveTo(40,y);g.lineTo(W,y);g.stroke();
    g.fillText((max*i/4).toFixed(0),4,y+4);}
  ids.forEach((id,n)=>{
    const h=hist[id], d=data.find(x=>x.id===id); g.strokeStyle=colors[n%colors.length]; g.lineWidth=2;
    g.beginPath(); h.forEach((v,i)=>{const x=40+(W-40)*i/(MAXPTS-1), y=H-20-(H-30)*v/max;
      i?g.lineTo(x,y):g.moveTo(x,y);}); g.stroke();
    g.fillStyle=colors[n%colors.length]; g.fillText((d?d.label:id),50+n*170,14);
  });
}
tick(); setInterval(tick,1000);
</script></body></html>
"""


def make_handler(reader):
    lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            if self.path.startswith("/data"):
                try:
                    with lock:
                        payload = reader.read()
                except Exception as e:  # message affiché dans la page
                    payload = {"error": str(e)}
                body = json.dumps(payload).encode()
                ctype = "application/json"
            elif self.path in ("/", "/index.html"):
                body, ctype = PAGE.encode("utf-8"), "text/html; charset=utf-8"
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    return Handler


def main():
    ap = argparse.ArgumentParser(description="Tableau live des capteurs HWiNFO")
    ap.add_argument("--port", type=int, default=8085)
    ap.add_argument("--demo", action="store_true", help="données factices")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    reader = DemoReader() if args.demo else HWiNFOReader()
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(reader))
    url = f"http://localhost:{args.port}"
    print(f"Tableau en direct : {url}  (Ctrl+C pour arrêter)")
    if not args.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
