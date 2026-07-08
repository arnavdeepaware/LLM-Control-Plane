from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderTarget:
    provider: str
    model: str

    @classmethod
    def from_string(cls, value: str) -> "ProviderTarget":
        parts = value.split(":", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid provider target format: '{value}' (expected 'provider:model')")
        return cls.from_parts(parts[0], parts[1])

    @classmethod
    def from_parts(cls, provider: str, model: str) -> "ProviderTarget":
        if not provider or not provider.strip():
            raise ValueError("Provider target provider must not be empty")
        if not model or not model.strip():
            raise ValueError("Provider target model must not be empty")
        if provider != provider.strip():
            raise ValueError(f"Provider target provider must not contain surrounding whitespace: '{provider}'")
        if model != model.strip():
            raise ValueError(f"Provider target model must not contain surrounding whitespace: '{model}'")
        return cls(provider=provider, model=model)

    def to_string(self) -> str:
        return f"{self.provider}:{self.model}"
