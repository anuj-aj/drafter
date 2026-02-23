"""LLM factory for selecting between different language model providers."""

from app.config import settings


def get_llm_model():
    """Factory function to get the appropriate LLM based on settings.
    
    Returns:
        ChatOpenAI or ChatOllama instance based on LLM_PROVIDER setting.
        
    Raises:
        ValueError: If LLM_PROVIDER is not recognized.
    """
    if settings.llm_provider == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(model="gpt-4o", api_key=settings.openai_api_key)
    elif settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")
