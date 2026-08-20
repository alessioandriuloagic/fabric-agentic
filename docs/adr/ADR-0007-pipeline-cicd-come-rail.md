# ADR-0007 — Le pipeline CI/CD esistenti come rail e come canale di promozione

| Campo | Valore |
|---|---|
| Stato | **Accettato** — decisione dell'owner 2026-08-20 |
| Data | 2026-08-20b |
| Autore | Ralph (Fabric Solution Architect) |
| Supera | [ADR-0002](ADR-0002-promozione-ambienti-via-git.md) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §13 |
| Decisori | Owner · @reza (Data Engineering) · @marco (Power BI) |

---

## Contesto

ADR-0002 assumeva che la promozione tra ambienti fosse un *update from Git* eseguito manualmente
da un umano nell'interfaccia Fabric, perché nessun documento del design dichiarava un meccanismo
alternativo. L'assunzione era sbagliata per difetto di informazione, non di ragionamento: esiste
già in azienda un asset di deploy Fabric funzionante, `IP.dai_fabric_environments`, e l'owner ha
deciso che **i deploy passano da lì** — Azure DevOps Pipelines e GitHub Actions — e che **le
pipeline CI/CD diventano i rail degli agenti**.

Fatti rilevati per ispezione diretta dell'asset:

- deploy multi-tenant via GitHub Actions con **OIDC**, federated credential vincolata a
  `environment:deploy-<cliente>`, **nessun secret persistente in CI**;
- l'asset sorgente separa due ruoli: **Deploy** (OIDC effimero, Admin sui workspace, Capacity
  Contributor) e **Runtime** (secret nel Key Vault del cliente). In Agentic questi sono ruoli,
  non un requisito di due service principal: ogni cliente configura una sola `ExecutionCredential`
  adatta al proprio scenario;
- moduli Python idempotenti in `deploy/` (`workspace_manager`, `connection_manager`,
  `shortcut_manager`, `lake_manager`, `onelake_uploader`, `sjd_scheduler`);
- item deployati con la libreria **fabric-cicd** da `fabric-items/`;
- parametrizzazione per istanza in `config/<cliente>/` con validazione jsonschema fail-fast;
- **preflight anti cross-tenant** prima di ogni scrittura;
- workflow dedicati per operazioni distruttive e diagnostiche (`delete-workspace.yml`,
  `delete-connection.yml`, `*-diagnose.yml`);
- idempotenza e roll-forward come principio dichiarato (loro ADR-6).

Fatti di piattaforma verificati (fonti in `07-architecture-review.md` §13.7):

- **[V]** ado-permissions «Queue builds» è un permesso impostabile **sulla singola pipeline**, con
  `Allow`/`Deny` e ereditarietà disattivabile — ma il gruppo `Contributors` lo possiede **per
  default**;
- **[V]** approvals gli approvals & checks **non stanno nello YAML**: «Users modifying the pipeline
  yaml file can't modify the checks performed before start of a stage». Esistono i check
  **Approvals**, **Branch control**, **Required template**, **Exclusive lock**;
- **[V]** gh-oidc il claim `sub` del token OIDC vale `repo:org/repo:environment:<nome>` ed è emesso
  **per job**; **[V]** gh-environments un job che referenzia un environment con *required
  reviewers* non parte, e i suoi secret non sono accessibili, finché un umano non approva;
- **[V]** concurrency i job Spark avviati **da pipeline** vengono **accodati** sotto capacity
  satura; quelli avviati via API pubblica del notebook vengono **rifiutati**.

## Decisione

**1. I rail sono pipeline CI/CD.** I cinque rail dell'MVP diventano pipeline parametriche:
`pipe_agent_branch_out`, `pipe_agent_run_load`, `pipe_agent_sync`, `pipe_agent_diagnose_data`,
`pipe_sched_sweep`. Il rail
lato agente si riduce a: invocare la pipeline, attenderne il termine, leggerne l'artefatto.

**1-bis. Ogni cliente espone una sola `ExecutionCredential` alla pipeline, mai all'agente.** La
credenziale può essere un service principal con OIDC, un service principal con secret, oppure
un'utenza di servizio del cliente custodita in Azure Key Vault. Il tipo è configurazione
dell'istanza; il contratto dei rail non cambia. Non è richiesto che il cliente crei due service
principal. La credenziale non è riusata tra clienti e l'agente non può leggerla, esportarla o
impersonarla.

**2. La promozione tra ambienti è eseguita da pipeline CI/CD**, innescate da un umano e protette
da approvazione. Le **Fabric Deployment Pipelines non sono usate** — il rifiuto di ADR-0002 resta
valido e si rafforza. **Git resta la sorgente di verità**: ciò che è in produzione è un commit
identificabile; cambia solo chi applica quel commit al workspace.

**2-bis. Il merge umano su `main` attiva `pipe_ci_publish_dev`.** Questa pipeline legge il commit
mergiato da `main` e lo pubblica su DEV senza ulteriore intervento umano. Non è una pipeline
accodabile dal Dev Agent e non promuove verso test o produzione, che restano `pipe_human_*`.

**3. Due famiglie di pipeline, separate nel nome e nella sicurezza.**

| Famiglia | Chi la accoda | Bersaglio | Protezione |
|---|---|---|---|
| `pipe_agent_*` | Dev Agent, owner | Solo `feature` e `dev` | Nessun environment protetto consumato |
| `pipe_human_*` | Solo umani | `test`, `prod` | **`Deny`** su «Queue builds» per le identità degli agenti, con ereditarietà **disattivata**, **e** environment con check *Approvals* + *Branch control* |
| `pipe_sched_*` | Solo lo scheduler | Manutenzione | Non invocabile da alcun agente |

Il service principal degli agenti **non entra nel gruppo `Contributors`**: entrarci gli
concederebbe «Queue builds» su tutte le pipeline, produzione inclusa.

**4. La definizione della pipeline privilegiata è ancorata a `main`.** Il rail invoca una pipeline
**parametrizzata**, mai una pipeline la cui definizione YAML provenga dal branch di feature. Il
branch di feature è un *parametro* del run, non la sua definizione. Il vincolo è imposto da tre
meccanismi indipendenti: check **Branch control** su `refs/heads/main`, check **Required
template**, e restrizione di environment e service connection alle sole pipeline nominate.

> Senza il punto 4 l'intero modello è aggirabile: chi scrive lo YAML comanda l'identità con cui
> quello YAML gira, e quell'identità è Admin su Fabric. Vedi rilievo **RB-4**.

**5. Ogni pipeline invocabile da un agente pubblica un artefatto `rail-result.json`** con schema
versionato nel repo. **Il rail restituisce l'artefatto, non i log.** L'assenza dell'artefatto è un
fallimento del rail, distinto dal fallimento del job. Campi minimi:

```jsonc
{
  "schema_version": "1.0",
  "rail": "run_load",
  "outcome": "success | technical_failure | quality_failure",
  "run_id": "...",
  "workspace_id": "...",
  "datasets": [{
    "name": "...",
    "extracted_count": 0,
    "loaded_count": 0,
    "source_count": null,
    "supports_source_count": false,
    "pk_check": "passed | failed | not_applicable"
  }],
  "messages": []
}
```

La distinzione **fallimento tecnico / fallimento di qualità** è calcolata **dentro la pipeline**,
che ha l'accesso ai dati, e serializzata in `outcome`. L'agente non ha bisogno di accedere a
Fabric per decidere se correggere (blocco B1) o escalare (blocco B2).

**6. L'esecuzione dei carichi avviene sempre tramite pipeline, mai per chiamata diretta al
notebook.** La raccomandazione R1.2 della review smette di essere una buona pratica e diventa una
conseguenza necessaria del modello: **[V]** concurrency i job da pipeline sono accodati, quelli da
API del notebook sono rifiutati sotto throttling.

**7. Le pipeline dei rail sono piccole e dedicate.** Non si riusa la pipeline di deploy monolitica
dell'asset: una pipeline per rail, con dipendenze in cache. È una scelta di latenza, e la latenza
qui è un KPI (KPI-2, lead time < 30 minuti).

**8. Il rail `diagnose_data` rende l'analisi operativa un workflow quotidiano.** Esegue query e
controlli nel perimetro della `ExecutionCredential` e pubblica soltanto conteggi, statistiche,
schema drift, watermark, chiavi mascherate e campioni ammessi dalla policy cliente. Il Dev Agent
usa tali evidenze per investigare anomalie Bronze/Silver/sorgente senza ricevere dati grezzi o
segreti.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Rail come script locali che chiamano direttamente le API Fabric** (progetto originale) | Richiede credenziali Fabric long-lived sulla macchina dell'owner e permessi di scrittura al service principal dell'agente. Duplica plumbing già scritto, testato e in esercizio |
| **Fabric Deployment Pipelines** | Confermato il rifiuto di ADR-0002: incompatibili con PBIR, nessuna traccia in Git di cosa sia in produzione |
| **Una sola pipeline generica con un parametro `azione`** | Rende impossibile la separazione per permesso: «Queue builds» si concede o si nega **per pipeline**, non per parametro. Il controllo di sicurezza sparirebbe |
| **Rail ibridi: pipeline per la scrittura, chiamate dirette per la lettura** | È ciò che ADR-0008 concede in forma limitata e controllata. Come regola generale reintrodurrebbe due modi di fare la stessa cosa, e il secondo verrebbe usato "perché è più veloce" |
| **Un solo SP AGIC riutilizzato fra clienti** | Riduce l'onboarding apparente ma unisce audit, revoca e blast radius di clienti distinti. La semplificazione ammessa è una sola credenziale tecnica **per cliente**, non una credenziale globale |
| **Dipendere dal codice di `IP.dai_fabric_environments`** invece di copiarne i pattern | Decisione dell'owner. Registrata e discussa in ADR-0009 |

## Conseguenze

**Positive**
- Il service principal dell'agente **non ha più bisogno** dello switch di tenant «create
  workspaces, connections, and deployment pipelines»: **RB-1 è declassato**.
- Il divieto di deploy in produzione diventa una **proprietà del protocollo di autenticazione**
  (niente approvazione → niente token OIDC → niente accesso a Fabric), non una riga in una matrice.
- Si riusa plumbing già testato (89% di coverage sull'asset) anziché riscriverlo.
- Lo Sweep diventa una pipeline schedulata: **RB-3 è risolto** e funziona a macchina spenta.
- I job Spark vengono accodati anziché rifiutati sotto throttling.
- Ticket di anomalia, riconciliazione, schema drift, carico fermo e analisi sorgente seguono lo
  stesso workflow tracciabile di un ticket di sviluppo.

**Negative**
- **Latenza.** Accodamento, avvio dell'agente di build, checkout e installazione delle dipendenze
  si sommano a ogni invocazione. **[NV]** l'entità non è misurata; è un rischio su KPI-2 che va
  strumentato dallo Slice 1, non scoperto allo Slice 3.
- **Opacità.** Senza artefatto strutturato, il rail restituirebbe «pipeline fallita» e la diagnosi
  richiederebbe la lettura di log. Il punto 5 è la contromisura, e va costruito **prima** del primo
  rail, non dopo.
- **Nuova superficie da presidiare**: permessi di pipeline, environment, check, service connection.
  Sono oggetti di sicurezza che oggi il design non nomina affatto.
- **RB-4 è una falla che esiste solo in questo modello.** Non esisteva prima, la crea questa
  decisione, e va chiusa con il punto 4 e con i controlli 7 e 8 della verifica pratica di S0-06.
- **La lane Power BI resta scoperta.** **[NV]** il supporto di fabric-cicd per i report **PBIR** e
  per i semantic model TMDL non è verificato. È la stessa incompatibilità che aveva motivato
  ADR-0002: cambiare canale **non** la risolve automaticamente.
- Un'utenza di servizio può essere incompatibile con MFA o Conditional Access non automatizzabili;
  va verificata al bootstrap e sostituita da un SP quando non è utilizzabile in modo non interattivo.

**Da fare**
- **Spike obbligatorio in S1-01**: fabric-cicd supporta PBIR e TMDL? Se no, la promozione della
  lane Power BI ha bisogno di un canale proprio, e va deciso prima dello Slice 6.
- Item di backlog **N1**, **N2**, **N3** dello Slice 0 (§13.5 della review).
- Riscrivere `03-rail-script.md`: i contratti restano, cambia l'implementazione; aggiungere lo
  schema di `rail-result.json` e la regola del punto 4.
- Aggiornare `05-struttura-repository.md` con la collocazione delle definizioni di pipeline e della
  configurazione per istanza.
- Verificare praticamente il comportamento del `Deny` su «Queue builds» in presenza di
  appartenenza a gruppi con `Allow` — **[NV]**, la precedenza va provata, non assunta.
