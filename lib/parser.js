function cleanText(text) {
  return text
    .replace(/\r/g, '\n')
    .replace(/[\uFFFD]/g, ' ')
    .replace(/\t/g, ' ')
    .replace(/ +/g, ' ')
    .trim();
}

function find(patterns, text, fallback = null) {
  for (const pattern of patterns) {
    const match = text.match(pattern);
    if (match && match[1]) {
      return match[1].trim();
    }
  }
  return fallback;
}

function parseNumber(value) {
  if (!value) return null;
  const match = value.match(/[-+]?[0-9][0-9.,\s]*/);
  if (!match) return null;
  const normalized = match[0].replace(/\s+/g, '').replace(',', '.');
  const parsed = parseFloat(normalized);
  return Number.isFinite(parsed) ? parsed : null;
}

function parseCurrency(text) {
  const found = find([
    /\b(F\s*CFA|FCFA|CFA|EUR|€|US\$|USD)\b/i,
    /(F\s*CFA|FCFA|CFA|EUR|€|US\$|USD)/i
  ], text);
  return found ? found.toUpperCase().replace('€', 'EUR') : 'F CFA';
}

function parseDate(text) {
  const match = text.match(/\b(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})\b/);
  return match ? match[1] : null;
}

function parseInvoiceLines(text) {
  return text
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function parseArticles(lines) {
  const articles = [];
  const articlePattern = /(.*?)(?:\s+(\d+(?:[.,]\d+)?)\s+([0-9\s.,]+)\s+([0-9\s.,]+))$/;

  for (const line of lines) {
    const match = line.match(articlePattern);
    if (match) {
      const [, designation, quantite, prixUnitaire, totalHt] = match;
      articles.push({
        reference: null,
        designation: designation.trim(),
        quantite: parseNumber(quantite),
        unite: null,
        prix_unitaire_ht: parseNumber(prixUnitaire),
        remise_pct: null,
        total_ht: parseNumber(totalHt)
      });
    }
  }
  return articles;
}

export function parseInvoiceText(rawText, filename = null) {
  const text = cleanText(rawText);
  const lines = parseInvoiceLines(text);
  const lower = text.toLowerCase();

  const societe_emettrice = find([
    /^(.*?)\s*facture/i,
    /^(.+?)\s*\b(?:facture|invoice)\b/i
  ], text, lines[0] || null);

  const client = find([
    /client(?:\s*[:\-])?\s*(.+)/i,
    /facturé à\s*(.+)/i,
    /pour\s+le\s+client\s*[:\-]?\s*(.+)/i
  ], text, null);

  const numero_facture = find([
    /num(?:éro|ero)?\s*facture\s*[:\-]?\s*([A-Z0-9-]+)/i,
    /facture\s*[:\-]?\s*([A-Z0-9-]+)/i,
    /#\s*([A-Z0-9-]+)/i
  ], text, null);

  const date_emission = find([
    /date\s*d['eé]\s*facturation\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})/i,
    /date\s*d['eé]\s*émission\s*[:\-]?\s*(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})/i,
    /(\d{1,2}[\/\-.]\d{1,2}[\/\-.]\d{2,4})/
  ], text, null);

  const adresse_client = find([
    /adresse\s*client\s*[:\-]?\s*(.+)/i,
    /client\s*[:\-]?\s*(.+)/i
  ], text, null);

  const ifu = find([
    /ifu\s*[:\-]?\s*([0-9\s]+)/i,
    /identification fiscale\s*[:\-]?\s*([0-9\s]+)/i
  ], text, null);

  const rccm = find([
    /rccm\s*[:\-]?\s*([A-Z0-9\/\s]+)/i,
    /reg\.\s*com\.\s*[:\-]?\s*([A-Z0-9\/\s]+)/i
  ], text, null);

  const devise = parseCurrency(text);

  const mode_paiement = find([
    /mode\s*de\s*paiement\s*[:\-]?\s*(.+)/i,
    /(espèces|virement|chèque|carte bancaire)/i
  ], text, null);

  const taux_tva = find([
    /(\d{1,2}%)\s*tva/i,
    /tva\s*[:\-]?\s*(\d{1,2}%)/i
  ], text, null);

  const montant_ht = parseNumber(find([
    /montant\s*hors\s*taxes\s*[:\-]?\s*([0-9\s.,]+)/i,
    /total\s*ht\s*[:\-]?\s*([0-9\s.,]+)/i
  ], text, '0'));

  const tva = parseNumber(find([
    /tva\s*[:\-]?\s*([0-9\s.,]+)/i,
    /montant\s*tva\s*[:\-]?\s*([0-9\s.,]+)/i
  ], text, '0'));

  const montant_ttc = parseNumber(find([
    /montant\s*toutes\s*taxes\s*comprises\s*[:\-]?\s*([0-9\s.,]+)/i,
    /total\s*ttc\s*[:\-]?\s*([0-9\s.,]+)/i
  ], text, '0'));

  const restant_du = parseNumber(find([
    /restant\s*du\s*[:\-]?\s*([0-9\s.,]+)/i,
    /solde\s*[:\-]?\s*([0-9\s.,]+)/i
  ], text, '0'));

  const articles = parseArticles(lines);

  return {
    societe_emettrice: societe_emettrice || null,
    client: client || null,
    numero_facture: numero_facture || null,
    date_emission: date_emission || null,
    date_echeance: null,
    adresse_emetteur: null,
    adresse_client: adresse_client || null,
    ifu: ifu || null,
    rccm: rccm || null,
    articles,
    montant_ht,
    remise_globale: null,
    taux_tva: taux_tva || null,
    tva,
    montant_ttc,
    acompte: null,
    restant_du,
    devise: devise || null,
    mode_paiement: mode_paiement || null,
    notes: null,
    confiance: 0.85,
    _meta: {
      fichier: filename || null,
      modele: 'ocr-space-js-parser',
      pages: null,
      analyse_le: new Date().toISOString().replace('T', ' ').slice(0, 19),
      tokens_utilises: {
        input: null,
        output: null
      }
    }
  };
}
