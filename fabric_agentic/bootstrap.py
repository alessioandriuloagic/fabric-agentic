"""Colleague-ready project starter: an instance profile plus a human bootstrap checklist."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from fabric_agentic.instance_profile import SLUG


DEFAULT_PROJECT_SLUG = "cliente_demo"
DEFAULT_DISPLAY_NAME = "Cliente Demo"

INSTANCE_FILE_NAME = "instance.json"
CHECKLIST_FILE_NAME = "CHECKLIST.md"

_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9_]+")


class InitError(Exception):
    """Raised before any file is written: init never leaves a starter half-created."""


@dataclass(frozen=True)
class InitResult:
    written: tuple[Path, ...]
    skipped: tuple[Path, ...]


def slug_from_directory(directory: Path) -> str:
    """Derive a project slug from a directory name, for a colleague who omits --project-slug."""

    candidate = _SLUG_INVALID_CHARS.sub("_", directory.resolve().name.lower()).strip("_")
    if not candidate:
        return "project"
    if not candidate[0].isalpha():
        candidate = f"p_{candidate}"
    return candidate


def build_profile_document(project_slug: str, display_name: str) -> dict:
    if not SLUG.match(project_slug):
        raise InitError("the project slug must be lowercase alphanumeric with underscores")
    return {
        "schema_version": "1.0",
        "project": {"slug": project_slug, "display_name": display_name},
        "tracker": {
            "type": "github_issues",
            "owner": "REPLACE_WITH_OWNER",
            "repository": "REPLACE_WITH_REPOSITORY",
        },
        "environments": ["dev"],
        "sources": [
            {
                "name": "crm_demo",
                "connector": "crm_dataverse",
                "connection_ref": "REPLACE_WITH_FABRIC_CONNECTION_ID",
                "datasets": [
                    {
                        "name": "accounts",
                        "primary_key": ["accountid"],
                        "load_mode": "incremental",
                        "watermark_column": "modifiedon",
                    }
                ],
            }
        ],
        "credentials": [
            {
                "name": "execution_credential",
                "store": "key_vault",
                "reference": "REPLACE_WITH_SECRET_REFERENCE",
            }
        ],
    }


def render_instance_profile(project_slug: str, display_name: str) -> str:
    document = build_profile_document(project_slug, display_name)
    return json.dumps(document, indent=2, ensure_ascii=False) + "\n"


def render_checklist(project_slug: str, display_name: str) -> str:
    return f"""# Checklist di bootstrap — {display_name}

Generata da `fabric-agentic init` per il progetto `{project_slug}`. Nessun passaggio qui è
automatizzabile dagli agenti: creare identità e assegnare permessi resta, per scelta di sicurezza,
un compito umano. Procedura completa e motivazioni:
[docs/functional/06-onboarding-nuovo-cliente.md](docs/functional/06-onboarding-nuovo-cliente.md).

## Identità e permessi

- [ ] Predisporre le identità di Issue, Dev e Review Agent, distinte da account personali e dalla
      credenziale tecnica del cliente
- [ ] Scegliere una sola `ExecutionCredential` per `{project_slug}`: SP OIDC, SP con secret o
      utenza di servizio
- [ ] Assegnare alla `ExecutionCredential` i soli permessi necessari su workspace e sorgenti

## Fabric

- [ ] Verificare che la capacity di destinazione sia attiva e dimensionata sul carico previsto
- [ ] Creare il workspace `dev` (e gli altri ambienti dichiarati in `instance.json`) e assegnare
      la `ExecutionCredential` con il ruolo minimo necessario
- [ ] Verificare che il Dev Agent non abbia ruoli di scrittura Fabric né accesso diretto alle
      connessioni dati, e che Issue e Review non abbiano alcun accesso a Fabric

## Git

- [ ] Creare il repository e la board con gli stati previsti dal ciclo di vita
- [ ] Creare le etichette `issue-agent` / `dev-agent` richieste dai dispatcher
- [ ] Vietare il push diretto su `main` a tutti e tre gli agenti e richiedere pull request
- [ ] Rendere obbligatoria l'approvazione umana in aggiunta al voto del Review Agent
- [ ] Verificare la policy provando un push con l'identità di un agente e confermando il rifiuto

## Secret store

- [ ] Custodire la `ExecutionCredential` in Key Vault (o secret store equivalente): l'agente non
      deve poterla leggere, solo il rail deterministico la intermedia
- [ ] Registrare in `instance.json` solo riferimenti al secret store, mai credenziali in chiaro

## Profilo di istanza

- [ ] Compilare i placeholder `REPLACE_WITH_*` in `{INSTANCE_FILE_NAME}`
- [ ] `python -m fabric_agentic validate --config {INSTANCE_FILE_NAME}`
- [ ] `python -m fabric_agentic render --config {INSTANCE_FILE_NAME} --output .generated`

## Ambiente locale dell'operatore

- [ ] `python -m fabric_agentic doctor` verde su Issue, Dev e Review
- [ ] Avviare ogni dispatcher con `--once --dry-run` prima del primo ciclo reale

## Aggiornare a uno schema successivo

`instance.json` dichiara `schema_version`. Quando il pacchetto ne introduce una nuova, aggiorna il
valore secondo il `CHANGELOG.md` del kit, poi ri-esegui `validate` e `render`: un diff del piano
rigenerato è la verifica che la migrazione non abbia cambiato nulla di inatteso.
"""


def init(
    directory: Path,
    project_slug: str | None = None,
    display_name: str | None = None,
    force: bool = False,
) -> InitResult:
    """Write a starter instance profile and checklist. Idempotent: existing files are left alone."""

    slug = project_slug or slug_from_directory(directory)
    name = display_name or slug

    # Validate before touching the filesystem: init never leaves a half-written starter.
    instance_document = render_instance_profile(slug, name)
    checklist_document = render_checklist(slug, name)

    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    skipped: list[Path] = []
    for file_name, content in (
        (INSTANCE_FILE_NAME, instance_document),
        (CHECKLIST_FILE_NAME, checklist_document),
    ):
        path = directory / file_name
        if path.exists() and not force:
            skipped.append(path)
            continue
        path.write_text(content, encoding="utf-8", newline="\n")
        written.append(path)

    return InitResult(written=tuple(written), skipped=tuple(skipped))
