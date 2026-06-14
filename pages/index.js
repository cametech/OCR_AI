import { useState } from 'react';

const ACCEPTED_TYPES = [
  '.pdf',
  '.png',
  '.jpg',
  '.jpeg',
  '.tif',
  '.tiff'
];

function bytesToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result.split(',')[1]);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

function downloadText(filename, text) {
  const blob = new Blob([text], { type: 'application/json;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  link.click();
  URL.revokeObjectURL(link.href);
}

export default function Home() {
  const [files, setFiles] = useState([]);
  const [merge, setMerge] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleFiles = async (event) => {
    const chosen = Array.from(event.target.files || []);
    setFiles(chosen.filter((file) => ACCEPTED_TYPES.includes(file.name.slice(file.name.lastIndexOf('.')).toLowerCase())));
    setResult(null);
    setError(null);
  };

  const handleSubmit = async () => {
    if (!files.length) {
      setError('Veuillez sélectionner au moins un PDF ou une image.');
      return;
    }
    setError(null);
    setRunning(true);
    setResult(null);

    try {
      const payload = await Promise.all(
        files.map(async (file) => ({
          name: file.name,
          type: file.type || 'application/octet-stream',
          base64: await bytesToBase64(file)
        }))
      );

      const response = await fetch('/api/ocr', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ files: payload, merge })
      });

      if (!response.ok) {
        const body = await response.text();
        throw new Error(`Échec du serveur: ${response.status} ${body}`);
      }

      const data = await response.json();
      setResult(data);
    } catch (err) {
      setError(err.message || 'Erreur inconnue');
    } finally {
      setRunning(false);
    }
  };

  const downloadResult = () => {
    if (!result) return;
    const filename = merge ? 'result-merged.json' : 'result-individual.json';
    downloadText(filename, JSON.stringify(result, null, 2));
  };

  return (
    <main className="container">
      <div className="card">
        <h1>CamAI OCR pour factures</h1>
        <p>Importez un PDF ou une image, puis lancez l'analyse. Le texte OCR est transformé en JSON de facture.</p>

        <label className="file-label">
          Sélectionner des fichiers
          <input type="file" accept={ACCEPTED_TYPES.join(',')} multiple onChange={handleFiles} />
        </label>

        <div className="options">
          <label>
            <input type="checkbox" checked={merge} onChange={() => setMerge(!merge)} />
            Fusionner tous les documents dans un seul JSON
          </label>
        </div>

        <button className="primary" onClick={handleSubmit} disabled={running}>
          {running ? 'Traitement en cours…' : 'Lancer l’analyse'}
        </button>

        {error && <div className="error">{error}</div>}
        {files.length > 0 && (
          <div className="file-list">
            <strong>Fichiers sélectionnés :</strong>
            <ul>{files.map((file) => <li key={file.name}>{file.name}</li>)}</ul>
          </div>
        )}

        {result && (
          <div className="result">
            <div className="result-header">
              <strong>Résultat JSON</strong>
              <button className="secondary" onClick={downloadResult}>Télécharger</button>
            </div>
            <pre>{JSON.stringify(result, null, 2)}</pre>
          </div>
        )}
      </div>

      <style jsx>{`
        .container {
          padding: 3rem;
          max-width: 900px;
          margin: 0 auto;
          font-family: system-ui, sans-serif;
        }
        .card {
          background: #fff;
          border-radius: 18px;
          padding: 2rem;
          box-shadow: 0 20px 80px rgba(0,0,0,0.08);
        }
        h1 {
          margin: 0 0 1rem;
          font-size: 2rem;
        }
        .file-label {
          display: inline-flex;
          flex-direction: column;
          gap: 0.75rem;
          margin-bottom: 1rem;
          font-weight: 600;
        }
        input[type=file] {
          cursor: pointer;
        }
        .options {
          margin: 1rem 0;
        }
        .primary {
          background: #0070f3;
          color: white;
          border: none;
          border-radius: 10px;
          padding: 0.9rem 1.4rem;
          font-size: 1rem;
          cursor: pointer;
        }
        .secondary {
          background: #eaeaea;
          border: none;
          border-radius: 10px;
          padding: 0.7rem 1rem;
          cursor: pointer;
        }
        .error {
          margin-top: 1rem;
          color: #b00020;
          font-weight: 600;
        }
        .file-list {
          margin-top: 1rem;
        }
        .result {
          margin-top: 1.5rem;
          background: #f6f8ff;
          border-radius: 16px;
          padding: 1rem;
        }
        pre {
          overflow-x: auto;
          margin: 0;
          white-space: pre-wrap;
          word-break: break-word;
        }
        .result-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 1rem;
          margin-bottom: 0.75rem;
        }
      `}</style>
    </main>
  );
}
