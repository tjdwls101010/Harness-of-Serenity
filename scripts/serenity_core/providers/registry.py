"""Provider-neutral dispatch for schema-valid adaptive evidence requests."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from serenity_core.providers.base import ProviderEnvelope
from serenity_core.providers.issuer_ir import VerifiedIssuerOrigin
from serenity_core.research import ResearchArtifactValidationError, load_evidence_catalog
from serenity_core.schema import SchemaViolation, validate_document


EVIDENCE_REQUEST_SCHEMA_ID = "urn:serenity:schema:evidence-request:1"
PROVIDER_ENVELOPE_SCHEMA_ID = "urn:serenity:schema:provider-envelope:1"
REGISTRY_PROVIDER_VERSION = "registry/1"
_SNAPSHOT_CAPABILITIES = frozenset(
    {
        "yfinance.market-data",
        "yfinance.financial-statements",
        "yfinance.valuation",
        "sec.identity",
        "openfigi.security-identity",
        "ibd-rs-rating.relative-strength-observation",
    }
)
_SECRET_PARAMETER_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "password",
        "secret",
        "token",
        "userid",
        "registrationkey",
        "registration_key",
        "bls_registration_key",
        "eia_api_key",
        "bea_api_key",
        "sam_api_key",
        "uspto_api_key",
    }
)
_PUBLIC_CREDENTIAL_CONFIG = {
    "eia": ("eia_api_key", ("eia_api_key", "api_key")),
    "bls": ("bls_registration_key", ("bls_registration_key", "registrationkey", "registration_key")),
    "bea": ("bea_api_key", ("bea_api_key", "api_key")),
    "sam": ("sam_api_key", ("sam_api_key", "api_key")),
    "uspto": ("uspto_api_key", ("uspto_api_key", "api_key")),
}

Clock = Callable[[], datetime | str]
ProviderFactory = Callable[..., Any]


class ProviderRegistryValidationError(ResearchArtifactValidationError):
    """Raised for an invalid dispatch document before a provider can run."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


class EvidenceProviderRegistry:
    """Collect provider envelopes through one capability-checked public seam.

    ``provider_factories`` are keyed by catalog ``provider_id`` and receive
    keyword-only ``provider_id``, ``config``, and ``clock`` values. Configuration
    is provider-scoped (for example ``{"alfred-fred": {"api_key": "..."}}``)
    and is never copied into registry-generated envelopes or exceptions.
    """

    def __init__(
        self,
        *,
        provider_factories: Mapping[str, ProviderFactory] | None = None,
        config: Mapping[str, Mapping[str, Any]] | None = None,
        clock: Clock = _utc_now,
        catalog: Mapping[str, Any] | None = None,
    ) -> None:
        catalog_document = dict(catalog) if catalog is not None else load_evidence_catalog()
        try:
            validate_document(catalog_document, "urn:serenity:schema:evidence-catalog:1")
        except SchemaViolation as exc:
            raise ProviderRegistryValidationError(f"evidence catalog is invalid: {exc}") from exc
        self._owners = self._capability_owners(catalog_document)
        self._provider_ids = {provider["provider_id"] for provider in catalog_document["providers"]}
        self._factories = dict(provider_factories or {})
        self._config = {provider_id: dict(values) for provider_id, values in (config or {}).items() if isinstance(values, Mapping)}
        self._clock = clock

    def collect(
        self,
        request_doc: Mapping[str, Any],
        *,
        issuer_origin_binding: VerifiedIssuerOrigin | None = None,
    ) -> list[ProviderEnvelope]:
        """Return at least one schema-valid envelope or raise a validation error.

        Validation happens before a factory is constructed, so a mismatched
        capability/provider policy cannot cause an external request.
        """

        request = self._validate_request(request_doc)
        capability_id = request["capability_id"]
        provider_id = self._owners[capability_id]
        policy = request["provider_policy"]
        cutoff = policy.get("historical_cutoff")
        if policy.get("allow_network", True) is False:
            return self._finalize([self._registry_envelope(provider_id, request, "not_requested", "network access is disabled by provider_policy")])
        if provider_id == "issuer-ir" and issuer_origin_binding is None:
            raise ProviderRegistryValidationError("issuer-ir.document requires a runtime-verified issuer origin binding")
        if capability_id in _SNAPSHOT_CAPABILITIES:
            return self._finalize(
                [self._registry_envelope(provider_id, request, "not_applicable", "baseline snapshot capability is owned by the snapshot service")]
            )
        try:
            envelopes = self._dispatch(
                provider_id,
                capability_id,
                request["provider_parameters"],
                cutoff,
                issuer_origin_binding=issuer_origin_binding,
            )
        except Exception as exc:  # Provider faults must remain typed evidence.
            envelopes = [
                self._registry_envelope(
                    provider_id,
                    request,
                    "unavailable",
                    f"provider adapter failed: {type(exc).__name__}",
                )
            ]
        envelopes = self._enforce_cutoff(envelopes, cutoff, provider_id, request)
        return self._finalize(envelopes, provider_id=provider_id, request=request)

    @staticmethod
    def _capability_owners(catalog: Mapping[str, Any]) -> dict[str, str]:
        owners: dict[str, str] = {}
        for provider in catalog["providers"]:
            provider_id = provider["provider_id"]
            for capability_id in provider["capabilities"]:
                if capability_id in owners:
                    raise ProviderRegistryValidationError(f"evidence catalog declares capability more than once: {capability_id}")
                owners[capability_id] = provider_id
        return owners

    def _validate_request(self, request_doc: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(request_doc, Mapping):
            raise ProviderRegistryValidationError("evidence request must be an object")
        try:
            request = json.loads(json.dumps(dict(request_doc), ensure_ascii=False))
        except (TypeError, ValueError) as exc:
            raise ProviderRegistryValidationError("evidence request must be JSON-compatible") from exc
        try:
            validate_document(request, EVIDENCE_REQUEST_SCHEMA_ID)
        except SchemaViolation as exc:
            raise ProviderRegistryValidationError(f"evidence request is invalid: {exc}") from exc
        capability_id = request["capability_id"]
        if capability_id not in self._owners:
            raise ProviderRegistryValidationError(f"capability_id is not declared by the evidence catalog: {capability_id}")
        provider_id = self._owners[capability_id]
        providers = request["provider_policy"]["providers"]
        unknown_providers = sorted(set(providers) - self._provider_ids)
        if unknown_providers:
            raise ProviderRegistryValidationError(f"provider_policy has unknown providers: {unknown_providers}")
        if provider_id not in providers:
            raise ProviderRegistryValidationError(f"provider_policy does not allow capability owner: {provider_id}")
        cutoff = request["provider_policy"].get("historical_cutoff")
        if cutoff is not None:
            try:
                _as_instant(cutoff)
            except (TypeError, ValueError) as exc:
                raise ProviderRegistryValidationError("historical_cutoff must be an ISO instant") from exc
        if provider_id == "alfred-fred" and request["provider_policy"].get("allow_network", True) is not False:
            series_id = request["provider_parameters"].get("series_id")
            if not isinstance(series_id, str) or not series_id:
                raise ProviderRegistryValidationError("alfred-fred requires provider_parameters.series_id")
            if cutoff is None:
                raise ProviderRegistryValidationError("alfred-fred requires provider_policy.historical_cutoff")
        return request

    def _dispatch(
        self,
        provider_id: str,
        capability_id: str,
        parameters: dict[str, Any],
        cutoff: str | None,
        *,
        issuer_origin_binding: VerifiedIssuerOrigin | None,
    ) -> list[ProviderEnvelope]:
        provider = self._provider(provider_id)
        if provider_id == "alfred-fred":
            result = provider.observations(parameters["series_id"], cutoff=cutoff)
        elif provider_id == "sec" and capability_id in {"sec.submissions", "sec.filings"}:
            filing_request = {**parameters, "capability": capability_id.split(".", 1)[1]}
            result = provider.execute(filing_request, cutoff=cutoff)
        elif provider_id == "issuer-ir" and capability_id == "issuer-ir.document":
            result = provider.collect(parameters, cutoff=cutoff, verified_origin=issuer_origin_binding)
        else:
            result = provider.collect(parameters)
        return self._as_envelopes(result)

    def _provider(self, provider_id: str) -> Any:
        factory = self._factories.get(provider_id)
        if factory is not None:
            return factory(provider_id=provider_id, config=dict(self._config.get(provider_id, {})), clock=self._clock)
        if provider_id == "alfred-fred":
            from serenity_core.providers.fred import FredProvider

            api_key = self._config.get(provider_id, {}).get("api_key")
            return FredProvider(api_key=api_key if isinstance(api_key, str) else None, clock=self._clock)
        if provider_id == "sec":
            from serenity_core.providers.filings import FilingsProvider

            return FilingsProvider(clock=self._clock)
        if provider_id == "issuer-ir":
            from serenity_core.providers.issuer_ir import IssuerIRProvider

            return IssuerIRProvider(clock=self._clock)
        from serenity_core.providers.public_data import public_data_catalog

        provider_config = self._public_data_config(provider_id)
        catalog = public_data_catalog(clock=self._clock, config=provider_config)
        if provider_id not in catalog:
            raise LookupError("no executable adapter is registered for this catalog provider")
        return catalog[provider_id]

    def _public_data_config(self, provider_id: str) -> dict[str, str]:
        values = self._config.get(provider_id, {})
        definition = _PUBLIC_CREDENTIAL_CONFIG.get(provider_id)
        if definition is None:
            return {}
        config_key, aliases = definition
        for alias in aliases:
            credential = values.get(alias)
            if isinstance(credential, str) and credential:
                return {config_key: credential}
        return {}

    @staticmethod
    def _as_envelopes(result: Any) -> list[ProviderEnvelope]:
        candidates: Sequence[Any] = result if isinstance(result, Sequence) and not isinstance(result, (str, bytes, ProviderEnvelope)) else [result]
        envelopes: list[ProviderEnvelope] = []
        for candidate in candidates:
            if not isinstance(candidate, ProviderEnvelope):
                raise TypeError("provider returned a non-envelope result")
            validate_document(candidate.to_dict(), PROVIDER_ENVELOPE_SCHEMA_ID)
            envelopes.append(candidate)
        return envelopes

    def _enforce_cutoff(
        self,
        envelopes: list[ProviderEnvelope],
        cutoff: str | None,
        provider_id: str,
        request: Mapping[str, Any],
    ) -> list[ProviderEnvelope]:
        if cutoff is None:
            return envelopes
        cutoff_at = _as_instant(cutoff)
        eligible: list[ProviderEnvelope] = []
        for envelope in envelopes:
            document = envelope.to_dict()
            if document["status"] != "available":
                eligible.append(envelope)
                continue
            available_at = document["temporal"]["available_at"]
            if isinstance(available_at, str) and _as_instant(available_at) <= cutoff_at:
                eligible.append(envelope)
        if eligible:
            return eligible
        return [self._registry_envelope(provider_id, request, "unavailable", "provider evidence was not available by historical cutoff")]

    def _finalize(
        self,
        envelopes: list[ProviderEnvelope],
        *,
        provider_id: str | None = None,
        request: Mapping[str, Any] | None = None,
    ) -> list[ProviderEnvelope]:
        if not envelopes:
            if provider_id is None or request is None:
                raise AssertionError("registry fallback needs provider and request")
            envelopes = [self._registry_envelope(provider_id, request, "unavailable", "provider returned no envelopes")]
        sanitized = [envelope.with_document(self._redact_source_parameters(envelope.to_dict())) for envelope in envelopes]
        for envelope in sanitized:
            validate_document(envelope.to_dict(), PROVIDER_ENVELOPE_SCHEMA_ID)
        return sorted(sanitized, key=self._sort_key)

    @staticmethod
    def _sort_key(envelope: ProviderEnvelope) -> tuple[str, str, str, str, str]:
        document = envelope.to_dict()
        temporal = document["temporal"]
        return (
            document["provider"],
            temporal["available_at"] or "",
            temporal["effective_at"] or "",
            temporal["source_version"] or "",
            json.dumps(document, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def _registry_envelope(
        self, provider_id: str, request: Mapping[str, Any], status: str, reason: str
    ) -> ProviderEnvelope:
        return ProviderEnvelope.unavailable(
            provider=provider_id,
            provider_version=REGISTRY_PROVIDER_VERSION,
            source_uri=f"https://registry.serenity.local/providers/{provider_id}",
            fetched_at=self._clock(),
            request={"evidence_request_id": request["request_id"], "capability_id": request["capability_id"]},
            status=status,
            reason=reason,
            parse={"status": "not_parsed", "transform_version": REGISTRY_PROVIDER_VERSION},
        )

    @staticmethod
    def _redact_source_parameters(document: dict[str, Any]) -> dict[str, Any]:
        source = document.get("source")
        parameters = source.get("parameters") if isinstance(source, Mapping) else None
        if not isinstance(parameters, Mapping):
            return document
        redacted = EvidenceProviderRegistry._redact_parameters(parameters)
        return {**document, "source": {**source, "parameters": redacted}}

    @staticmethod
    def _redact_parameters(value: Any) -> Any:
        if isinstance(value, Mapping):
            return {
                key: "[REDACTED]"
                if EvidenceProviderRegistry._is_secret_parameter(key)
                else EvidenceProviderRegistry._redact_parameters(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [EvidenceProviderRegistry._redact_parameters(item) for item in value]
        return value

    @staticmethod
    def _is_secret_parameter(key: Any) -> bool:
        if not isinstance(key, str):
            return False
        normalized = key.lower().replace("-", "_")
        return normalized in _SECRET_PARAMETER_NAMES or normalized.endswith(("_api_key", "_registration_key"))
