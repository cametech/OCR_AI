from openai import OpenAI

client = OpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key="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"
)

print("Modèles disponibles sur votre compte NVIDIA :\n")
models = client.models.list()
for m in models.data:
    print(" -", m.id)