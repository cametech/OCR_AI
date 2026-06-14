import { parseInvoiceText } from '../../lib/parser';

export const config = {
  api: {
    bodyParser: {
      sizeLimit: '20mb'
    }
  }
};

const OCR_SPACE_URL = 'https://api.ocr.space/parse/image';
const OCR_SPACE_API_KEY = process.env.OCR_SPACE_API_KEY || 'helloworld';

async function sendToOcrSpace(name, mimeType, base64data) {
  const buffer = Buffer.from(base64data, 'base64');
  const formData = new FormData();
  formData.append('apikey', OCR_SPACE_API_KEY);
  formData.append('language', 'fre');
  formData.append('isOverlayRequired', 'false');
  formData.append('file', buffer, name);

  const response = await fetch(OCR_SPACE_URL, {
    method: 'POST',
    body: formData
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(`OCR.space a renvoyé ${response.status}: ${text}`);
  }

  const json = await response.json();
  if (!json.ParsedResults || !json.ParsedResults.length) {
    throw new Error('OCR.space n’a pas retourné de résultat valide.');
  }

  return json.ParsedResults[0].ParsedText || '';
}

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    res.setHeader('Allow', 'POST');
    return res.status(405).json({ error: 'Méthode non autorisée' });
  }

  const body = req.body;
  const { files, merge } = body || {};
  if (!files || !Array.isArray(files) || !files.length) {
    return res.status(400).json({ error: 'Aucun fichier fourni.' });
  }

  try {
    const results = await Promise.all(
      files.map(async (file) => {
        const text = await sendToOcrSpace(file.name, file.type, file.base64);
        const parsed = parseInvoiceText(text, file.name);
        return {
          file: file.name,
          text,
          parsed
        };
      })
    );

    if (merge) {
      const merged = results.map((item) => item.parsed);
      return res.status(200).json({ merged, details: results });
    }

    return res.status(200).json({ results });
  } catch (error) {
    return res.status(500).json({ error: error.message || 'Erreur OCR interne.' });
  }
}
