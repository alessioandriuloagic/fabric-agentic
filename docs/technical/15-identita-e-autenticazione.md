# 15 - Identita' e autenticazione per sistema

Decisione: [ADR-0019](../adr/ADR-0019-identita-per-sistema-e-login-assistito.md).
Il login del tracker, quello Fabric e la licenza del runtime AI non sono intercambiabili.

## 1. Stato implementato

| Percorso | Configurazione | Stato |
|---|---|---|
| GitHub App | Campi App esistenti; autenticazione omessa o `github_app` | Default compatibile |
| GitHub utente | `github.authentication`, modo `github_user` | Dev, Issue e Review: discovery/clone; publisher nominali |
| Azure Boards SP | Campi certificato esistenti; modo omesso o `entra_sp` | Percorso Dev esistente |
| Azure Boards utente | `azure_devops.authentication`, modo `entra_user` | Provider e tracker Dev implementati, non collaudati live |
| Azure Boards Issue/Review | Non disponibile nei dispatcher Issue/Review | Da implementare; non usare config nominale per dichiararlo pronto |
| Fabric utente | Profilo `execution.delegated_assisted` | Login, status read-only e logout implementati e provati live |
| Fabric deploy/carichi dal Dev | Rail OIDC esistenti | Collegamento nominale non implementato |
| Runtime AI | `agent.claude_command`; profilo `inference` | Comando configurabile; riferimenti dichiarativi, non provisioning/login |

Il core valida e renderizza il profilo; non genera automaticamente le configurazioni dei tre
dispatcher. Il mapping per ruolo va riportato nel file operativo del ruolo corrispondente.
Non c'e' autenticazione universale: permessi repo/workspace, consenso, SSO e CA restano del cliente.

## 2. Profilo di istanza

Nel campo `tracker` aggiungere `authentication` per i ruoli interessati:

```json
{
  "type": "github_issues",
  "owner": "cliente",
  "repository": "soluzione",
  "authentication": {
    "issue": {"mode": "github_user", "account": "collega", "config_directory": "~/.fabric-agentic/tracker-contexts/cliente-github"},
    "dev": {"mode": "github_user", "account": "collega", "config_directory": "~/.fabric-agentic/tracker-contexts/cliente-github"},
    "review": {"mode": "github_user", "account": "collega", "config_directory": "~/.fabric-agentic/tracker-contexts/cliente-github"}
  }
}
```

`github_app` ed `entra_sp` richiedono solo `mode` nel blocco di scelta; i campi della credenziale
applicativa restano nella configurazione operativa preesistente. Le modalita' incompatibili con
il tracker, ruoli sconosciuti, token/password o campi extra sono rifiutati.

Il blocco Fabric rimane indipendente:

```json
{"mode": "delegated_assisted", "tenant_id": "<tenant-uuid>", "workspace_id": "<workspace-uuid>", "account": "<upn-cliente>"}
```

Questa e' la forma del campo `execution`, non un file completo. Per generare il profilo:

```powershell
python -m fabric_agentic init --directory profiles/cliente --tenant-id "<tenant-uuid>" --workspace-id "<workspace-uuid>" --account "<upn-cliente>"
python -m fabric_agentic validate --config profiles/cliente/instance.json
python -m fabric_agentic render --config profiles/cliente/instance.json --output .generated
```

Per l'inferenza e' disponibile il campo opzionale:

```json
{
  "issue": {"command": "claude", "identity_ref": "enterprise-seat://agic/issue"},
  "dev": {"command": "claude", "identity_ref": "enterprise-seat://agic/dev"},
  "review": {"command": "claude", "identity_ref": "enterprise-seat://agic/review"}
}
```

Questa e' la forma di `inference`. Usare i riferimenti effettivamente approvati, non copiare gli
esempi come prova di licenze. Il comando operativo resta `agent.claude_command`: il render non
avvia login AI, non imposta account e non prova indipendenza del modello Review.

## 3. Configurare GitHub nominale

Preparare una directory locale privata, fuori dal repo e dal contesto leggibile del modello.
Eseguire login personalmente nel terminale o browser; mai inviare password, OTP o token in chat.

```powershell
$previousGhConfig = $env:GH_CONFIG_DIR
$env:GH_CONFIG_DIR = "$env:USERPROFILE\.fabric-agentic\tracker-contexts\cliente-github"
gh auth login --hostname github.com --web --git-protocol https
$env:GH_CONFIG_DIR = $previousGhConfig
```

Verificare anche eventuale autorizzazione SSO richiesta dall'organizzazione GitHub cliente.
Non usare `gh auth token` in chat. Il provider cattura il token internamente, ignora token GitHub
ereditati dall'ambiente e verifica il login tramite `/user`; un account errato blocca il ciclo.

In ciascun `~/.fabric-agentic/<ruolo>-agent/dispatcher-config.json`, sostituire il blocco `github`
con owner/repository e l'autenticazione di quel ruolo:

```json
{
  "owner": "cliente",
  "repository": "soluzione",
  "authentication": {
    "mode": "github_user",
    "account": "collega",
    "config_directory": "~/.fabric-agentic/tracker-contexts/cliente-github"
  }
}
```

App ID, installation ID e PEM non sono richiesti in questa modalita'. Conservare `agent`, la
clone dedicata e, per Dev, `dispatcher.tracker_type: github_issues`. Non modificare una clone con
lavoro in corso. Usare una configurazione/clone separata per cliente e ruolo. Il provider supporta
qui github.com, non GitHub Enterprise Server con hostname personalizzato.

## 4. Configurare Azure Boards nominale (Dev)

Login nel tenant del tracker, che puo' essere diverso da Fabric:

```powershell
$previousAzureConfig = $env:AZURE_CONFIG_DIR
$env:AZURE_CONFIG_DIR = "$env:USERPROFILE\.fabric-agentic\tracker-contexts\cliente-ado"
az login --tenant "<tenant-tracker-uuid>" --allow-no-subscriptions
$env:AZURE_CONFIG_DIR = $previousAzureConfig
```

Nel blocco `azure_devops` della configurazione Dev:

```json
{
  "organization": "cliente",
  "project": "soluzione",
  "dev_agent_display_name": "[fabric-agentic-dev-agent]",
  "authentication": {
    "mode": "entra_user",
    "account": "collega@cliente.example",
    "tenant_id": "<tenant-tracker-uuid>",
    "config_directory": "~/.fabric-agentic/tracker-contexts/cliente-ado"
  }
}
```

Impostare `dispatcher.tracker_type: azure_devops`. Il provider verifica tenant, tipo utente e
UPN prima di acquisire il token per `https://app.vssps.visualstudio.com`. Nessun certificato SP
e' richiesto per Boards nominale. Il percorso Dev continua pero' a usare GitHub per clone, PR e
thread di review: conservare il blocco `github` e autenticarlo separatamente. Questo incremento
non implementa repository/PR Azure Repos o la catena Issue/Review Azure Boards.

## 5. Avvio, pubblicazione e fine lavoro

1. Installare il runtime AI aziendale e autenticarsi con il seat autorizzato.
2. Completare login tracker e Fabric separatamente; non avviare polling per chiedere MFA al modello.
3. Eseguire `python -m fabric_agentic doctor`: readiness nominale indica contesto dichiarato,
   **login non verificato**. La discovery verifica il login effettivo e i permessi API.
4. Provare ogni dispatcher con i comandi della guida avvio, usando `--once --dry-run`.
5. Avviare polling soltanto quando configurazione, clone e perimetro sono confermati.
6. Finito il lavoro, interrompere i dispatcher. Fare logout nelle stesse directory selezionate:
   `gh auth logout --hostname github.com`, `az logout` per il tracker; per Fabric usare
   `python -m fabric_agentic session logout --config <profilo>`.

I publisher ricevono account e directory, non token, via `--user-account` e
`--user-config-directory`, alternativi ai tre parametri App. Validano prima pacchetto/esito,
poi autenticano e pubblicano. Issue: autore + marcatore + fingerprint. Review: autore + marcatore
+ head SHA. Una review umana dello stesso account non equivale alla review agentica.
L'auto-review diventa COMMENT e riporta `requested_event` e `independent_identity: false`.
Non aggira il merge umano o le policy del repository.

Il broker mantiene i token fuori dall'argv Git; il wrapper del modello nega `gh auth`, `gh api`,
alias, estensioni e merge. Sono limitazioni del wrapper, non isolamento contro una shell/Python
arbitraria sullo stesso utente OS. I marcatori di ruolo non sono un confine crittografico.

## 6. Evidenze del 2026-10-06

| Prova | Esito e limite |
|---|---|
| Login Fabric nominale in Agic Dev | Account/tenant verificati, `read_verified` |
| Secondo `session status` | Successo senza nuovo login; non prova durata o rinnovo futuro |
| Creazione workspace operatore | `ws_agentic_auth_test_20261006`, ID `1e661f8f-e641-4a0d-a79a-e1577b149b0c` |
| Capacity verificata con GET | `fabricalessiodev`, ID `8626d394-40c1-4872-a1f1-25b8cfcbf6ad`, `Completed` |
| Perimetro workspace test | Vuoto alla creazione; nessun Git, item, carico o ruolo aggiuntivo configurato |
| Tracker nominali | Test deterministici, nessuna scrittura live o smoke cliente dichiarato |

La creazione workspace e' stata un test API esplicitamente autorizzato dell'operatore, non una
sessione Dev dispatchata e non un nuovo rail di produzione. Il workspace e' rimasto disponibile;
nessuna cancellazione automatica e' stata autorizzata. Il profilo live locale conserva il workspace
DEV usato per il preflight, non viene cambiato automaticamente al workspace appena creato.

## 7. Collaudo e limiti aperti

Test CI: provider e account errato, tenant Azure errato, config senza App/PEM, discovery nominale,
attribuzione commenti, publisher nominali idempotenti, auto-review COMMENT, blocco export token,
schema/profile/render, compatibilita' dei default applicativi. Prima di adozione su un cliente
eseguire gli smoke read-only con le sue identita' e policy; una suite mock non dimostra consenso,
licenza, SSO o RBAC reali. Restano aperti isolamento runtime, deploy/carichi nominali, Azure Repos,
Issue/Review Azure Boards e provisioning dei seat AI.

Fonti: [Azure CLI login/MFA](https://learn.microsoft.com/en-us/cli/azure/authenticate-azure-cli-interactively),
[GitHub CLI auth login](https://cli.github.com/manual/gh_auth_login),
[GitHub authenticated user](https://docs.github.com/en/rest/users/users#get-the-authenticated-user),
[Fabric create workspace](https://learn.microsoft.com/en-us/rest/api/fabric/core/workspaces/create-workspace).