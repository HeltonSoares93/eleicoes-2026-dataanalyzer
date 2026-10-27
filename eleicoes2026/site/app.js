/* Eleição presidencial em mapas — página estática.
   Lê os arquivos de data/ gerados por `python -m eleicoes.exportar_site`. */
"use strict";

const fmtInt = new Intl.NumberFormat("pt-BR");
const fmt1 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const fmt2 = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const pct = (v, f = fmt1) => (v == null ? "–" : `${f.format(v)}%`);
const pp = (v) => (v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : ""}${fmt1.format(Math.abs(v))} p.p.`);

const css = (nome) => getComputedStyle(document.documentElement).getPropertyValue(nome).trim();
let COR = {};
function lerCores() {
  COR = {
    a: css("--cor-a"), aClara: css("--cor-a-clara"), b: css("--cor-b"), bClara: css("--cor-b-clara"),
    outros: css("--cor-outros"), neutro: css("--neutro"), semDado: css("--sem-dado"),
    tinta: css("--tinta"), tinta2: css("--tinta-2"), superficie: css("--superficie"),
  };
}

const estado = { turno: null, uf: "BR", metrica: "margem", vista: "area", selecionado: null, busca: "", ordem: "validos", asc: false, limite: 25 };
let D = {}; // dados carregados
let M = []; // municípios como objetos
let indicePorCodigo = new Map();
let featurePorCodigo = new Map();

const NOMES_UF = {
  AC: "Acre", AL: "Alagoas", AM: "Amazonas", AP: "Amapá", BA: "Bahia", CE: "Ceará", DF: "Distrito Federal",
  ES: "Espírito Santo", GO: "Goiás", MA: "Maranhão", MG: "Minas Gerais", MS: "Mato Grosso do Sul",
  MT: "Mato Grosso", PA: "Pará", PB: "Paraíba", PE: "Pernambuco", PI: "Piauí", PR: "Paraná",
  RJ: "Rio de Janeiro", RN: "Rio Grande do Norte", RO: "Rondônia", RR: "Roraima", RS: "Rio Grande do Sul",
  SC: "Santa Catarina", SE: "Sergipe", SP: "São Paulo", TO: "Tocantins",
};

// ------------------------------------------------------------------ carga

async function carregar() {
  const ler = (n) => fetch(`data/${n}`).then((r) => { if (!r.ok) throw new Error(`${n}: ${r.status}`); return r.json(); });
  const [meta, resumo, agregados, municipios, malha, ufs] = await Promise.all(
    ["meta.json", "resumo.json", "agregados.json", "municipios.json", "malha.json", "ufs.json"].map(ler));
  const avancado = meta.tem_avancado ? await ler("avancado.json").catch(() => null) : null;
  D = { meta, resumo, agregados, municipios, malha, ufs, avancado };

  const mu = municipios;
  M = mu.cd.map((cd, i) => {
    const o = { i, cd, nome: mu.nome[i], uf: mu.uf[i], lat: mu.lat[i], lon: mu.lon[i] };
    for (const t of meta.turnos) {
      const b = mu[`t${t}`];
      o[`t${t}`] = { validos: b.validos[i], A: b.A[i], B: b.B[i], venc: b.venc[i], margem: b.margem[i], abst: b.abst ? b.abst[i] : null };
    }
    if (mu.swing) for (const [nr, arr] of Object.entries(mu.swing.por_numero)) o[`sw${nr}`] = arr[i];
    return o;
  });
  indicePorCodigo = new Map(M.map((m) => [m.cd, m]));
  for (const f of malha.features) featurePorCodigo.set(f.properties.c, f);
  estado.turno = meta.turnos[meta.turnos.length - 1];
}

// ------------------------------------------------------------------ utilidades

const A = () => D.meta.finalistas.A;
const B = () => D.meta.finalistas.B;
const doRecorte = () => (estado.uf === "BR" ? M : M.filter((m) => m.uf === estado.uf));
const T = (m) => m[`t${estado.turno}`];

function largura(el, minimo = 300) {
  return Math.max(minimo, Math.floor(el.getBoundingClientRect().width));
}

function botoesSegmentados(el, opcoes, atual, aoEscolher) {
  el.replaceChildren();
  for (const op of opcoes) {
    const b = document.createElement("button");
    b.type = "button";
    b.setAttribute("role", "radio");
    b.setAttribute("aria-checked", String(op.valor === atual));
    b.textContent = op.rotulo;
    if (op.desabilitado) { b.disabled = true; b.title = op.motivo || ""; }
    b.addEventListener("click", () => aoEscolher(op.valor));
    el.append(b);
  }
}

const dica = document.getElementById("dica");
function mostrarDica(evento, html) {
  dica.innerHTML = html;
  dica.hidden = false;
  const { innerWidth: W, innerHeight: H } = window;
  const r = dica.getBoundingClientRect();
  let x = evento.clientX + 14, y = evento.clientY + 14;
  if (x + r.width > W - 8) x = evento.clientX - r.width - 14;
  if (y + r.height > H - 8) y = evento.clientY - r.height - 14;
  dica.style.left = `${Math.max(8, x)}px`;
  dica.style.top = `${Math.max(8, y)}px`;
}
const esconderDica = () => { dica.hidden = true; };

function dicaMunicipio(m) {
  const t = T(m);
  if (!t || t.validos == null) return `<strong>${m.nome} (${m.uf})</strong>Sem dados neste turno`;
  const linhas = [
    [A().rotulo, pct(t.A)], [B().rotulo, pct(t.B)],
    ["Votos válidos", fmtInt.format(t.validos)],
  ];
  if (t.abst != null) linhas.push(["Abstenção", pct(t.abst)]);
  if (estado.metrica.startsWith("sw")) linhas.push([`Variação desde ${D.meta.ano_comparacao}`, pp(m[estado.metrica])]);
  return `<strong>${m.nome} (${m.uf})</strong>` +
    linhas.map(([k, v]) => `<span class="linha-dica"><span>${k}</span><b>${v}</b></span>`).join("");
}

// ------------------------------------------------------------------ escalas de cor

function escalaMetrica() {
  const div = (neg, negC, pos, posC, lim) => d3.scaleLinear()
    .domain([-lim, -lim / 2, 0, lim / 2, lim]).range([neg, negC, COR.neutro, posC, pos])
    .interpolate(d3.interpolateRgb).clamp(true);
  if (estado.metrica === "margem") {
    return { valor: (m) => (T(m)?.A == null ? null : T(m).A - T(m).B), cor: div(COR.b, COR.bClara, COR.a, COR.aClara, 60),
      tipo: "div", lim: 60, rotulos: [`vantagem de ${B().rotulo}`, `vantagem de ${A().rotulo}`], unidade: "p.p." };
  }
  if (estado.metrica === "abst") {
    const vals = M.map((m) => T(m)?.abst).filter((v) => v != null);
    const hi = Math.ceil((d3.quantile(vals.sort(d3.ascending), 0.98) || 40) / 5) * 5;
    return { valor: (m) => T(m)?.abst, cor: d3.scaleSequential(d3.interpolateRgb(COR.neutro, COR.tinta)).domain([0, hi]).clamp(true),
      tipo: "seq", min: 0, max: hi, rotulos: ["% dos eleitores aptos que não votaram"], unidade: "%" };
  }
  const nr = Number(estado.metrica.slice(2));
  const ehA = nr === A().nr;
  const ganha = ehA ? COR.a : COR.b, ganhaC = ehA ? COR.aClara : COR.bClara;
  const perde = ehA ? COR.b : COR.a, perdeC = ehA ? COR.bClara : COR.aClara;
  return { valor: (m) => m[estado.metrica], cor: div(perde, perdeC, ganha, ganhaC, 20), tipo: "div", lim: 20,
    rotulos: ["perdeu", "ganhou"], unidade: "p.p." };
}

// ------------------------------------------------------------------ apuração (topo)

function renderApuracao() {
  const t = estado.turno;
  let pa, pb, po, va, vb, validos, abst = null, extra = "";
  if (estado.uf === "BR") {
    const r = D.resumo[String(t)];
    const ca = r.candidatos.find((c) => c.nr === A().nr), cb = r.candidatos.find((c) => c.nr === B().nr);
    pa = ca?.pct ?? 0; pb = cb?.pct ?? 0; po = Math.max(0, 100 - pa - pb);
    va = ca?.votos ?? 0; vb = cb?.votos ?? 0; validos = r.validos; abst = r.abstencao_pct;
    extra = ` Brancos: ${fmtInt.format(r.brancos)}. Nulos: ${fmtInt.format(r.nulos)}.`;
  } else {
    const ms = doRecorte();
    validos = d3.sum(ms, (m) => T(m)?.validos || 0);
    va = d3.sum(ms, (m) => ((T(m)?.validos || 0) * (T(m)?.A || 0)) / 100);
    vb = d3.sum(ms, (m) => ((T(m)?.validos || 0) * (T(m)?.B || 0)) / 100);
    pa = (va / validos) * 100; pb = (vb / validos) * 100; po = Math.max(0, 100 - pa - pb);
    const linha = D.agregados.uf[String(t)].find((x) => x.nome === estado.uf);
    abst = linha?.abst ?? null;
  }
  document.getElementById("titulo").textContent =
    estado.uf === "BR" ? `Eleição presidencial ${D.meta.ano}` : `${NOMES_UF[estado.uf]}, presidente ${D.meta.ano}`;
  document.getElementById("nome-a").textContent = A().rotulo;
  document.getElementById("nome-b").textContent = B().rotulo;
  document.getElementById("pct-a").textContent = pct(pa, fmt2);
  document.getElementById("pct-b").textContent = pct(pb, fmt2);
  document.getElementById("votos-a").textContent = `${fmtInt.format(Math.round(va))} votos`;
  document.getElementById("votos-b").textContent = `${fmtInt.format(Math.round(vb))} votos`;
  document.getElementById("seg-a").style.width = `${pa}%`;
  document.getElementById("seg-o").style.width = `${po}%`;
  document.getElementById("seg-b").style.width = `${pb}%`;
  document.getElementById("barra").setAttribute("aria-label",
    `${A().rotulo} ${pct(pa)}, demais candidatos ${pct(po)}, ${B().rotulo} ${pct(pb)} dos votos válidos`);
  const outros = po > 0.05 ? ` Demais candidatos: ${pct(po)}.` : "";
  document.getElementById("apuracao-rodape").textContent =
    `${estado.turno}º turno. ${fmtInt.format(validos)} votos válidos.${outros}` +
    (abst != null ? ` Abstenção: ${pct(abst)}.` : "") + (estado.uf === "BR" ? extra : "");
}

// ------------------------------------------------------------------ mapa

function renderMapa() {
  const svg = d3.select("#mapa svg");
  svg.selectAll("*").remove();
  const W = 800;
  const feats = D.malha.features.filter((f) => estado.uf === "BR" || indicePorCodigo.get(f.properties.c)?.uf === estado.uf);
  const ufsFeat = D.ufs.features.filter((f) => estado.uf === "BR" || f.properties.uf === estado.uf);
  const alvo = { type: "FeatureCollection", features: estado.uf === "BR" ? ufsFeat : semIlhasDistantes(feats) };
  const proj0 = d3.geoMercator().fitWidth(W - 20, alvo);
  const [[, y0], [, y1]] = d3.geoPath(proj0).bounds(alvo);
  const H = Math.min(900, Math.ceil(y1 - y0) + 20);
  const pad = estado.vista === "prop" ? 36 : 10; // espaço para os círculos maiores
  const proj = d3.geoMercator().fitExtent([[pad, pad], [W - pad, H - pad]], alvo);
  const caminho = d3.geoPath(proj);
  svg.attr("viewBox", `0 0 ${W} ${H}`);
  const esc = escalaMetrica();

  if (estado.vista === "area") {
    svg.append("g").selectAll("path").data(feats).join("path")
      .attr("class", "mun").attr("d", caminho)
      .attr("fill", (f) => { const m = indicePorCodigo.get(f.properties.c); const v = m && esc.valor(m); return v == null ? COR.semDado : esc.cor(v); })
      .on("mousemove", (ev, f) => { const m = indicePorCodigo.get(f.properties.c); if (m) mostrarDica(ev, dicaMunicipio(m)); })
      .on("mouseleave", esconderDica)
      .on("click", (ev, f) => { const m = indicePorCodigo.get(f.properties.c); if (m) clicarMunicipio(m); });
    svg.append("g").selectAll("path").data(ufsFeat).join("path").attr("class", "uf-contorno").attr("d", caminho);
  } else {
    svg.append("g").selectAll("path").data(ufsFeat).join("path").attr("class", "uf-base").attr("d", caminho)
      .on("click", (ev, f) => { if (estado.uf === "BR") escolherUF(f.properties.uf); });
    const pts = doRecorte().filter((m) => m.lat != null && T(m)?.validos);
    const maxV = d3.max(pts, (m) => T(m).validos) || 1;
    const r = d3.scaleSqrt().domain([0, maxV]).range([0, estado.uf === "BR" ? 30 : 34]);
    svg.append("g").selectAll("circle").data(pts.sort((a, b) => T(b).validos - T(a).validos)).join("circle")
      .attr("class", "bolha")
      .attr("cx", (m) => proj([m.lon, m.lat])[0]).attr("cy", (m) => proj([m.lon, m.lat])[1])
      .attr("r", (m) => Math.max(0.8, r(T(m).validos)))
      .attr("fill", (m) => { const v = esc.valor(m); return v == null ? COR.semDado : esc.cor(v); })
      .on("mousemove", (ev, m) => mostrarDica(ev, dicaMunicipio(m)))
      .on("mouseleave", esconderDica)
      .on("click", (ev, m) => clicarMunicipio(m));
    estado._escalaRaio = { r, maxV };
  }
  renderLegenda(esc);
  renderExplicaMapa();
}

// Enquadra o território principal: ilhas distantes (ex.: Fernando de Noronha, em PE)
// continuam desenhadas, mas não definem o zoom.
function semIlhasDistantes(feats) {
  if (feats.length < 3) return feats;
  const c = feats.map((f) => d3.geoCentroid(f));
  // distância de cada município ao vizinho mais próximo (centroides, em graus)
  const nn = c.map((p, i) => d3.min(c, (q, j) => (i === j ? Infinity : Math.hypot(p[0] - q[0], p[1] - q[1]))));
  const lim = Math.max(1.5, 3 * d3.median(nn));
  const perto = feats.filter((f, i) => nn[i] <= lim);
  return perto.length ? perto : feats;
}

function clicarMunicipio(m) {
  if (estado.uf === "BR") { escolherUF(m.uf, m); return; }
  estado.selecionado = m;
  renderPainel();
}

function renderExplicaMapa() {
  const txt = {
    margem: `Cor indica quem venceu e por quanto: diferença, em pontos percentuais dos votos válidos, entre ${A().rotulo} e ${B().rotulo}.`,
    abst: "Quanto mais escura a cor, maior a parcela de eleitores aptos que não votou.",
  };
  let t = txt[estado.metrica];
  if (estado.metrica.startsWith("sw")) {
    const nr = estado.metrica.slice(2);
    t = `Variação da votação do número ${nr} (${D.meta.candidatos[nr]}) entre ${D.meta.ano_comparacao} e ${D.meta.ano}, no ${D.municipios.swing.turno}º turno.`;
  }
  const vista = estado.vista === "area"
    ? " Neste mapa, municípios grandes e pouco povoados ocupam mais espaço do que seu peso em votos."
    : " Cada círculo é um município, com área proporcional aos votos válidos: mostra onde os votos estão.";
  document.getElementById("explica-mapa").textContent = t + vista +
    (estado.uf === "BR" ? " Clique num município para aproximar o estado." : "");
}

function renderLegenda(esc) {
  const el = d3.select("#legenda");
  el.selectAll("*").remove();
  const W = 300, h = 10;
  const svg = el.append("svg").attr("width", W).attr("height", 34).attr("aria-hidden", "true");
  const id = "grad-legenda";
  const grad = svg.append("defs").append("linearGradient").attr("id", id);
  const dom = esc.tipo === "div" ? [-esc.lim, esc.lim] : [esc.min, esc.max];
  d3.range(0, 1.0001, 0.1).forEach((k) => grad.append("stop").attr("offset", k).attr("stop-color", esc.cor(dom[0] + k * (dom[1] - dom[0]))));
  svg.append("rect").attr("width", W).attr("height", h).attr("rx", 2).attr("fill", `url(#${id})`);
  const x = d3.scaleLinear().domain(dom).range([0, W]);
  const ticks = esc.tipo === "div" ? [dom[0], dom[0] / 2, 0, dom[1] / 2, dom[1]] : x.ticks(4);
  svg.selectAll("text").data(ticks).join("text").attr("x", (d) => x(d)).attr("y", h + 15)
    .attr("text-anchor", (d, i) => (i === 0 ? "start" : i === ticks.length - 1 ? "end" : "middle"))
    .text((d) => (esc.tipo === "div" ? fmtInt.format(Math.abs(d)) : `${fmtInt.format(d)}${d === ticks[ticks.length - 1] ? "%+" : "%"}`));
  const rot = el.append("span");
  rot.text(esc.tipo === "div" ? `← ${esc.rotulos[0]}  |  ${esc.unidade}  |  ${esc.rotulos[1]} →` : esc.rotulos[0]);
  if (estado.vista === "prop" && estado._escalaRaio) {
    const { r, maxV } = estado._escalaRaio;
    const topo = 10 ** Math.floor(Math.log10(maxV));
    const refs = [topo / 10, topo].filter((v) => v >= 1);
    const g = el.append("span").attr("class", "item");
    for (const v of refs) {
      const s = g.append("svg").attr("width", 2 * r(v) + 2).attr("height", 2 * r(v) + 2).attr("aria-hidden", "true");
      s.append("circle").attr("cx", r(v) + 1).attr("cy", r(v) + 1).attr("r", r(v)).attr("fill", "none").attr("stroke", COR.tinta2);
      g.append("span").text(`${fmtInt.format(v)} votos`);
    }
  }
}

// ------------------------------------------------------------------ painel lateral

function renderPainel() {
  const el = document.getElementById("painel");
  const ms = doRecorte().filter((m) => T(m)?.venc != null);
  const cont = d3.rollup(ms, (v) => v.length, (m) => (T(m).venc === A().nr ? "A" : T(m).venc === B().nr ? "B" : "O"));
  const nome = estado.uf === "BR" ? "Brasil" : NOMES_UF[estado.uf];
  let html = `<h3>${nome}: municípios vencidos</h3><dl>
    <dt>${A().rotulo}</dt><dd>${fmtInt.format(cont.get("A") || 0)}</dd>
    <dt>${B().rotulo}</dt><dd>${fmtInt.format(cont.get("B") || 0)}</dd>`;
  if (cont.get("O")) html += `<dt>Outros</dt><dd>${fmtInt.format(cont.get("O"))}</dd>`;
  html += "</dl>";
  const grandes = ms.filter((m) => T(m).validos >= (estado.uf === "BR" ? 50000 : 10000));
  const apertada = d3.least(grandes, (m) => T(m).margem);
  if (apertada) html += `<p class="dica-uso">Disputa mais apertada entre os municípios maiores: <b>${apertada.nome}</b> (${apertada.uf}), ${fmt1.format(T(apertada).margem)} p.p.</p>`;
  const m = estado.selecionado;
  if (m && (estado.uf === "BR" || m.uf === estado.uf) && T(m)?.validos != null) {
    const t = T(m);
    html += `<h3 style="margin-top:18px">${m.nome}</h3>
      <div class="mini-barra"><span style="width:${t.A}%;background:${COR.a}"></span><span style="width:${100 - t.A - t.B}%;background:${COR.outros}"></span><span style="width:${t.B}%;background:${COR.b}"></span></div>
      <dl><dt>${A().rotulo}</dt><dd>${pct(t.A)}</dd><dt>${B().rotulo}</dt><dd>${pct(t.B)}</dd>
      <dt>Votos válidos</dt><dd>${fmtInt.format(t.validos)}</dd>` +
      (t.abst != null ? `<dt>Abstenção</dt><dd>${pct(t.abst)}</dd>` : "") + "</dl>";
  } else {
    html += `<p class="dica-uso">${estado.uf === "BR" ? "Clique num município para ver o estado de perto." : "Clique num município para ver os detalhes aqui."}</p>`;
  }
  if (estado.uf !== "BR") html += `<p><button type="button" class="voltar" id="voltar-br">Voltar ao Brasil</button></p>`;
  el.innerHTML = html;
  el.querySelectorAll(".mini-barra span").forEach((s) => { s.style.display = "block"; s.style.height = "100%"; });
  document.getElementById("voltar-br")?.addEventListener("click", () => escolherUF("BR"));
}

// ------------------------------------------------------------------ barras por UF / região

function renderBarras(seletor, linhas, clicavel) {
  const el = document.querySelector(seletor);
  el.replaceChildren();
  if (!linhas?.length) return;
  const W = largura(el);
  const rotW = W < 520 ? 34 : 120, alt = 22, gap = 6, H = linhas.length * (alt + gap) + 24;
  const x = d3.scaleLinear().domain([0, 100]).range([rotW, W - 4]);
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img")
    .attr("aria-label", "Percentual dos votos válidos por " + (clicavel ? "estado" : "região"));
  const ord = [...linhas].sort((a, b) => b.A - a.A);
  const g = svg.selectAll("g.linha").data(ord).join("g").attr("class", (d) => `linha${d.nome === estado.uf ? " destaque" : ""}`)
    .attr("transform", (d, i) => `translate(0,${i * (alt + gap)})`);
  g.append("text").attr("x", rotW - 8).attr("y", alt / 2 + 4).attr("text-anchor", "end")
    .text((d) => (clicavel && W >= 520 ? NOMES_UF[d.nome] || d.nome : d.nome));
  const segs = (d) => [["A", 0, d.A, COR.a], ["O", d.A, d.O, COR.outros], ["B", d.A + d.O, d.B, COR.b]];
  g.selectAll("rect").data((d) => segs(d).map((s) => ({ d, s }))).join("rect").attr("class", "barra-uf")
    .attr("x", ({ s }) => x(s[1])).attr("y", 0).attr("height", alt)
    .attr("width", ({ s }) => Math.max(0, x(s[1] + s[2]) - x(s[1]) - 1.5)).attr("fill", ({ s }) => s[3])
    .style("cursor", clicavel ? "pointer" : null)
    .on("mousemove", (ev, { d }) => mostrarDica(ev, `<strong>${NOMES_UF[d.nome] || d.nome}</strong>` +
      `<span class="linha-dica"><span>${A().rotulo}</span><b>${pct(d.A)}</b></span>` +
      `<span class="linha-dica"><span>Outros</span><b>${pct(d.O)}</b></span>` +
      `<span class="linha-dica"><span>${B().rotulo}</span><b>${pct(d.B)}</b></span>` +
      `<span class="linha-dica"><span>Votos válidos</span><b>${fmtInt.format(d.validos)}</b></span>` +
      (d.abst != null ? `<span class="linha-dica"><span>Abstenção</span><b>${pct(d.abst)}</b></span>` : "")))
    .on("mouseleave", esconderDica)
    .on("click", (ev, { d }) => { if (clicavel) escolherUF(d.nome); });
  g.filter((d) => x(d.A) - rotW > 44).append("text").attr("class", "rotulo-dentro").attr("x", rotW + 6).attr("y", alt / 2 + 4).text((d) => pct(d.A));
  g.filter((d) => x(100) - x(100 - d.B) > 44).append("text").attr("class", "rotulo-dentro").attr("x", W - 10).attr("y", alt / 2 + 4)
    .attr("text-anchor", "end").text((d) => pct(d.B));
  svg.append("line").attr("class", "ref").attr("x1", x(50)).attr("x2", x(50)).attr("y1", -4).attr("y2", H - 22);
  svg.append("g").attr("class", "eixo").attr("transform", `translate(0,${H - 20})`)
    .call(d3.axisBottom(x).tickValues([0, 25, 50, 75, 100]).tickFormat((d) => `${d}%`).tickSizeOuter(0));
}

// ------------------------------------------------------------------ histogramas

function histograma(seletor, valores, { inicio, fim, passo, cor, rotuloX }) {
  const el = document.querySelector(seletor);
  el.replaceChildren();
  if (!valores.length) { el.innerHTML = `<p class="vazio">Sem dados para este recorte.</p>`; return; }
  const W = largura(el, 280), H = 220, m = { t: 8, r: 8, b: 40, l: 44 };
  const bins = d3.bin().domain([inicio, fim]).thresholds(d3.range(inicio, fim + 0.001, passo))(valores.map((v) => Math.max(inicio, Math.min(fim - 1e-9, v))));
  const x = d3.scaleLinear().domain([inicio, fim]).range([m.l, W - m.r]);
  const y = d3.scaleLinear().domain([0, d3.max(bins, (b) => b.length) || 1]).nice().range([H - m.b, m.t]);
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", rotuloX);
  svg.append("g").attr("class", "grade").attr("transform", `translate(${m.l},0)`)
    .call(d3.axisLeft(y).ticks(4).tickSize(-(W - m.l - m.r)).tickFormat("")).call((g) => g.select(".domain").remove());
  svg.append("g").selectAll("rect").data(bins).join("rect")
    .attr("x", (b) => x(b.x0) + 1).attr("width", (b) => Math.max(0, x(b.x1) - x(b.x0) - 2))
    .attr("y", (b) => y(b.length)).attr("height", (b) => y(0) - y(b.length)).attr("rx", 2)
    .attr("fill", (b) => cor((b.x0 + b.x1) / 2))
    .on("mousemove", (ev, b) => mostrarDica(ev, `<strong>${fmtInt.format(b.length)} municípios</strong>${rotuloX}: ${fmtInt.format(b.x0)} a ${fmtInt.format(b.x1)}`))
    .on("mouseleave", esconderDica);
  svg.append("g").attr("class", "eixo").attr("transform", `translate(0,${H - m.b})`)
    .call(d3.axisBottom(x).ticks(W < 420 ? 5 : 9).tickFormat((d) => fmtInt.format(Math.abs(d))).tickSizeOuter(0));
  svg.append("g").attr("class", "eixo").attr("transform", `translate(${m.l},0)`).call(d3.axisLeft(y).ticks(4).tickFormat(fmtInt.format))
    .call((g) => g.select(".domain").remove());
  svg.append("text").attr("x", (m.l + W - m.r) / 2).attr("y", H - 6).attr("text-anchor", "middle").text(rotuloX);
}

function renderHistogramas() {
  const ms = doRecorte();
  const dif = ms.map((m) => (T(m)?.A == null ? null : T(m).A - T(m).B)).filter((v) => v != null);
  const nA = dif.filter((v) => v > 0).length;
  document.getElementById("explica-hist-margem").textContent =
    `Cada barra conta municípios por faixa de diferença (p.p.). À direita, vitórias de ${A().rotulo} (${fmtInt.format(nA)}); à esquerda, de ${B().rotulo} (${fmtInt.format(dif.length - nA)}).`;
  histograma("#hist-margem", dif, { inicio: -100, fim: 100, passo: 5, rotuloX: `← ${B().rotulo}  |  diferença (p.p.)  |  ${A().rotulo} →`,
    cor: (c) => (c > 0 ? COR.a : COR.b) });
  const ab = ms.map((m) => T(m)?.abst).filter((v) => v != null);
  if (!ab.length) {
    document.getElementById("hist-abst").innerHTML = `<p class="vazio">Abstenção indisponível: processe o arquivo "Detalhe da apuração" do TSE.</p>`;
  } else {
    histograma("#hist-abst", ab, { inicio: 0, fim: Math.max(40, Math.ceil(d3.max(ab) / 2) * 2), passo: 2, rotuloX: "abstenção (%)", cor: () => COR.tinta2 });
  }
}

// ------------------------------------------------------------------ tabela

function renderTabela() {
  const cols = [
    { k: "nome", t: "Município", v: (m) => m.nome },
    { k: "uf", t: "UF", v: (m) => m.uf },
    { k: "validos", t: "Votos válidos", v: (m) => T(m)?.validos, f: (v) => fmtInt.format(v) },
    { k: "A", t: `% ${A().rotulo}`, v: (m) => T(m)?.A, f: (v) => fmt1.format(v) },
    { k: "B", t: `% ${B().rotulo}`, v: (m) => T(m)?.B, f: (v) => fmt1.format(v) },
    { k: "margem", t: "Margem (p.p.)", v: (m) => T(m)?.margem, f: (v) => fmt1.format(v) },
  ];
  if (D.meta.tem_abstencao) cols.push({ k: "abst", t: "Abstenção", v: (m) => T(m)?.abst, f: (v) => pct(v) });
  const busca = estado.busca.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase();
  let linhas = doRecorte().filter((m) => T(m)?.validos != null);
  if (busca) linhas = linhas.filter((m) => m.nome.normalize("NFD").replace(/\p{Diacritic}/gu, "").toLowerCase().includes(busca));
  const col = cols.find((c) => c.k === estado.ordem) || cols[2];
  linhas.sort((a, b) => {
    const va = col.v(a), vb = col.v(b);
    const r = typeof va === "string" ? va.localeCompare(vb, "pt-BR") : (va ?? -Infinity) - (vb ?? -Infinity);
    return estado.asc ? r : -r;
  });
  const total = linhas.length;
  linhas = linhas.slice(0, estado.limite);
  const tab = document.getElementById("tabela");
  tab.innerHTML = `<thead><tr>${cols.map((c) => `<th scope="col"><button type="button" data-k="${c.k}"${c.k === estado.ordem ? ` aria-sort="${estado.asc ? "ascending" : "descending"}"` : ""}>${c.t}</button></th>`).join("")}</tr></thead>` +
    `<tbody>${linhas.map((m) => {
      const t = T(m);
      const cor = t.venc === A().nr ? COR.a : t.venc === B().nr ? COR.b : COR.outros;
      return `<tr>${cols.map((c, i) => {
        const v = c.v(m);
        const txt = v == null ? "–" : c.f ? c.f(v) : v;
        return `<td>${i === 0 ? `<span class="ponto" style="background:${cor}" title="Vencedor"></span>` : ""}${txt}</td>`;
      }).join("")}</tr>`;
    }).join("")}</tbody>`;
  tab.querySelectorAll("th button").forEach((b) => b.addEventListener("click", () => {
    const k = b.dataset.k;
    if (estado.ordem === k) estado.asc = !estado.asc; else { estado.ordem = k; estado.asc = k === "nome" || k === "uf"; }
    renderTabela();
  }));
  const rod = document.getElementById("tabela-rodape");
  rod.replaceChildren(total > estado.limite
    ? `Mostrando ${fmtInt.format(estado.limite)} de ${fmtInt.format(total)} municípios. Use a busca ou clique nos títulos para ordenar. `
    : `${fmtInt.format(total)} municípios.`);
  if (total > estado.limite) {
    const b = document.createElement("button");
    b.type = "button"; b.className = "voltar"; b.textContent = "Mostrar mais 25";
    b.addEventListener("click", () => { estado.limite += 25; renderTabela(); });
    rod.append(b);
  }
}

// ------------------------------------------------------------------ análises avançadas

function renderAvancado() {
  const av = D.avancado;
  if (!av) return;
  document.getElementById("avancado").hidden = false;
  const turnoTxt = `${av.turno}º turno`;

  if (av.transferencia) {
    const tr = av.transferencia;
    document.getElementById("an-transf").hidden = false;
    document.getElementById("txt-transf").textContent =
      `Cada linha mostra como os eleitores de uma opção do 1º turno se dividiram no 2º: de cada 100, quantos foram para cada lado. Estimativa feita com ${fmtInt.format(tr.n_secoes)} seções eleitorais; o modelo reproduz o resultado de cada seção com erro médio de ${fmt1.format(tr.erro_ajuste)} p.p.`;
    const esc = d3.scaleLinear().domain([0, 100]).range([COR.neutro, COR.a]).interpolate(d3.interpolateRgb);
    const corTexto = (v) => (v > 55 ? "#fff" : COR.tinta);
    const html = `<table class="matriz"><thead><tr><th></th>${tr.colunas.map((c) => `<th scope="col">${c}</th>`).join("")}</tr></thead><tbody>` +
      tr.linhas.map((l, i) => `<tr><th scope="row">${l}</th>${tr.colunas.map((c, j) => {
        const v = tr.pct[i][j];
        return `<td style="background:${esc(v)};color:${corTexto(v)}" title="${fmtInt.format(tr.votos[i][j])} votos estimados"><span class="v">${fmtInt.format(Math.round(v))}%</span><span class="ic">${fmtInt.format(Math.round(tr.ic_inf[i][j]))} a ${fmtInt.format(Math.round(tr.ic_sup[i][j]))}</span></td>`;
      }).join("")}</tr>`).join("") + "</tbody></table>";
    document.getElementById("graf-transf").innerHTML = `<div class="tabela-rolagem" style="border:0;background:none">${html}</div>`;
  }

  if (!av.transferencia) {
    document.getElementById("an-transf").hidden = false;
    document.getElementById("txt-transf").textContent =
      "Esta estimativa compara o 1º e o 2º turno seção por seção. Ela aparece aqui assim que os dados do 2º turno forem publicados pelo TSE e processados.";
    document.querySelector("#an-transf .ressalva").hidden = true;
  }

  if (av.espacial) {
    const es = av.espacial;
    document.getElementById("an-espacial").hidden = false;
    const forca = es.I >= 0.5 ? "forte" : es.I >= 0.3 ? "moderada" : es.I >= 0.1 ? "fraca" : "muito fraca ou nula";
    document.getElementById("txt-espacial").textContent =
      `No ${turnoTxt}, o índice de Moran é ${fmt2.format(es.I)} (p = ${fmt2.format(es.p_valor)}): uma concentração geográfica ${forca}. O índice vai de −1 a 1; perto de 0, o voto se espalha ao acaso; positivo, municípios vizinhos votam parecido. O mapa mostra onde estão os blocos estatisticamente significativos.`;
    const cores = { "Alto-Alto": COR.a, "Baixo-Baixo": COR.b, "Alto-Baixo": COR.aClara, "Baixo-Alto": COR.bClara, "Não significativo": COR.neutro };
    const nomes = { "Alto-Alto": `Bloco de ${A().rotulo}`, "Baixo-Baixo": `Bloco de ${B().rotulo}`, "Alto-Baixo": `${A().rotulo} forte, vizinhos não`, "Baixo-Alto": `${B().rotulo} forte, vizinhos não`, "Não significativo": "Sem padrão significativo" };
    const catDe = new Map(M.map((m, i) => [m.cd, es.lisa[i] == null ? null : es.categorias[es.lisa[i]]]));
    const svg = d3.select("#mapa-lisa");
    const W = 640;
    const proj = d3.geoMercator().fitWidth(W, D.ufs);
    const [[, y0], [, y1]] = d3.geoPath(proj).bounds(D.ufs);
    const H = Math.ceil(y1 - y0);
    proj.fitExtent([[0, 0], [W, H]], D.ufs);
    const cam = d3.geoPath(proj);
    svg.attr("viewBox", `0 0 ${W} ${H}`);
    svg.append("g").selectAll("path").data(D.malha.features).join("path").attr("d", cam)
      .attr("fill", (f) => { const c = catDe.get(f.properties.c); return c ? cores[c] : COR.semDado; })
      .on("mousemove", (ev, f) => { const m = indicePorCodigo.get(f.properties.c); const c = catDe.get(f.properties.c); if (m) mostrarDica(ev, `<strong>${m.nome} (${m.uf})</strong>${nomes[c] || "Sem dados"}`); })
      .on("mouseleave", esconderDica);
    svg.append("g").selectAll("path").data(D.ufs.features).join("path").attr("class", "uf-contorno").attr("d", cam);
    const cont = d3.rollup([...catDe.values()].filter(Boolean), (v) => v.length, (c) => c);
    document.getElementById("legenda-lisa").innerHTML = Object.keys(cores).map((k) =>
      `<span class="item"><span class="amostra" style="background:${cores[k]}"></span>${nomes[k]} (${fmtInt.format(cont.get(k) || 0)})</span>`).join("");
  }

  if (av.regressao) {
    const rg = av.regressao;
    document.getElementById("an-regressao").hidden = false;
    document.getElementById("txt-regressao").textContent =
      `Quanto muda o percentual de ${A().rotulo} (${turnoTxt}) quando cada indicador aumenta um desvio-padrão, mantendo os demais e a região constantes. Regressão linear ponderada pelos votos válidos de ${fmtInt.format(rg.n)} municípios, que explica ${fmtInt.format(Math.round(rg.r2 * 100))}% da variação entre eles (R²). Linhas cinzas não são estatisticamente diferentes de zero.`;
    graficoCoeficientes("#graf-regressao", rg.coef);
  }

  if (av.gbm) {
    const g = av.gbm;
    document.getElementById("an-gbm").hidden = false;
    const util = g.mae < g.mae_base * 0.95 && g.r2 > 0.05;
    document.getElementById("txt-gbm").textContent =
      `Um modelo de gradient boosting tenta prever o percentual de ${A().rotulo} em cada município a partir dos indicadores sociais. Testado em estados que não viu no treino, erra em média ${fmt1.format(g.mae)} p.p.; um palpite pela média erraria ${fmt1.format(g.mae_base)} p.p. ` +
      (util
        ? `Ele explica ${fmtInt.format(Math.round(g.r2 * 100))}% da variação entre municípios. Abaixo, os indicadores que mais pesam na previsão.`
        : "Ou seja, os indicadores sociais quase não ajudam a prever o resultado nesta eleição; a importância abaixo deve ser lida com isso em mente.");
    graficoImportancia("#graf-gbm", g.importancia);
  }
}

function graficoCoeficientes(seletor, coef) {
  const el = document.querySelector(seletor);
  el.replaceChildren();
  const W = largura(el), rotW = W < 520 ? 150 : 220, alt = 28, H = coef.length * alt + 40;
  const lim = d3.max(coef, (c) => Math.max(Math.abs(c.ic_inf), Math.abs(c.ic_sup))) || 1;
  const x = d3.scaleLinear().domain([-lim, lim]).nice().range([rotW, W - 10]);
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Coeficientes da regressão");
  svg.append("line").attr("class", "ref").attr("x1", x(0)).attr("x2", x(0)).attr("y1", 0).attr("y2", H - 30);
  const g = svg.selectAll("g.c").data(coef).join("g").attr("transform", (d, i) => `translate(0,${i * alt + 14})`);
  const sig = (d) => d.p < 0.05;
  g.append("text").attr("x", rotW - 10).attr("y", 4).attr("text-anchor", "end").text((d) => d.var);
  g.append("line").attr("x1", (d) => x(d.ic_inf)).attr("x2", (d) => x(d.ic_sup)).attr("stroke-width", 3).attr("stroke-linecap", "round")
    .attr("stroke", (d) => (sig(d) ? (d.coef > 0 ? COR.a : COR.b) : COR.outros));
  g.append("circle").attr("cx", (d) => x(d.coef)).attr("r", 5).attr("stroke", COR.superficie).attr("stroke-width", 1.5)
    .attr("fill", (d) => (sig(d) ? (d.coef > 0 ? COR.a : COR.b) : COR.outros))
    .on("mousemove", (ev, d) => mostrarDica(ev, `<strong>${d.var}</strong>Efeito: ${pp(d.coef)}<br>IC 95%: ${fmt1.format(d.ic_inf)} a ${fmt1.format(d.ic_sup)}<br>p = ${d.p < 0.001 ? "< 0,001" : fmt2.format(d.p)}`))
    .on("mouseleave", esconderDica);
  svg.append("g").attr("class", "eixo").attr("transform", `translate(0,${H - 26})`)
    .call(d3.axisBottom(x).ticks(6).tickFormat((d) => `${d > 0 ? "+" : d < 0 ? "−" : ""}${fmtInt.format(Math.abs(d))}`).tickSizeOuter(0));
}

function graficoImportancia(seletor, imp) {
  const el = document.querySelector(seletor);
  el.replaceChildren();
  const W = largura(el), rotW = W < 520 ? 150 : 220, alt = 26, H = imp.length * alt + 30;
  const x = d3.scaleLinear().domain([0, d3.max(imp, (d) => d.valor) || 1]).nice().range([rotW, W - 50]);
  const svg = d3.select(el).append("svg").attr("viewBox", `0 0 ${W} ${H}`).attr("role", "img").attr("aria-label", "Importância dos indicadores");
  const g = svg.selectAll("g.i").data(imp).join("g").attr("transform", (d, i) => `translate(0,${i * alt})`);
  g.append("text").attr("x", rotW - 10).attr("y", alt / 2 + 4).attr("text-anchor", "end").text((d) => d.var);
  g.append("rect").attr("x", rotW).attr("y", 4).attr("height", alt - 8).attr("rx", 3)
    .attr("width", (d) => x(d.valor) - rotW).attr("fill", COR.tinta2);
  g.append("text").attr("x", (d) => x(d.valor) + 6).attr("y", alt / 2 + 4).text((d) => `${fmt1.format(d.valor)} p.p.`);
}

// ------------------------------------------------------------------ controles e ciclo

function escolherUF(uf, municipio = null) {
  estado.uf = uf;
  estado.selecionado = municipio;
  document.getElementById("ctl-uf").value = uf;
  renderTudo();
  if (uf !== "BR") document.getElementById("mapa").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
}

function renderControles() {
  const ts = D.meta.turnos;
  botoesSegmentados(document.getElementById("ctl-turno"),
    [1, 2].map((t) => ({ valor: t, rotulo: `${t}º turno`, desabilitado: !ts.includes(t), motivo: "Ainda não publicado pelo TSE" })),
    estado.turno, (t) => { estado.turno = t; renderTudo(); });
  const met = [{ v: "margem", t: "Quem venceu" }];
  if (D.meta.tem_abstencao) met.push({ v: "abst", t: "Abstenção" });
  if (D.meta.tem_swing) {
    for (const nr of Object.keys(D.municipios.swing.por_numero)) {
      met.push({ v: `sw${nr}`, t: `Variação de ${D.meta.candidatos[nr]} desde ${D.meta.ano_comparacao}` });
    }
  }
  const sel = document.getElementById("ctl-metrica");
  sel.innerHTML = met.map((m) => `<option value="${m.v}"${m.v === estado.metrica ? " selected" : ""}>${m.t}</option>`).join("");
  botoesSegmentados(document.getElementById("ctl-vista"),
    [{ valor: "area", rotulo: "Por área" }, { valor: "prop", rotulo: "Por votos" }],
    estado.vista, (v) => { estado.vista = v; renderControles(); renderMapa(); });
}

function renderTudo() {
  renderControles();
  renderApuracao();
  renderMapa();
  renderPainel();
  renderBarras("#graf-uf", D.agregados.uf[String(estado.turno)], true);
  renderBarras("#graf-regiao", D.agregados.regiao[String(estado.turno)], false);
  renderHistogramas();
  renderTabela();
}

async function iniciar() {
  lerCores();
  try {
    await carregar();
  } catch (e) {
    document.getElementById("conteudo").innerHTML =
      `<p class="vazio">Não foi possível carregar os dados (${e.message}). Gere-os com <code>python -m eleicoes.exportar_site</code> e abra a página por um servidor, por exemplo <code>python -m http.server -d site 8000</code>.</p>`;
    console.error(e);
    return;
  }
  const selUF = document.getElementById("ctl-uf");
  for (const uf of [...new Set(M.map((m) => m.uf))].sort((a, b) => (NOMES_UF[a] || a).localeCompare(NOMES_UF[b] || b, "pt-BR"))) {
    selUF.add(new Option(NOMES_UF[uf] || uf, uf));
  }
  selUF.addEventListener("change", () => escolherUF(selUF.value));
  document.getElementById("ctl-metrica").addEventListener("change", (e) => { estado.metrica = e.target.value; renderMapa(); });
  document.getElementById("busca").addEventListener("input", (e) => { estado.busca = e.target.value; estado.limite = 25; renderTabela(); });
  document.getElementById("gerado").textContent = `Dados gerados em ${D.meta.gerado_em}.`;
  renderTudo();
  renderAvancado();

  let espera;
  window.addEventListener("resize", () => {
    clearTimeout(espera);
    espera = setTimeout(() => {
      renderBarras("#graf-uf", D.agregados.uf[String(estado.turno)], true);
      renderBarras("#graf-regiao", D.agregados.regiao[String(estado.turno)], false);
      renderHistogramas();
      if (D.avancado?.regressao) graficoCoeficientes("#graf-regressao", D.avancado.regressao.coef);
      if (D.avancado?.gbm) graficoImportancia("#graf-gbm", D.avancado.gbm.importancia);
    }, 200);
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    lerCores();
    renderTudo();
    d3.select("#mapa-lisa").selectAll("*").remove();
    renderAvancado();
  });
}

iniciar();
