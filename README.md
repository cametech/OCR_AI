# OCR_AI

Ce projet contient une application Next.js pour tester l'OCR des factures via Vercel.

## Installation locale

```bash
npm install
npm run dev
```

## Utilisation

- Ouvrez `http://localhost:3000`
- Chargez un fichier PDF ou une image
- Lancez l'analyse
- Téléchargez le JSON de sortie

## Déploiement sur Vercel

1. Connectez votre dépôt GitHub à Vercel.
2. Dans Vercel, créez un projet à partir du dépôt `cametech/OCR_AI`.
3. Ajoutez la variable d'environnement `OCR_SPACE_API_KEY` dans le tableau Vercel.
   - Si vous ne fournissez pas de clé, la clé de démonstration `helloworld` est utilisée avec des limites.
4. Déployez le projet.

> Le site web déployé est l’application Next.js contenue dans ce dépôt.
### Variables d’environnement

Pour le développement local, créez un fichier `.env.local` à la racine du projet avec :

```env
OCR_SPACE_API_KEY=eb7e9706a688957
```

Ne commitez pas ce fichier : il est automatiquement ignoré par Git.
## Utilisation du GUI Python local

Le fichier `ai_agent_gui.py` est une application de bureau Python pour Windows, macOS et Linux qui s’exécute localement.

Installation des dépendances Python :

```bash
pip install -r requirements.txt
```

Puis lancez :

```bash
python ai_agent_gui.py
```

## API OCR externe

L'application utilise `OCR.space` pour la reconnaissance de texte (OCR). Le résultat est ensuite converti en JSON de facture avec un parser JavaScript.

## Notes

- Cette version fonctionne mieux avec des factures au format PDF ou image contenant du texte imprimé.
- Pour de grandes factures, vérifiez les limites du service `OCR.space` et la taille du fichier.
