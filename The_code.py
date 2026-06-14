import os
from openai import OpenAI

# Modèles disponibles sur ton compte — du plus puissant au plus rapide
MODELES = {
    "1": ("nvidia/llama-3.3-nemotron-super-49b-v1.5", "Nemotron Super 49B (raisonnement avancé)"),
    "2": ("meta/llama-3.3-70b-instruct",              "Llama 3.3 70B (rapide & puissant)"),
    "3": ("mistralai/mistral-large-3-675b-instruct-2512", "Mistral Large 3 675B (très grand)"),
    "4": ("qwen/qwen3.5-397b-a17b",                   "Qwen 3.5 397B (ultra large)"),
    "5": ("deepseek-ai/deepseek-v4-pro",              "DeepSeek V4 Pro"),
}

class NemotronAgent:
    def __init__(self, api_key=None):
        self.client = OpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=api_key or "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"
        )
        self.model = MODELES["1"][0]  # Par défaut : Nemotron Super 49B

    def choisir_modele(self):
        print("\nChoisissez un modèle :")
        for k, (_, nom) in MODELES.items():
            print(f"  {k}. {nom}")
        choix = input("Votre choix (Enter pour garder l'actuel) : ").strip()
        if choix in MODELES:
            self.model = MODELES[choix][0]
            print(f"✅ Modèle sélectionné : {MODELES[choix][1]}")

    def poser_question(self, prompt):
        self._reponse_started = False
        print(f"\n[Modèle : {self.model}]")
        print("Connexion à l'API NVIDIA...\n")

        try:
            completion = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Tu es un expert et en maitrise un rayon dans les domaines informatiques (IA, programmation, systèmes, réseaux, cybersecurité, développement web/mobile, design, etc.) et ton domaine de predilection est la cybersecurité, tu en es un expert incontesté. "
                            "Tu es un assistant d'élite, brillant et bienveillant. "
                            "Tu réponds en français de façon élégante, structurée, approfondie et majestueuse. "
                            "Tu peux repondre en anglais uniquement si je le demande ou si la question est posée en anglais. "
                            "Tes réponses sont complètes, riches et bien organisées et tu montres la logique de tes raisonnements."
                        )
                    },
                    {"role": "user", "content": prompt}
                ],
                temperature=0.6,
                top_p=0.95,
                max_tokens=4096,
                stream=True
            )

            print("--- ✨ Réponse ---\n")
            for chunk in completion:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    if not hasattr(self, "_thinking_started"):
                        print("--- 🧠 Raisonnement ---")
                        self._thinking_started = True
                    print(delta.reasoning_content, end="", flush=True)
                elif delta.content:
                    if not self._reponse_started:
                        if hasattr(self, "_thinking_started"):
                            print("\n\n--- ✨ Réponse Finale ---\n")
                        self._reponse_started = True
                    print(delta.content, end="", flush=True)
            print("\n")

        except Exception as e:
            print(f"\n❌ Erreur ({self.model}) : {type(e).__name__}: {e}")
            print("💡 Tapez 'modele' pour changer de modèle.\n")


if __name__ == "__main__":
    agent = NemotronAgent()

    print("=" * 60)
    print("   Agent NVIDIA — Intelligence Artificielle Élite")
    print("=" * 60)
    print(f"Modèle actuel : {agent.model}")
    print("Commandes : 'modele' pour changer | 'quitter' pour sortir")

    while True:
        user_prompt = input("\nVotre question : ").strip()
        if not user_prompt:
            continue
        if user_prompt.lower() in ("quitter", "exit", "quit"):
            print("Au revoir !")
            break
        if user_prompt.lower() == "modele":
            agent.choisir_modele()
            continue
        agent.poser_question(user_prompt)