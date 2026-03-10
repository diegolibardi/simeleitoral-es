/**
 * EleitOS — Módulo de Relatório PDF
 * Geração client-side via jsPDF (sem envio ao servidor)
 * Lei 9.504/97 + Lei 14.211/2021
 */

// ─── Paleta ───────────────────────────────────────────────────────────────────
const PDF = {
  // Cores principais
  azul:    [59,  130, 246],
  verde:   [16,  185, 129],
  ouro:    [245, 158, 11],
  vermelho:[239, 68,  68],
  roxo:    [139, 92,  246],
  rosa:    [244, 114, 182],
  cinza:   [100, 116, 139],

  // Tons de fundo
  bgEscuro: [8,  12,  20],
  surface:  [15, 22,  35],
  surface2: [20, 30,  50],
  borda:    [30, 45,  70],

  // Texto
  textoBranco: [255, 255, 255],
  textoClaro:  [226, 232, 240],
  textoMedio:  [148, 163, 184],
  textoFraco:  [71,  85,  105],

  // Dimensões A4 (mm)
  W: 210,
  H: 297,
  M: 14,   // margem
};

// ─── Helpers ─────────────────────────────────────────────────────────────────
function pdfFmt(n) {
  return Number(n || 0).toLocaleString('pt-BR');
}

function pdfPct(v, total) {
  if (!total) return '0,0%';
  return ((v / total) * 100).toFixed(1).replace('.', ',') + '%';
}

function corPartido(idx) {
  const cores = [
    [59,130,246],[16,185,129],[245,158,11],[139,92,246],
    [239,68,68], [20,184,166],[249,115,22],[236,72,153],
    [132,204,22],[6,182,212],
  ];
  return cores[idx % cores.length];
}

// ─── Rodapé padrão ────────────────────────────────────────────────────────────
function rodape(doc, pagina, totalPags, nomeSimulacao) {
  const y = PDF.H - 8;
  doc.setFillColor(...PDF.borda);
  doc.rect(0, PDF.H - 12, PDF.W, 12, 'F');

  doc.setFontSize(7);
  doc.setTextColor(...PDF.textoFraco);
  doc.text('EleitOS — Sistema de Simulação Eleitoral', PDF.M, y);
  doc.text(`Lei 9.504/97 + Lei 14.211/2021`, PDF.W / 2, y, { align: 'center' });
  doc.text(`Pág. ${pagina}/${totalPags}`, PDF.W - PDF.M, y, { align: 'right' });

  doc.setFontSize(6.5);
  doc.setTextColor(...PDF.textoFraco);
  doc.text(nomeSimulacao, PDF.M, y - 4);
  doc.text(new Date().toLocaleString('pt-BR'), PDF.W - PDF.M, y - 4, { align: 'right' });
}

// ─── Cabeçalho de seção ───────────────────────────────────────────────────────
function secao(doc, y, titulo, cor) {
  cor = cor || PDF.azul;
  doc.setFillColor(...cor);
  doc.rect(PDF.M, y, 3, 6, 'F');
  doc.setFontSize(10);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(...PDF.textoClaro);
  doc.text(titulo, PDF.M + 5, y + 4.5);
  doc.setFontSize(8);
  doc.setFont('helvetica', 'normal');
  return y + 10;
}

// ─── Linha separadora ─────────────────────────────────────────────────────────
function separador(doc, y) {
  doc.setDrawColor(...PDF.borda);
  doc.setLineWidth(0.2);
  doc.line(PDF.M, y, PDF.W - PDF.M, y);
  return y + 4;
}

// ─── KPI card ─────────────────────────────────────────────────────────────────
function kpiCard(doc, x, y, w, h, valor, label, cor) {
  cor = cor || PDF.azul;
  doc.setFillColor(20, 30, 50);
  doc.roundedRect(x, y, w, h, 2, 2, 'F');
  doc.setFillColor(...cor);
  doc.rect(x, y, 2, h, 'F');

  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(...cor);
  doc.text(String(valor), x + w / 2, y + h / 2 - 1, { align: 'center' });

  doc.setFontSize(6.5);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...PDF.textoMedio);
  doc.text(label, x + w / 2, y + h / 2 + 5, { align: 'center' });
}

// ─── Tabela genérica ─────────────────────────────────────────────────────────
function tabela(doc, y, colunas, linhas, opcoes) {
  opcoes = opcoes || {};
  const largTotal = PDF.W - 2 * PDF.M;
  const altLin    = opcoes.altLin || 6.5;
  const altCab    = opcoes.altCab || 7.5;

  // Cabeçalho
  doc.setFillColor(...(opcoes.corCab || PDF.surface2));
  doc.rect(PDF.M, y, largTotal, altCab, 'F');
  doc.setFontSize(7);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(...PDF.textoMedio);

  let xc = PDF.M + 2;
  colunas.forEach(col => {
    const align = col.align || 'left';
    const tx = align === 'right'  ? xc + col.w - 2
              : align === 'center' ? xc + col.w / 2
              : xc;
    doc.text(col.label, tx, y + 5, { align });
    xc += col.w;
  });
  y += altCab;

  // Linhas
  linhas.forEach((linha, ri) => {
    // Verificar quebra de página
    if (y + altLin > PDF.H - 16) return; // trunca — caller deve paginar

    if (ri % 2 === 0) {
      doc.setFillColor(15, 22, 35);
      doc.rect(PDF.M, y, largTotal, altLin, 'F');
    }

    let xl = PDF.M + 2;
    colunas.forEach((col, ci) => {
      const val  = linha[ci] !== undefined ? String(linha[ci]) : '';
      const cor  = linha._cores && linha._cores[ci] ? linha._cores[ci] : PDF.textoClaro;
      const bold = linha._bold && linha._bold[ci];
      const align = col.align || 'left';
      const tx = align === 'right'  ? xl + col.w - 2
                : align === 'center' ? xl + col.w / 2
                : xl;

      doc.setFont('helvetica', bold ? 'bold' : 'normal');
      doc.setFontSize(7);
      doc.setTextColor(...cor);
      doc.text(val, tx, y + 4.5, { align });
      xl += col.w;
    });
    y += altLin;
  });

  return y;
}

// ═════════════════════════════════════════════════════════════════════════════
// GERADOR PRINCIPAL
// ═════════════════════════════════════════════════════════════════════════════
function gerarRelatorioPDF(resultado, nomeSimulacao, cargo) {
  if (!resultado) {
    alert('Calcule a simulação antes de exportar o relatório.');
    return;
  }

  const r   = resultado;
  const nom = nomeSimulacao || 'Simulação Eleitoral';
  const { jsPDF } = window.jspdf;
  const doc = new jsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

  // Estimar total de páginas (aproximado)
  const totalPags = 4;
  let pag = 1;

  // ══════════════════════════════════════════════════════════════════════════
  // PÁGINA 1 — Capa + Resumo Geral
  // ══════════════════════════════════════════════════════════════════════════

  // Fundo escuro
  doc.setFillColor(...PDF.bgEscuro);
  doc.rect(0, 0, PDF.W, PDF.H, 'F');

  // Faixa de topo
  doc.setFillColor(...PDF.azul);
  doc.rect(0, 0, PDF.W, 38, 'F');

  // Ícone / logo text
  doc.setFontSize(22);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(255, 255, 255);
  doc.text('⚡ EleitOS', PDF.M, 16);

  doc.setFontSize(10);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(186, 230, 253);
  doc.text('Sistema de Simulação Eleitoral — Espírito Santo', PDF.M, 23);

  doc.setFontSize(8);
  doc.setTextColor(147, 197, 253);
  doc.text('Lei 9.504/97 + Lei 14.211/2021 (Regra 80/20)', PDF.M, 29);

  // Nome da simulação e cargo
  doc.setFontSize(9);
  doc.setTextColor(255, 255, 255);
  doc.text(nom, PDF.W - PDF.M, 16, { align: 'right' });
  doc.setFontSize(8);
  doc.setTextColor(186, 230, 253);
  doc.text(cargo || 'Deputado Federal', PDF.W - PDF.M, 23, { align: 'right' });
  doc.text(new Date().toLocaleDateString('pt-BR', { day:'2-digit', month:'long', year:'numeric' }), PDF.W - PDF.M, 30, { align: 'right' });

  // ── KPIs principais ───────────────────────────────────────────────────────
  let y = 46;
  const cw = (PDF.W - 2 * PDF.M - 9) / 4; // 4 cards por linha
  const ch = 20;

  kpiCard(doc, PDF.M,           y, cw, ch, pdfFmt(r.qe),          'Quociente Eleitoral', PDF.ouro);
  kpiCard(doc, PDF.M + cw + 3,  y, cw, ch, pdfFmt(r.total_validos),'Votos Válidos',       PDF.azul);
  kpiCard(doc, PDF.M + (cw+3)*2,y, cw, ch, r.total_eleitos,        'Eleitos',             PDF.verde);
  kpiCard(doc, PDF.M + (cw+3)*3,y, cw, ch,
    r.partidos.filter(p=>p.atingiu_qe).length + ' partidos', 'Atingiram QE', PDF.roxo);

  y += ch + 4;

  const cw2 = (PDF.W - 2 * PDF.M - 9) / 4;
  const comp = r.comparecimento || 1;
  kpiCard(doc, PDF.M,            y, cw2, ch, pdfFmt(r.comparecimento),  'Comparecimento',     PDF.azul);
  kpiCard(doc, PDF.M + cw2+3,    y, cw2, ch, pdfFmt(r.total_brancos),   'Votos Brancos',      PDF.cinza);
  kpiCard(doc, PDF.M + (cw2+3)*2,y, cw2, ch, pdfFmt(r.total_nulos),    'Votos Nulos',        PDF.vermelho);
  kpiCard(doc, PDF.M + (cw2+3)*3,y, cw2, ch,
    pdfPct(r.abstencao, r.eleitores), 'Abstenção', [100, 116, 139]);
  y += ch + 6;

  // ── Composição do comparecimento ─────────────────────────────────────────
  y = secao(doc, y, 'Composição do Comparecimento', PDF.azul);

  const largBarra = PDF.W - 2 * PDF.M;
  const pctV = r.total_validos / comp;
  const pctB = r.total_brancos / comp;
  const pctN = r.total_nulos   / comp;

  // Barra empilhada
  doc.setFillColor(30, 45, 70);
  doc.roundedRect(PDF.M, y, largBarra, 8, 1, 1, 'F');
  let xb = PDF.M;
  if (pctV > 0) { doc.setFillColor(...PDF.azul);    doc.rect(xb, y, largBarra * pctV, 8, 'F'); xb += largBarra * pctV; }
  if (pctB > 0) { doc.setFillColor(...PDF.ouro);    doc.rect(xb, y, largBarra * pctB, 8, 'F'); xb += largBarra * pctB; }
  if (pctN > 0) { doc.setFillColor(...PDF.vermelho); doc.rect(xb, y, largBarra * pctN, 8, 'F'); }
  y += 11;

  // Legenda
  const legItems = [
    { label: 'Válidos',  val: pdfFmt(r.total_validos), pct: pdfPct(r.total_validos, comp), cor: PDF.azul    },
    { label: 'Brancos',  val: pdfFmt(r.total_brancos), pct: pdfPct(r.total_brancos, comp), cor: PDF.ouro    },
    { label: 'Nulos',    val: pdfFmt(r.total_nulos),   pct: pdfPct(r.total_nulos,   comp), cor: PDF.vermelho },
    { label: 'Abstenção',val: pdfFmt(r.abstencao),     pct: pdfPct(r.abstencao, r.eleitores||1), cor: PDF.cinza },
  ];
  const lw = (PDF.W - 2*PDF.M) / 4;
  legItems.forEach((it, i) => {
    const lx = PDF.M + i * lw;
    doc.setFillColor(...it.cor);
    doc.rect(lx, y, 3, 3, 'F');
    doc.setFontSize(7);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...it.cor);
    doc.text(it.pct, lx + 5, y + 3);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...PDF.textoMedio);
    doc.text(`${it.label}: ${it.val}`, lx + 5, y + 7);
  });
  y += 12;

  // ── Referências legais ────────────────────────────────────────────────────
  y = separador(doc, y);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...PDF.textoFraco);
  const refs = [
    `QE (Quociente Eleitoral): ${pdfFmt(r.qe)}  |  80% QE: ${pdfFmt(r.minimo_80_qe)}  |  20% QE: ${pdfFmt(r.minimo_20_qe)}  |  10% QE: ${pdfFmt(r.minimo_individual)}`,
    `Eleitores aptos: ${pdfFmt(r.eleitores)}  |  Vagas disputadas: ${r.vagas}  |  Vagas por QP: ${r.vagas_qp_total}  |  Vagas por Sobra: ${r.vagas_sobras}`,
  ];
  refs.forEach(ref => { doc.text(ref, PDF.M, y); y += 4; });
  y += 2;

  // ── Partidos — tabela resumida ────────────────────────────────────────────
  y = secao(doc, y, 'Resultado por Partido', PDF.roxo);

  const colsPartidos = [
    { label: 'Partido',    w: 22 },
    { label: 'Votos',      w: 26, align: 'right' },
    { label: '% Válidos',  w: 20, align: 'right' },
    { label: '≥ QE',       w: 12, align: 'center' },
    { label: '≥ 80% QE',   w: 16, align: 'center' },
    { label: 'Vagas QP',   w: 18, align: 'center' },
    { label: 'Sobras',     w: 16, align: 'center' },
    { label: 'Total',      w: 14, align: 'center' },
    { label: '♂',          w: 10, align: 'center' },
    { label: '♀',          w: 10, align: 'center' },
    { label: 'Eleitos',    w: 18, align: 'center' },
  ];

  const linhasPartidos = r.partidos
    .sort((a, b) => b.vagas_total - a.vagas_total || b.total_votos - a.total_votos)
    .map(p => {
      const cands_p = r.candidatos.filter(c => c.partido === p.sigla);
      const nM = cands_p.filter(c => c.sexo === 'M').length;
      const nF = cands_p.filter(c => c.sexo === 'F').length;
      const eleitos_p = cands_p.filter(c => c.status === 'ELEITO').length;
      const row = [
        p.sigla,
        pdfFmt(p.total_votos),
        pdfPct(p.total_votos, r.total_validos),
        p.atingiu_qe    ? '✓' : '✗',
        p.atingiu_80_qe ? '✓' : '✗',
        p.vagas_qp,
        p.vagas_sobra,
        p.vagas_total || '—',
        nM || '—',
        nF || '—',
        eleitos_p || '—',
      ];
      row._cores = [
        PDF.textoClaro,
        PDF.textoClaro,
        PDF.textoMedio,
        p.atingiu_qe    ? PDF.verde : PDF.vermelho,
        p.atingiu_80_qe ? PDF.verde : PDF.vermelho,
        PDF.azul,
        PDF.roxo,
        p.vagas_total > 0 ? PDF.ouro : PDF.textoMedio,
        PDF.azul,
        PDF.rosa,
        eleitos_p > 0 ? PDF.verde : PDF.textoMedio,
      ];
      row._bold = [true, false, false, false, false, false, false, true, false, false, true];
      return row;
    });

  y = tabela(doc, y, colsPartidos, linhasPartidos, { altLin: 6, altCab: 7 });

  rodape(doc, pag, totalPags, nom);

  // ══════════════════════════════════════════════════════════════════════════
  // PÁGINA 2 — Eleitos
  // ══════════════════════════════════════════════════════════════════════════
  doc.addPage();
  pag++;

  doc.setFillColor(...PDF.bgEscuro);
  doc.rect(0, 0, PDF.W, PDF.H, 'F');

  // Faixa
  doc.setFillColor(...PDF.verde);
  doc.rect(0, 0, PDF.W, 18, 'F');
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(255,255,255);
  doc.text('Candidatos Eleitos', PDF.M, 12);
  doc.setFontSize(8);
  doc.setTextColor(187, 247, 208);
  doc.text(`${r.total_eleitos} eleitos — ${cargo || 'Deputado Federal'}`, PDF.W - PDF.M, 12, { align: 'right' });

  y = 24;

  // Painel de gênero dos eleitos
  const eleitos = r.candidatos.filter(c => c.status === 'ELEITO');
  const eM = eleitos.filter(c => c.sexo === 'M').length;
  const eF = eleitos.filter(c => c.sexo === 'F').length;
  const eTot = eleitos.length || 1;

  const gw = (PDF.W - 2*PDF.M - 6) / 3;
  kpiCard(doc, PDF.M,        y, gw, 16, eM, '♂ Homens eleitos',  PDF.azul);
  kpiCard(doc, PDF.M+gw+3,   y, gw, 16, eF, '♀ Mulheres eleitas', PDF.rosa);
  kpiCard(doc, PDF.M+(gw+3)*2,y,gw, 16,
    pdfPct(eF, eTot), '% Mulheres',
    eF/eTot >= 0.30 ? PDF.verde : PDF.vermelho);
  y += 20;

  // Barra de gênero
  const largG = PDF.W - 2*PDF.M;
  doc.setFillColor(30, 45, 70);
  doc.roundedRect(PDF.M, y, largG, 5, 1, 1, 'F');
  const pctEM = eM / eTot;
  const pctEF = eF / eTot;
  if (pctEM > 0) { doc.setFillColor(...PDF.azul); doc.rect(PDF.M, y, largG * pctEM, 5, 'F'); }
  if (pctEF > 0) { doc.setFillColor(...PDF.rosa); doc.rect(PDF.M + largG * pctEM, y, largG * pctEF, 5, 'F'); }
  y += 9;

  // Tabela de eleitos
  y = secao(doc, y, 'Lista de Eleitos', PDF.verde);

  const colsEleitos = [
    { label: '#',        w: 8,  align: 'center' },
    { label: 'Candidato',w: 52 },
    { label: 'Partido',  w: 22 },
    { label: 'Sexo',     w: 14, align: 'center' },
    { label: 'Votos',    w: 26, align: 'right'  },
    { label: 'Eleito por',w:20, align: 'center' },
    { label: '% Válidos',w: 20, align: 'right'  },
  ];

  const linhasEleitos = eleitos
    .sort((a, b) => b.votos - a.votos)
    .map((c, i) => {
      const row = [
        i + 1,
        c.nome,
        c.partido,
        c.sexo === 'M' ? '♂ Mas' : c.sexo === 'F' ? '♀ Fem' : '—',
        pdfFmt(c.votos),
        c.eleito_por || '—',
        pdfPct(c.votos, r.total_validos),
      ];
      row._cores = [
        PDF.textoMedio,
        PDF.textoClaro,
        PDF.azul,
        c.sexo === 'M' ? PDF.azul : c.sexo === 'F' ? PDF.rosa : PDF.cinza,
        PDF.textoClaro,
        c.eleito_por === 'QP' ? PDF.verde : PDF.roxo,
        PDF.textoMedio,
      ];
      row._bold = [false, true, false, true, true, false, false];
      return row;
    });

  y = tabela(doc, y, colsEleitos, linhasEleitos, { altLin: 6.5, altCab: 7.5 });
  rodape(doc, pag, totalPags, nom);

  // ══════════════════════════════════════════════════════════════════════════
  // PÁGINA 3 — Todos os candidatos por partido
  // ══════════════════════════════════════════════════════════════════════════
  doc.addPage();
  pag++;

  doc.setFillColor(...PDF.bgEscuro);
  doc.rect(0, 0, PDF.W, PDF.H, 'F');

  doc.setFillColor(...PDF.roxo);
  doc.rect(0, 0, PDF.W, 18, 'F');
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(255,255,255);
  doc.text('Candidatos por Partido', PDF.M, 12);
  doc.setFontSize(8);
  doc.setTextColor(221, 214, 254);
  doc.text(`${r.candidatos.length} candidatos — ${cargo || 'Deputado Federal'}`, PDF.W - PDF.M, 12, { align: 'right' });

  y = 24;

  const colsCands = [
    { label: '#',       w: 8,  align: 'center' },
    { label: 'Candidato',w:50 },
    { label: 'Partido', w: 20 },
    { label: 'Sexo',    w: 12, align: 'center' },
    { label: 'Votos',   w: 24, align: 'right'  },
    { label: 'Status',  w: 22, align: 'center' },
    { label: 'Critério',w: 24, align: 'center' },
    { label: '% Válidos',w:22, align: 'right'  },
  ];

  const partidosOrdenados = [...r.partidos]
    .sort((a, b) => b.vagas_total - a.vagas_total || b.total_votos - a.total_votos);

  for (const p of partidosOrdenados) {
    if (y > PDF.H - 30) {
      rodape(doc, pag, totalPags, nom);
      doc.addPage();
      pag++;
      doc.setFillColor(...PDF.bgEscuro);
      doc.rect(0, 0, PDF.W, PDF.H, 'F');
      y = 14;
    }

    // Header do partido
    const cor_p = corPartido(r.partidos.indexOf(p));
    doc.setFillColor(...cor_p);
    doc.rect(PDF.M, y, 3, 8, 'F');
    doc.setFillColor(20, 30, 50);
    doc.rect(PDF.M + 3, y, PDF.W - 2*PDF.M - 3, 8, 'F');

    const cands_p  = r.candidatos.filter(c => c.partido === p.sigla).sort((a,b) => b.votos - a.votos);
    const nM_p     = cands_p.filter(c => c.sexo === 'M').length;
    const nF_p     = cands_p.filter(c => c.sexo === 'F').length;
    const eleitos_p = cands_p.filter(c => c.status === 'ELEITO').length;

    doc.setFontSize(9);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...cor_p);
    doc.text(p.sigla, PDF.M + 6, y + 5.5);

    doc.setFontSize(7);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...PDF.textoMedio);
    doc.text(
      `${cands_p.length} candidatos  |  ♂ ${nM_p}  ♀ ${nF_p}  |  ${pdfFmt(p.total_votos)} votos  |  ${eleitos_p} eleito${eleitos_p !== 1 ? 's' : ''}  |  QP: ${p.vagas_qp}  Sobra: ${p.vagas_sobra}`,
      PDF.M + 24, y + 5.5
    );
    y += 8;

    const linhas_p = cands_p.map((c, ci) => {
      const statusCor = c.status === 'ELEITO'    ? PDF.verde
                      : c.status === 'SUPLENTE'  ? PDF.ouro
                      : PDF.vermelho;
      const row = [
        ci + 1,
        c.nome,
        c.partido,
        c.sexo === 'M' ? '♂' : c.sexo === 'F' ? '♀' : '?',
        pdfFmt(c.votos),
        c.status,
        c.eleito_por || (c.status === 'SUPLENTE' ? `Sup. #${c.posicao}` : '—'),
        pdfPct(c.votos, r.total_validos),
      ];
      row._cores = [
        PDF.textoFraco,
        c.status === 'ELEITO' ? PDF.textoClaro : PDF.textoMedio,
        cor_p,
        c.sexo === 'M' ? PDF.azul : PDF.rosa,
        PDF.textoClaro,
        statusCor,
        PDF.textoMedio,
        PDF.textoFraco,
      ];
      row._bold = [false, c.status === 'ELEITO', false, false, c.status === 'ELEITO', true, false, false];
      return row;
    });

    // Mini-tabela por partido (sem cabeçalho repetido — só na primeira)
    const altL = 5.8;
    linhas_p.forEach((linha, ri) => {
      if (y + altL > PDF.H - 16) {
        rodape(doc, pag, totalPags, nom);
        doc.addPage();
        pag++;
        doc.setFillColor(...PDF.bgEscuro);
        doc.rect(0, 0, PDF.W, PDF.H, 'F');
        y = 14;
      }
      if (ri % 2 === 0) {
        doc.setFillColor(15, 22, 35);
        doc.rect(PDF.M, y, PDF.W - 2*PDF.M, altL, 'F');
      }
      let xl = PDF.M + 2;
      colsCands.forEach((col, ci) => {
        const val   = linha[ci] !== undefined ? String(linha[ci]) : '';
        const cor   = linha._cores && linha._cores[ci] ? linha._cores[ci] : PDF.textoClaro;
        const bold  = linha._bold && linha._bold[ci];
        const align = col.align || 'left';
        const tx    = align === 'right'  ? xl + col.w - 2
                    : align === 'center' ? xl + col.w / 2 : xl;
        doc.setFont('helvetica', bold ? 'bold' : 'normal');
        doc.setFontSize(6.8);
        doc.setTextColor(...cor);
        doc.text(val, tx, y + 4, { align });
        xl += col.w;
      });
      y += altL;
    });
    y += 3;
  }

  rodape(doc, pag, totalPags, nom);

  // ══════════════════════════════════════════════════════════════════════════
  // PÁGINA 4 — Memória de Cálculo
  // ══════════════════════════════════════════════════════════════════════════
  doc.addPage();
  pag++;

  doc.setFillColor(...PDF.bgEscuro);
  doc.rect(0, 0, PDF.W, PDF.H, 'F');

  doc.setFillColor(...PDF.ouro);
  doc.rect(0, 0, PDF.W, 18, 'F');
  doc.setFontSize(13);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(28, 25, 23);
  doc.text('Memória de Cálculo', PDF.M, 12);
  doc.setFontSize(8);
  doc.setTextColor(92, 83, 60);
  doc.text('Lei 9.504/97 + Lei 14.211/2021 (Regra 80/20)', PDF.W - PDF.M, 12, { align: 'right' });

  y = 24;

  // Etapa 1 — Votos válidos
  y = secao(doc, y, 'ETAPA 1 — Apuração dos Votos', PDF.azul);
  const etapa1 = [
    ['Eleitores aptos',    pdfFmt(r.eleitores)],
    ['Comparecimento',     pdfFmt(r.comparecimento)],
    ['Votos válidos (nominal + legenda)', pdfFmt(r.total_validos)],
    ['Votos brancos (excluídos do QE)',  pdfFmt(r.total_brancos)],
    ['Votos nulos (excluídos do QE)',    pdfFmt(r.total_nulos)],
    ['Abstenção',          pdfFmt(r.abstencao) + ' (' + pdfPct(r.abstencao, r.eleitores) + ')'],
  ];
  etapa1.forEach(([k, v]) => {
    doc.setFontSize(7.5);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...PDF.textoMedio);
    doc.text(k, PDF.M + 4, y);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...PDF.textoClaro);
    doc.text(v, PDF.W - PDF.M, y, { align: 'right' });
    y += 5.5;
  });
  y += 2;

  // Etapa 2 — QE
  y = secao(doc, y, 'ETAPA 2 — Quociente Eleitoral (QE)', PDF.ouro);
  const formula = `QE = Votos Válidos ÷ Vagas = ${pdfFmt(r.total_validos)} ÷ ${r.vagas} = ${pdfFmt(r.qe)}`;
  doc.setFontSize(8);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(...PDF.ouro);
  doc.text(formula, PDF.M + 4, y); y += 6;

  const etapa2 = [
    ['QE (Quociente Eleitoral)',        pdfFmt(r.qe)],
    ['80% QE — mínimo para sobras',     pdfFmt(r.minimo_80_qe)],
    ['20% QE — candidato receber sobra',pdfFmt(r.minimo_20_qe)],
    ['10% QE — mínimo individual',      pdfFmt(r.minimo_individual)],
  ];
  etapa2.forEach(([k, v]) => {
    doc.setFontSize(7.5);
    doc.setFont('helvetica', 'normal');
    doc.setTextColor(...PDF.textoMedio);
    doc.text(k, PDF.M + 4, y);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(...PDF.ouro);
    doc.text(v, PDF.W - PDF.M, y, { align: 'right' });
    y += 5.5;
  });
  y += 2;

  // Etapa 3 — QP
  y = secao(doc, y, 'ETAPA 3 — Distribuição pelo Quociente Partidário (QP)', PDF.verde);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...PDF.textoMedio);
  doc.text('Vagas QP = floor(Votos do Partido ÷ QE)  —  apenas partidos com votos ≥ QE participam', PDF.M + 4, y); y += 5;

  r.partidos
    .filter(p => p.atingiu_qe)
    .sort((a,b) => b.vagas_qp - a.vagas_qp || b.total_votos - a.total_votos)
    .forEach(p => {
      const calc = `${pdfFmt(p.total_votos)} ÷ ${pdfFmt(r.qe)} = ${p.vagas_qp} vaga${p.vagas_qp !== 1 ? 's' : ''}`;
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...PDF.verde);
      doc.text(p.sigla, PDF.M + 4, y);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...PDF.textoMedio);
      doc.text(calc, PDF.M + 22, y);
      y += 5;
    });
  y += 2;

  // Etapa 4 — Sobras
  y = secao(doc, y, 'ETAPA 4 — Distribuição das Sobras (D\'Hondt — Regra 80/20)', PDF.roxo);
  doc.setFontSize(7);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...PDF.textoMedio);
  doc.text(`Partido eligível: ≥ ${pdfFmt(r.minimo_80_qe)} votos (80% QE)  |  Candidato: ≥ ${pdfFmt(r.minimo_20_qe)} votos (20% QE)`, PDF.M + 4, y); y += 5;
  doc.text(`Vagas distribuídas por QP: ${r.vagas_qp_total}  |  Vagas restantes (sobras): ${r.vagas_sobras}`, PDF.M + 4, y); y += 5;

  const comSobra = r.partidos.filter(p => p.vagas_sobra > 0);
  if (comSobra.length > 0) {
    comSobra.sort((a,b) => b.vagas_sobra - a.vagas_sobra).forEach(p => {
      doc.setFont('helvetica', 'bold');
      doc.setTextColor(...PDF.roxo);
      doc.text(p.sigla, PDF.M + 4, y);
      doc.setFont('helvetica', 'normal');
      doc.setTextColor(...PDF.textoMedio);
      doc.text(`+${p.vagas_sobra} vaga${p.vagas_sobra > 1 ? 's' : ''} por maior média`, PDF.M + 22, y);
      y += 5;
    });
  } else {
    doc.setTextColor(...PDF.textoFraco);
    doc.text('Nenhuma vaga de sobra distribuída.', PDF.M + 4, y); y += 5;
  }

  y += 3;

  // Nota legal
  doc.setFillColor(20, 30, 50);
  doc.roundedRect(PDF.M, y, PDF.W - 2*PDF.M, 18, 2, 2, 'F');
  doc.setFillColor(...PDF.ouro);
  doc.rect(PDF.M, y, 2, 18, 'F');
  doc.setFontSize(7);
  doc.setFont('helvetica', 'bold');
  doc.setTextColor(...PDF.ouro);
  doc.text('Base Legal', PDF.M + 5, y + 5);
  doc.setFont('helvetica', 'normal');
  doc.setTextColor(...PDF.textoMedio);
  const notaLegal = [
    'Lei 9.504/97, Art. 10 — Cota de gênero: mín. 30% e máx. 70% de candidatos de cada sexo por partido.',
    'Lei 9.504/97, Art. 109 — Sistema proporcional com QE e distribuição de sobras por D\'Hondt.',
    'Lei 14.211/2021 (Regra 80/20) — Partido precisa de ≥ 80% do QE; candidato precisa de ≥ 20% do QE',
    'para receber vaga de sobra. O mínimo individual para eleição é 10% do QE.',
  ];
  notaLegal.forEach((l, i) => { doc.text(l, PDF.M + 5, y + 9 + i * 3.5); });

  rodape(doc, pag, totalPags, nom);

  // ── Salvar ────────────────────────────────────────────────────────────────
  const nomArq = (nom.replace(/[^a-zA-Z0-9À-ÿ\s]/g, '').trim().replace(/\s+/g, '_') || 'simulacao')
    + '_' + new Date().toISOString().slice(0, 10) + '.pdf';
  doc.save(nomArq);
}
