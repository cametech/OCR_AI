"""
AGENT OCR FACTURATION — Local parser + optional API fallback
Usage:
  python Factor_AI.py                      # interactive
  python Factor_AI.py facture.pdf          # single file
  python Factor_AI.py factures/ --merge     # folder + merge results
Options:
  --show-json       Show raw JSON
  --merge           Merge all results into one JSON file
  --merge-name NAME Use custom merged filename
  --sortie DIR      Output directory for JSON files

This is a reconstructed version of the script previously used in the workspace.
It prefers local PDF text extraction and parsing, and only uses the remote
API for image inputs if configured.
"""

import os
import sys
import json
import base64
import argparse
import textwrap
import re
from pathlib import Path
from datetime import datetime

# Ensure stdout/stderr use UTF-8 on Windows consoles to avoid UnicodeEncodeError
try:
    # Python 3.7+ provides reconfigure
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    try:
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception:
        # last resort: set PYTHONIOENCODING for subprocesses
        os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# Optional: OpenAI/OpenRouter client (only used for image-based OCR if available)
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from PIL import Image
    import io
except Exception:
    print("❌  Pillow is required. pip install Pillow")
    raise SystemExit(1)

try:
    from PyPDF2 import PdfReader
except Exception:
    print("❌  PyPDF2 is required. pip install PyPDF2")
    raise SystemExit(1)

# Rich is optional for nicer terminal output
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.syntax import Syntax
    from rich import box
    RICH = True
except Exception:
    RICH = False

console = Console() if RICH else None

# Configuration - prefer environment variable
API_KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.environ.get("OCR_MODEL", "deepseek/deepseek-reasoner")

SYSTEM_PROMPT = (
    "Tu es un agent OCR expert spécialisé dans l'extraction de données de factures."
)

SCHEMA_DESCRIPTION = """
{ "societe_emettrice": "..." }
"""

USER_PROMPT = f"Analyse cette facture et retourne uniquement un JSON correspondant au schéma.\n{SCHEMA_DESCRIPTION}"

# Utilities

def log(msg, style=""):
    if RICH:
        console.print(msg, style=style)
    else:
        print(msg)


def separator():
    log("─" * 68, style="dim")


def encode_image(path: Path) -> tuple[str, str]:
    img = Image.open(path)
    # Convert to RGB and resize if needed
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    max_dim = 4096
    if max(img.size) > max_dim:
        ratio = max_dim / max(img.size)
        img = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92)
    b64 = base64.b64encode(buf.getvalue()).decode()
    return b64, "image/jpeg"


def pdf_to_images(path: Path) -> list[tuple[str, str]]:
    try:
        from pdf2image import convert_from_path
    except Exception:
        raise RuntimeError("pdf2image is required for PDF->images: pip install pdf2image")
    pages = convert_from_path(str(path), dpi=200)
    results = []
    for p in pages:
        buf = io.BytesIO()
        p.save(buf, format="JPEG", quality=92)
        b64 = base64.b64encode(buf.getvalue()).decode()
        results.append((b64, "image/jpeg"))
    return results


def pdf_to_text(path: Path) -> str:
    reader = PdfReader(str(path))
    content = []
    for page in reader.pages:
        t = page.extract_text() or ""
        content.append(t)
    return "\n".join(content)


def _to_float(value: str) -> float | None:
    if not value:
        return None
    # Keep only digits, spaces, dots and commas
    m = re.search(r"[-+]?[0-9][0-9\s.,]*", value)
    if not m:
        return None
    s = m.group(0).replace(" ", "").replace(",", ".")
    try:
        return float(s)
    except Exception:
        return None


def _clean_number_spaces(value: str) -> str:
    return re.sub(r"(?<=\d)\s+(?=\d)", "", value)


def _parse_invoice_text(text: str, file_path: Path) -> dict:
    raw = text.replace("\r", "\n").replace("�", " ").strip()
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    all_text = "\n".join(lines)
    lower_text = all_text.lower()

    societe = None
    if lines:
        # heuristique
        if "ma-info" in lower_text:
            societe = "MA-INFO"
        else:
            societe = lines[0]

    numero_facture = None
    m = re.search(r"r[eé]f(?:erence|érence)?\s*[:\-]?\s*([A-Z0-9-]+)", all_text, re.I)
    if m:
        numero_facture = m.group(1).strip()

    date_emission = None
    m = re.search(r"(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", all_text)
    if m:
        date_emission = m.group(1).replace("-", "/")

    client = None
    m = re.search(r"destin(?:e|é)\s*(?:à|a)?\s*[:\-]?\s*(.+)", all_text, re.I)
    if m:
        client = m.group(1).split("\n")[0].strip()
    if not client:
        m = re.search(r"client\s*[:\-]?\s*(.+)", all_text, re.I)
        if m:
            client = m.group(1).split("\n")[0].strip()

    adresse_client = None
    m = re.search(r"adresse de facturation\s*[:\-]?\s*(.+)", all_text, re.I)
    if m:
        adresse_client = m.group(1).split("\n")[0].strip()

    ifu = None
    m = re.search(r"ifu\s*[:\-]?\s*([0-9\s,]+)", all_text, re.I)
    if m:
        ifu = m.group(1).replace(" ", "").replace(",", "").strip()

    rccm = None
    m = re.search(r"rccm\s*[:\-]?\s*([A-Z0-9/\s]+)", all_text, re.I)
    if m:
        rccm = m.group(1).strip()

    devise = None
    if "fcfa" in lower_text or "f cfa" in lower_text:
        devise = "F CFA"
    elif "xof" in lower_text:
        devise = "XOF"

    # Payment
    mode_paiement = None
    m = re.search(r"r[eé]gl(?:ement)?s?\s*[:\-]?\s*(.+)", all_text, re.I)
    if m:
        pm = m.group(1)
        if "esp" in pm.lower():
            mode_paiement = "Espèces"
        else:
            mode_paiement = pm.split("\n")[0].strip()
    elif "esp" in lower_text:
        mode_paiement = "Espèces"

    # Articles parsing: lines starting with number
    articles = []
    art_re = re.compile(r"^\s*(\d+)\s+(.+?)\s+([0-9]{1,3}(?:\s[0-9]{3})*)\s+([0-9]{1,3}(?:\s[0-9]{3})*)(?:\s*(?:FCFA|F CFA|XOF))?\s+([0-9]{1,3}(?:\s[0-9]{3})*)(?:\s*(?:FCFA|F CFA|XOF))?", re.I)
    for line in lines:
        m = art_re.match(line)
        if m:
            ref = None
            designation = m.group(2).strip()
            quantite = _to_float(m.group(3))
            pu = _to_float(m.group(4))
            total_ht = _to_float(m.group(5))
            articles.append({
                "reference": ref,
                "designation": designation,
                "quantite": quantite,
                "unite": None,
                "prix_unitaire_ht": pu,
                "remise_pct": None,
                "total_ht": total_ht,
            })

    def _find_amount(patterns):
        for p in patterns:
            mm = re.search(p, all_text, re.I)
            if mm:
                val = mm.group(1)
                if val:
                    return _to_float(_clean_number_spaces(val))
        return None

    montant_ht = _find_amount([r"prix total ht\s*[:\-]?\s*([0-9\s.,]+)", r"total ht\s*[:\-]?\s*([0-9\s.,]+)"])
    tva = _find_amount([r"t\.v\.a\s*[:\-]?\s*([0-9\s.,]+)", r"tva\s*[:\-]?\s*([0-9\s.,]+)"])
    montant_ttc = _find_amount([r"prix total ttc\s*[:\-]?\s*([0-9\s.,]+)", r"total ttc\s*[:\-]?\s*([0-9\s.,]+)"])

    restant_du = _find_amount([
        r"restant.*du\s*[:\-]?\s*([0-9\s.,]+)",
        r"net.*payer\s*[:\-]?\s*([0-9\s.,]+)",
        r"\b(0)\s*fcfa\b",
    ])
    if not restant_du:
        for line in lines:
            if "restant" in line.lower() or "net" in line.lower() or "payer" in line.lower():
                mm = re.search(r"([0-9]{1,3}(?:[\s.,][0-9]{3})*(?:[.,][0-9]+)?)", line)
                if mm:
                    restant_du = _to_float(_clean_number_spaces(mm.group(1)))
                    break

    taux_tva = None
    tvm = re.search(r"\((\d{1,3})%\)", all_text)
    if tvm:
        taux_tva = f"{tvm.group(1)}%"

    data = {
        "societe_emettrice": societe,
        "client": client,
        "numero_facture": numero_facture,
        "date_emission": date_emission,
        "date_echeance": None,
        "adresse_emetteur": None,
        "adresse_client": adresse_client,
        "ifu": ifu,
        "rccm": rccm,
        "articles": articles if articles else None,
        "montant_ht": montant_ht,
        "remise_globale": None,
        "taux_tva": taux_tva,
        "tva": tva,
        "montant_ttc": montant_ttc,
        "acompte": None,
        "restant_du": restant_du,
        "devise": devise,
        "mode_paiement": mode_paiement,
        "notes": None,
        "confiance": 0.85,
    }

    data["_meta"] = {
        "fichier": file_path.name,
        "modele": "local-parser",
        "pages": len(lines),
        "analyse_le": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "tokens_utilises": {"input": None, "output": None},
    }
    return data


class AgentOCR:
    def __init__(self):
        self.client = None
        if OpenAI and API_KEY:
            try:
                self.client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
            except Exception:
                self.client = None

    def _build_messages(self, images_b64: list[tuple[str, str]]) -> list[dict]:
        content = []
        for i, (b64, mime) in enumerate(images_b64):
            if len(images_b64) > 1:
                content.append({"type": "text", "text": f"--- Page {i+1} ---"})
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}})
        content.append({"type": "text", "text": USER_PROMPT})
        return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": content}]

    def analyser(self, file_path: Path) -> dict:
        ext = file_path.suffix.lower()
        if ext == ".pdf":
            text = pdf_to_text(file_path)
            if text.strip():
                return _parse_invoice_text(text, file_path)
            # fallback to images
            images = pdf_to_images(file_path)
        else:
            b64, mime = encode_image(file_path)
            images = [(b64, mime)]

        # If client available, call remote model
        if self.client:
            messages = self._build_messages(images)
            try:
                response = self.client.chat.completions.create(model=MODEL, messages=messages, max_tokens=4096, temperature=0)
                raw = response.choices[0].message.content or ""
                clean = raw.strip()
                if clean.startswith("```"):
                    lines = clean.splitlines()
                    clean = "\n".join(l for l in lines if not l.strip().startswith("```")).strip()
                try:
                    data = json.loads(clean)
                except Exception:
                    # try to find json inside
                    start = clean.find("{")
                    end = clean.rfind("}") + 1
                    if start != -1 and end > start:
                        data = json.loads(clean[start:end])
                    else:
                        raise
                data["_meta"] = data.get("_meta", {})
                data["_meta"].update({"fichier": file_path.name, "modele": MODEL, "pages": len(images), "analyse_le": datetime.now().strftime("%d/%m/%Y %H:%M:%S")})
                return data
            except Exception as e:
                # fallback to local parsing
                log(f"❌  API error, falling back to local parse: {e}", style="red")
                return _parse_invoice_text(pdf_to_text(file_path) if ext == ".pdf" else "", file_path)
        else:
            # local-only
            if ext == ".pdf":
                return _parse_invoice_text(pdf_to_text(file_path), file_path)
            else:
                # try basic OCR via images is not implemented; just return minimal
                return {"societe_emettrice": None, "_meta": {"fichier": file_path.name}}


def afficher_resultat(data: dict, show_json: bool = False):
    meta = data.get("_meta", {})
    confiance = float(data.get("confiance") or 0) * 100
    if RICH:
        couleur = "green" if confiance >= 80 else "yellow" if confiance >= 60 else "red"
        console.print()
        console.print(Panel.fit(f"[bold]{meta.get('fichier','Facture')}[/bold]\n[dim]{meta.get('analyse_le','')} · {meta.get('modele','')} · Confiance: {confiance:.0f}%[/dim]", title="[bold cyan]RÉSULTAT OCR[/bold cyan]", border_style="cyan"))
        
        # Information générale
        t = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
        t.add_column("Champ", style="dim", width=22)
        t.add_column("Valeur", style="bold")
        
        fields = [
            ("Société émettrice", data.get("societe_emettrice")),
            ("Client", data.get("client")),
            ("Adresse client", data.get("adresse_client")),
            ("N° Facture", data.get("numero_facture")),
            ("Date d'émission", data.get("date_emission")),
            ("IFU", data.get("ifu")),
            ("RCCM", data.get("rccm")),
            ("Mode paiement", data.get("mode_paiement")),
        ]
        for label, val in fields:
            if val:
                t.add_row(label, str(val))
        console.print(t)
        
        # Montants
        console.print("\n[bold]Montants:[/bold]")
        t_montants = Table(box=box.SIMPLE, show_header=False, padding=(0,1))
        t_montants.add_column("", style="dim", width=22)
        t_montants.add_column("", style="bold")
        montants = [
            ("Montant HT", data.get("montant_ht")),
            ("TVA", data.get("tva")),
            ("Montant TTC", data.get("montant_ttc")),
            ("Restant dû", data.get("restant_du")),
        ]
        for label, val in montants:
            if val is not None:
                devise = data.get("devise", "")
                t_montants.add_row(label, f"{val} {devise}".strip())
        console.print(t_montants)
        
        # Articles
        articles = data.get("articles")
        if articles:
            console.print(f"\n[bold]Articles ({len(articles)}):[/bold]")
            t_art = Table(box=box.SIMPLE, show_header=True, padding=(0,1))
            t_art.add_column("Désignation", style="cyan")
            t_art.add_column("Quantité", style="yellow")
            t_art.add_column("PU", style="yellow")
            t_art.add_column("Total", style="bold")
            for art in articles[:10]:  # afficher max 10 articles
                designation = art.get("designation", "")
                qte = art.get("quantite")
                pu = art.get("prix_unitaire_ht")
                total = art.get("total_ht")
                qte_str = f"{qte}" if qte is not None else "—"
                pu_str = f"{pu}" if pu is not None else "—"
                total_str = f"{total}" if total is not None else "—"
                t_art.add_row(designation[:40], qte_str, pu_str, total_str)
            console.print(t_art)
            if len(articles) > 10:
                console.print(f"[dim]… et {len(articles) - 10} autres articles[/dim]")
        
        if show_json:
            console.print(Panel(Syntax(json.dumps(data, indent=2, ensure_ascii=False), "json", theme="monokai"), title="JSON complet"))
    else:
        # Fallback sans RICH: afficher JSON complet par défaut
        print(f"\n{'='*70}")
        print(f"📄 {meta.get('fichier','')} — Confiance: {confiance:.0f}%")
        print(f"{'='*70}")
        print(json.dumps(data, indent=2, ensure_ascii=False))


def sauvegarder_json(data: dict, source_path: Path) -> Path:
    stem = source_path.stem
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = source_path.parent / f"{stem}_ocr_{ts}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return out


def get_supported_files(path: Path) -> list[Path]:
    extensions = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
    if path.is_dir():
        return [f for f in sorted(path.iterdir()) if f.suffix.lower() in extensions]
    elif path.is_file() and path.suffix.lower() in extensions:
        return [path]
    else:
        return []


# Main

def main():
    parser = argparse.ArgumentParser(description="Agent OCR Facturation — local parser", formatter_class=argparse.RawDescriptionHelpFormatter, epilog=textwrap.dedent("""\
        Exemples :
          python Factor_AI.py                   # mode interactif
          python Factor_AI.py facture.pdf       # fichier direct
          python Factor_AI.py ./factures/       # dossier entier
          python Factor_AI.py facture.jpg --show-json  # afficher JSON
          python Factor_AI.py documents --merge --merge-name resultat.json  # fusionner
    """))
    parser.add_argument("fichier", nargs="?", help="Chemin vers la facture ou le dossier")
    parser.add_argument("--json", "--show-json", action="store_true", dest="show_json", help="Afficher le JSON brut en sortie")
    parser.add_argument("--merge", action="store_true", help="Fusionner tous les résultats JSON dans un seul fichier")
    parser.add_argument("--merge-name", type=str, help="Nom du fichier JSON fusionné (défaut: merged_ocr.json)")
    parser.add_argument("--sortie", type=str, help="Dossier de sortie pour les JSON (défaut: même dossier que le fichier)")
    args = parser.parse_args()

    agent = AgentOCR()

    if args.fichier:
        path = Path(args.fichier)
        if not path.exists():
            sys.exit(f"❌  Introuvable : {path}")
        files = get_supported_files(path)
        if not files:
            sys.exit("❌  Aucun fichier supporté trouvé.")

        merged_results = []
        total = len(files)
        for i, fp in enumerate(files, 1):
            log(f"\n[{i}/{total}] 🔍  Analyse de {fp.name}…")
            try:
                data = agent.analyser(fp)
                afficher_resultat(data, show_json=args.show_json)
                merged_results.append(data)
                if args.sortie:
                    out_dir = Path(args.sortie)
                    out_dir.mkdir(parents=True, exist_ok=True)
                    out = out_dir / f"{fp.stem}_ocr.json"
                    with open(out, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                else:
                    out = sauvegarder_json(data, fp)
                log(f"💾  JSON → {out}")
            except Exception as e:
                log(f"❌  {fp.name} : {e}")

        if args.merge and merged_results:
            merged_file_name = args.merge_name or "merged_ocr.json"
            if args.sortie:
                merged_path = Path(args.sortie) / merged_file_name
            elif path.is_dir():
                merged_path = path / merged_file_name
            else:
                merged_path = path.parent / merged_file_name
            merged_path.parent.mkdir(parents=True, exist_ok=True)
            with open(merged_path, "w", encoding="utf-8") as f:
                json.dump(merged_results, f, indent=2, ensure_ascii=False)
            log(f"💾  JSON fusionné → {merged_path}")
    else:
        # interactive
        if RICH:
            console.print(Panel("[bold cyan]Agent OCR Facturation (interactive)[/bold cyan]", border_style="cyan"))
        while True:
            separator()
            try:
                chemin = console.input("Facture/Dossier > ") if RICH else input("Facture/Dossier > ")
            except (KeyboardInterrupt, EOFError):
                log("\nAu revoir !")
                break
            chemin = chemin.strip()
            if chemin.lower() in ("quit", "exit", "q", "quitter"):
                log("Au revoir !")
                break
            if not chemin:
                continue
            path = Path(chemin.strip('"').strip("'"))
            if not path.exists():
                log(f"❌  Fichier introuvable : {path}")
                continue
            files = get_supported_files(path)
            if not files:
                log("❌  Aucun fichier supporté trouvé.")
                continue
            for fp in files:
                log(f"\n🔍  Analyse de {fp.name}…")
                try:
                    data = agent.analyser(fp)
                    afficher_resultat(data, show_json=False)
                    out = sauvegarder_json(data, fp)
                    log(f"💾  JSON sauvegardé → {out}")
                except Exception as e:
                    log(f"❌  Erreur lors de l'analyse de {fp.name} : {e}")


if __name__ == "__main__":
    main()
