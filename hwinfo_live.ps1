<#
  hwinfo_live.ps1 - ConsoPC : tableau en direct des capteurs HWiNFO (sans Python)

  Lit les valeurs que HWiNFO publie dans le registre Windows
  (HKCU\SOFTWARE\HWiNFO64\VSB) et les affiche dans une page web locale.

  Preparation dans HWiNFO :
    1. Fenetre Capteurs > roue crantee (Parametres) > onglet "HWiNFO Gadget"
    2. Cocher "Enable reporting to Gadget" (activer le rapport vers le gadget)
    3. Dans la liste, cocher "Report value in Gadget" pour chaque capteur voulu
       (ex. CPU Package Power, GPU Power, ...)

  Lancement (PowerShell) :
    powershell -ExecutionPolicy Bypass -File .\hwinfo_live.ps1
    ... -Port 9000      change le port
    ... -Demo           donnees factices (test sans HWiNFO)
    ... -NoBrowser      n'ouvre pas le navigateur
#>
param([int]$Port = 8085, [switch]$Demo, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$regPath = 'HKCU:\SOFTWARE\HWiNFO64\VSB'
$stats = @{}
$inv = [Globalization.CultureInfo]::InvariantCulture

function Get-Type([string]$u) {
  switch ($u.Trim()) {
    'W'   { 'power' }
    {$_ -in '°C','°F','C'} { 'temp' }
    {$_ -in 'MHz','GHz'}   { 'clock' }
    '%'   { 'usage' }
    {$_ -in 'V','mV'}      { 'volt' }
    {$_ -in 'A','mA'}      { 'current' }
    'RPM' { 'fan' }
    default { 'other' }
  }
}

function Add-Stat([string]$key, [double]$v) {
  if (-not $stats.ContainsKey($key)) { $stats[$key] = @{ min = $v; max = $v; sum = 0.0; n = 0 } }
  $s = $stats[$key]
  if ($v -lt $s.min) { $s.min = $v }
  if ($v -gt $s.max) { $s.max = $v }
  $s.sum += $v; $s.n++
  return $s
}

function Get-DemoReadings {
  $t = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $items = @(
    @('CPU Demo','CPU Package Power','W',65,45), @('CPU Demo','IA Cores Power','W',50,35),
    @('GPU Demo','GPU Power','W',120,100), @('GPU Demo','GPU Temperature','°C',62,12),
    @('CPU Demo','Core 0 Clock','MHz',4200,400))
  $rnd = New-Object Random
  $out = @(); $n = 0
  foreach ($it in $items) {
    $v = [Math]::Max(0, $it[3] + $it[4] * 0.5 * [Math]::Sin($t / (2 + $n)) + $rnd.NextDouble() * 4)
    $s = Add-Stat "demo$n" $v
    $out += [ordered]@{ id = "0:$n"; sensor = $it[0]; label = $it[1]; type = (Get-Type $it[2]); unit = $it[2]
      value = $v; min = $s.min; max = $s.max; avg = $s.sum / $s.n }
    $n++
  }
  return ,$out
}

function Get-Readings {
  if ($Demo) { return ,(Get-DemoReadings) }
  if (-not (Test-Path $regPath)) {
    throw "Aucune valeur de HWiNFO dans le registre : activez 'Enable reporting to Gadget' et cochez des capteurs (onglet HWiNFO Gadget)."
  }
  $k = Get-ItemProperty -Path $regPath
  $idx = @()
  foreach ($p in $k.PSObject.Properties) {
    if ($p.Name -match '^Label(\d+)$') { $idx += [int]$Matches[1] }
  }
  if ($idx.Count -eq 0) { throw "Aucun capteur publie : cochez 'Report value in Gadget' sur les capteurs voulus." }
  $out = @()
  foreach ($i in ($idx | Sort-Object)) {
    $label = $k."Label$i"; $sensor = $k."Sensor$i"
    $valStr = [string]$k."Value$i"; $raw = [string]$k."ValueRaw$i"
    $unit = ''
    if ($valStr -match '^\s*[-+]?[\d\s.,]+\s*(.*)$') { $unit = $Matches[1].Trim() }
    $v = 0.0
    if (-not [double]::TryParse(($raw -replace ',', '.'), [Globalization.NumberStyles]::Float, $inv, [ref]$v)) { continue }
    $s = Add-Stat "$i|$sensor|$label" $v
    $out += [ordered]@{ id = "0:$i"; sensor = $sensor; label = $label; type = (Get-Type $unit); unit = $unit
      value = $v; min = $s.min; max = $s.max; avg = $s.sum / $s.n }
  }
  return ,$out
}

$page = @'
<!doctype html>
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

'@

$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add("http://localhost:$Port/")
try { $listener.Start() } catch { Write-Host "Impossible de demarrer sur le port $Port : $($_.Exception.Message)" -ForegroundColor Red; exit 1 }
$url = "http://localhost:$Port"
Write-Host "Tableau en direct : $url  (Ctrl+C pour arreter)"
if (-not $NoBrowser) { Start-Process $url }

try {
  while ($listener.IsListening) {
    $task = $listener.GetContextAsync()
    while (-not $task.AsyncWaitHandle.WaitOne(300)) { }
    $ctx = $task.GetAwaiter().GetResult()
    try {
      $path = $ctx.Request.Url.AbsolutePath
      if ($path -eq '/data') {
        try {
          $payload = @{ time = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds(); readings = @(Get-Readings) }
        } catch {
          $payload = @{ error = $_.Exception.Message }
        }
        $body = ConvertTo-Json -InputObject $payload -Depth 5 -Compress
        $ctype = 'application/json; charset=utf-8'
      } elseif ($path -eq '/' -or $path -eq '/index.html') {
        $body = $page; $ctype = 'text/html; charset=utf-8'
      } else {
        $ctx.Response.StatusCode = 404; $body = ''; $ctype = 'text/plain'
      }
      $bytes = [Text.Encoding]::UTF8.GetBytes($body)
      $ctx.Response.ContentType = $ctype
      $ctx.Response.Headers.Add('Cache-Control', 'no-store')
      $ctx.Response.ContentLength64 = $bytes.Length
      $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
    } catch { }
    finally { try { $ctx.Response.OutputStream.Close() } catch { } }
  }
} finally { $listener.Stop() }
