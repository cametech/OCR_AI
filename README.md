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
2. Définissez la variable d'environnement `OCR_SPACE_API_KEY` dans le tableau Vercel.
   - Si vous ne fournissez pas de clé, la clé de démonstration `helloworld` est utilisée avec des limites.
3. Déployez sur Vercel.

## API OCR externe

L'application utilise `OCR.space` pour la reconnaissance de texte (OCR). Le résultat est ensuite converti en JSON de facture avec un parser JavaScript.

## Notes

- Cette version fonctionne mieux avec des factures au format PDF ou image contenant du texte imprimé.
- Pour de grandes factures, vérifiez les limites du service `OCR.space` et la taille du fichier.
