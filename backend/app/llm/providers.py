"""Free LLM provider registry.

Pattern adapted from MoneyPrinterTurbo's LLMProviderSpec (MIT, see NOTICE),
trimmed to providers with a usable free tier and given native Zhipu/SiliconFlow entries.
"""

from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    label: str
    adapter: str  # "openai" (OpenAI-compatible) | "gemini"
    base_url: str | None
    key_attr: str  # Settings attribute holding the API key
    model_attr: str  # Settings attribute holding the model name
    signup_url: str
    supports_json_mode: bool = True


PROVIDERS: dict[str, ProviderSpec] = {
    p.name: p
    for p in [
        ProviderSpec(
            name="zhipu",
            label="Z.ai (Zhipu GLM-Flash, free)",
            adapter="openai",
            base_url="https://api.z.ai/api/paas/v4",
            key_attr="zhipu_api_key",
            model_attr="zhipu_model",
            signup_url="https://z.ai/manage-apikey/apikey-list",
        ),
        ProviderSpec(
            name="siliconflow",
            label="SiliconFlow (free Qwen)",
            adapter="openai",
            base_url="https://api.siliconflow.cn/v1",
            key_attr="siliconflow_api_key",
            model_attr="siliconflow_model",
            signup_url="https://cloud.siliconflow.cn/account/ak",
        ),
        ProviderSpec(
            name="groq",
            label="Groq (free tier)",
            adapter="openai",
            base_url="https://api.groq.com/openai/v1",
            key_attr="groq_api_key",
            model_attr="groq_model",
            signup_url="https://console.groq.com/keys",
        ),
        ProviderSpec(
            name="openrouter",
            label="OpenRouter (:free models)",
            adapter="openai",
            base_url="https://openrouter.ai/api/v1",
            key_attr="openrouter_api_key",
            model_attr="openrouter_model",
            signup_url="https://openrouter.ai/keys",
            supports_json_mode=False,
        ),
        ProviderSpec(
            name="gemini",
            label="Google Gemini (free tier)",
            adapter="gemini",
            base_url=None,
            key_attr="gemini_api_key",
            model_attr="gemini_model",
            signup_url="https://aistudio.google.com/apikey",
        ),
    ]
}


def configured_chain(settings: Settings) -> list[ProviderSpec]:
    """Providers in LLM_ORDER that have an API key set."""
    chain = []
    for name in (n.strip() for n in settings.llm_order.split(",")):
        spec = PROVIDERS.get(name)
        if spec and getattr(settings, spec.key_attr):
            chain.append(spec)
    return chain
