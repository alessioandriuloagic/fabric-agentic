# 06 — Onboarding di un nuovo cliente

> Risponde alla domanda: *"arriva un nuovo cliente — apriamo un progetto, apriamo un task e via?"*
>
> **Risposta breve: no.** Serve un gradino umano prima, e non è un limite temporaneo del sistema:
> è una scelta di sicurezza deliberata.

---

## 1. Perché non basta aprire un task

Due ragioni, entrambe strutturali.

### 1.1 Il problema dell'uovo e della gallina

Il dispatcher è in polling **su un progetto specifico**. Per aprire un task che dice "crea il
progetto", il progetto dovrebbe già esistere. Il primo anello della catena non può che essere
esterno alla catena.

### 1.2 L'escalation di privilegi

Il gradino umano non serve solo a rompere la circolarità. Serve soprattutto a questo:

> **Un agente non può creare la propria identità, né assegnarsi i propri permessi.**

Se il Dev Agent potesse creare service principal e attribuire permessi, l'intero modello di
sicurezza sarebbe decorativo: qualunque limite gli avessimo imposto, potrebbe rimuoverlo.
La creazione delle identità e l'assegnazione dei permessi restano fuori dal perimetro degli
agenti **per sempre**, non solo in fase 1.

---

## 2. I tre livelli di onboarding

```mermaid
flowchart TB
    L1["LIVELLO 1 · Bootstrap del progetto<br/>umano assistito da script · una tantum<br/>identità, permessi, repo, board, policy"]
    L2["LIVELLO 2 · Bootstrap della piattaforma<br/>primo ticket agentico<br/>workspace, cartelle, task flow, git integration"]
    L3["LIVELLO 3 · Onboarding delle sorgenti<br/>ticket agentici ricorrenti<br/>dataset, semantic model, report"]

    L1 --> L2 --> L3

    style L1 fill:#f6c667,stroke:#b8860b
    style L2 fill:#cfe8dd,stroke:#2e7d63
    style L3 fill:#cfe8dd,stroke:#2e7d63
```

| Livello | Chi | Frequenza | Automatizzabile |
|---|---|---|---|
| **1 — Bootstrap del progetto** | Umano, con script di supporto | Una volta per cliente | Parzialmente: lo script fa il lavoro, l'umano autorizza |
| **2 — Bootstrap della piattaforma** | Dev Agent | Una volta per cliente | Sì, interamente |
| **3 — Onboarding delle sorgenti** | Dev Agent | Continuo | Sì, interamente |

Solo il **Livello 1** richiede presenza umana. Ed è l'unico che si paga una volta sola.

---

## 3. Livello 1 — Bootstrap del progetto

### 3.1 Cosa serve prima di iniziare

| Prerequisito | Note |
|---|---|
| Tenant con capacity Fabric attiva | Dimensionata sul carico previsto |
| Organizzazione Azure DevOps (o GitHub) | Il tracker su cui girerà il flusso |
| Tenant dell'organizzazione Azure DevOps | Coincide con il tenant Fabric delle identità agentiche, oppure la migrazione di directory è completata prima di aggiungere gli SP |
| Credenziale tecnica per il cliente | SP OIDC, SP con secret oppure utenza di servizio; scelta e autorizzazione sono umane |
| Nome progetto | Diventa il segmento variabile del naming (`ws_<progetto>_<ambiente>`) |
| Identità di inferenza aziendale per Issue, Dev e Review | **Non l'account personale dell'operatore.** Oggi tutti e tre invocano lo stesso Claude Code sotto un login individuale (vedi `CONTEXT.md`, riga "Runtime dei tre agenti", e PRD Q-13): con un cliente reale o un collega serve un seat/licenza aziendale, con budget e policy propri, prima di avviare un solo dispatcher |

### 3.2 Checklist di bootstrap

**Identità e permessi** *(richiede un amministratore del tenant)*

- [ ] Predisporre le identità di Issue, Dev e Review Agent nell'organizzazione AGIC, distinte dalla credenziale del cliente e da qualunque account personale
- [ ] Associare l'organizzazione Azure DevOps al tenant Fabric che ospita le identità agentiche; per la sandbox è Agic Dev (`1cf6db06-3e00-48b6-a65c-be932526610e`)
- [ ] Verificare prima che l'Organization Owner sia un membro **attivo** del tenant di destinazione; il portale rifiuta il cambio directory per utenti esterni o non provisionati
- [ ] Scegliere una sola `ExecutionCredential` per il cliente: SP OIDC, SP con secret o utenza di servizio
- [ ] Se si usa utenza di servizio: verificare che MFA e Conditional Access permettano un uso non interattivo
- [ ] Custodire la credenziale o il suo riferimento in Azure Key Vault / secret store; l'agente non deve poterla leggere
- [ ] Assegnare alla `ExecutionCredential` i soli permessi necessari su workspace e sorgenti del cliente
- [ ] Creare il gruppo di sicurezza degli agenti e attivare gli switch di tenant necessari per le sole diagnosi consentite
- [ ] Verificare che il Dev Agent non abbia ruoli di scrittura Fabric né accesso diretto alle connessioni dati
- [ ] Verificare che il Review Agent **non** abbia alcun accesso a Fabric
- [ ] Verificare che l'Issue Agent **non** abbia alcun accesso a Fabric né possa creare o modificare work item
- [ ] Provisionare l'identità di inferenza aziendale (Claude Code o equivalente) e verificare che nessun dispatcher usi ancora un login personale
- [ ] Registrare solo riferimenti al secret store — mai credenziali in file di configurazione

**Esito sandbox Agentic (2026-08-20)**

- Tenant Fabric: Agic Dev (`1cf6db06-3e00-48b6-a65c-be932526610e`)
- Sottoscrizione: `898b6a78-11dd-4e23-bf53-9e17f541d955`; capacity: `fabricalessiodev`
- Dev Agent: `fabric-agentic-dev-agent` (app ID `e74ca724-e306-4ff3-ae02-77ef7368e673`)
- Review Agent: `fabric-agentic-review-agent` (app ID `a6d3e2af-92e5-447a-bb1e-9a466e1bdaed`)
- Nessun secret, ruolo Fabric o credenziale tecnica sorgente è stato ancora assegnato.
- Organizzazione Azure DevOps attiva: `AlessioAndriuloDev`, progetto `fabric-agentic`.
- Work item migrate nel nuovo progetto: #1 (S0-03), #2 (S0-04), #3 (S0-05), #4 (S0-N5), #5 (S0-N2).
- L'organizzazione precedente `alessioandriulo` resta la sorgente storica e non e' piu' il tracker operativo.
- Service principal presenti nell'organizzazione: Dev Agent con licenza `Basic`, Review Agent con licenza `Stakeholder`; entrambi risultano in provisioning `pending`.
- Workspace DEV creato: `ws_agentic_dev` (`b829fa8e-71c9-4f7f-b136-5b3c3a64d8ee`); Dev Agent assegnato come `Contributor`, senza permessi sulla capacity.
- Federated credential GitHub Actions configurata per l'environment `dev`; test riuscito su `main` con run `32468016615`, verificando login federato e lettura dei metadati del workspace.
- Environment GitHub `test` e `prod` creati. Le protection rules non sono disponibili sul piano corrente; il processo obbligatorio resta branch dedicato, PR verso `main` e merge umano.

**Tracker**

- [ ] Creare il progetto e il repository della soluzione
- [ ] Creare il repository o lo spazio della knowledge base
- [ ] Configurare la board con gli stati previsti dal ciclo di vita
- [ ] Creare il tag riservato al Dev Agent, e le etichette `issue-agent` / `dev-agent` per l'Issue Agent
- [ ] Assegnare ai tre service principal i permessi minimi previsti dal modello

**Protezione del ramo principale** *(il passo più importante dell'intero bootstrap)*

- [ ] Vietare il push diretto su `main` a **tutti e tre** gli agenti
- [ ] Richiedere la pull request per ogni modifica
- [ ] Rendere obbligatoria l'approvazione umana **in aggiunta** a quella del Review Agent
- [ ] **Verificare la policy provandola**: tentare un push con l'identità dell'agente e
      confermare che venga rifiutato

> L'ultimo punto non è pedanteria. Una policy configurata e mai verificata è una policy di cui
> non sai nulla. È il primo controllo che salterà, sotto pressione, e l'unico che non puoi
> permetterti di dare per buono.

**Knowledge base**

- [ ] Popolare `CONTEXT.md` con il nome progetto e le eventuali convenzioni specifiche
- [ ] Portare la documentazione funzionale nel nuovo progetto
- [ ] Generare la wiki dalla documentazione versionata

**Profilo di istanza**

- [ ] `python -m fabric_agentic init --directory profiles/<cliente> --project-slug <cliente> --display-name "<Nome cliente>"`
      genera `instance.json` e una `CHECKLIST.md` con questa stessa checklist, parametrizzata sul progetto —
      idempotente: rilanciato non sovrascrive file già modificati, a meno di `--force`
- [ ] In alternativa, usare la pagina statica di onboarding pubblicata da
      `.github/workflows/publish-onboarding-pages.yml`: il form legge schema e capacità dei connector
      generati dal package, lavora solo nel browser e scarica `instance.json` senza chiamare Fabric,
      GitHub API, Azure DevOps o secret store
- [ ] Compilare i placeholder `REPLACE_WITH_*` in `instance.json`: tracker, connessioni, riferimento al secret store
- [ ] Per una tecnologia senza adapter registrato (es. Business Central, Oracle, PostgreSQL o
      SharePoint), dichiarare `capabilities.supports_incremental` e
      `capabilities.supports_source_count`; un profilo valido descrive la sorgente ma il primo
      ticket deve ancora implementare e registrare l'adapter operativo
- [ ] `python -m fabric_agentic validate --config <profilo>` senza errori
- [ ] `python -m fabric_agentic render --config <profilo> --output .generated` e rilettura del piano

**Ambiente locale dell'operatore**

- [ ] Installare i tre runtime agentici in ambienti di esecuzione separati
- [ ] Predisporre il layout canonico per Issue, Dev e Review sotto `~/.fabric-agentic/<agente>-agent/`
      (vedi `../technical/12-console-e-avvio.md`)
- [ ] `python -m fabric_agentic doctor` verde su tutti e tre
- [ ] Verificare che ciascun dispatcher si autentichi con **il proprio** service principal
- [ ] Avviare i dispatcher con `--once --dry-run` e confermare il polling a vuoto, senza consumo di token

### 3.3 Cosa è asset e cosa è specifico del cliente

La distinzione va tenuta netta, altrimenti l'asset smette di essere riusabile al secondo cliente.

| Riusabile (asset) | Specifico dell'istanza |
|---|---|
| Documentazione funzionale e runbook | Nome progetto, tenant, identificativi |
| Checklist di review | Sorgenti dati e loro configurazione |
| Istruzioni degli agenti | Credenziali e riferimenti al secret store |
| Contratto `ExecutionCredential` e rail diagnostico | Tipo concreto della credenziale e relativo riferimento nel secret store |
| Script deterministici | Dimensionamento della capacity |
| Framework metadata-driven e connettori | Convenzioni specifiche concordate col cliente |
| Convenzioni di naming (come schema) | Il valore del segmento `<progetto>` |

**Regola**: tutto ciò che è specifico dell'istanza vive in **un unico punto parametrico**. Se
per istanziare un nuovo cliente devi cercare e sostituire un nome in più file, l'asset è già
degradato.

---

## 4. Livello 2 — Bootstrap della piattaforma

Prima del primo ticket agentico, l'owner predispone il solo workspace DEV e la relativa
identità/credential di deploy. `test` e `prod` restano non provisionati finché non esistono
workspace, credenziali e controlli dedicati.

Il primo ticket reale del nuovo cliente è:

> **"Onboarda un dataset sintetico/open data nel layer Bronze del feature workspace"**

Il Dev Agent:

1. crea branch e feature workspace tramite i rail;
2. applica la configurazione dichiarativa del dataset;
3. sincronizza ed esegue il carico nel feature workspace;
4. allega le evidenze di qualità dati;
5. aggiorna la documentazione della sorgente;
6. apre la PR.

> Questo ticket ha un valore che va oltre il risultato: è il **collaudo della catena**. Se
> funziona, sai che identità, rail, dispatcher, sincronizzazione Git, esecuzione e qualità dati
> sono tutti configurati correttamente prima di affrontare dati reali di cliente.

---

## 5. Livello 3 — Onboarding delle sorgenti

Ticket ordinari, secondo [03 — Runbook: onboarding di una sorgente](03-runbook-onboarding-sorgente.md).

Da questo punto il cliente è operativo e il sistema procede a regime.

---

## 6. Quanto costa un nuovo cliente

| Livello | Impegno | Chi |
|---|---|---|
| 1 — Bootstrap del progetto | Sessione di configurazione, con un amministratore di tenant disponibile | Umano |
| 2 — Bootstrap della piattaforma | Un ticket | Agente |
| 3 — Prima sorgente | Un ticket | Agente |

Il vincolo di pianificazione non è tecnico: è la **disponibilità dell'amministratore del tenant**
per la creazione delle identità e degli switch. Va prenotata in anticipo, non improvvisata il
giorno del kickoff.

---

## 7. Errori da non ripetere

| Errore | Conseguenza |
|---|---|
| Saltare la verifica pratica della branch policy | Scopri che gli agenti possono pushare su `main` nel momento peggiore |
| Dare al Review Agent accesso a Fabric "per comodità" | Perdi l'indipendenza della review: chi giudica può produrre le evidenze che giudica |
| Usare lo stesso service principal per entrambi gli agenti | L'audit log diventa inutilizzabile, i permessi si sommano |
| Consegnare la credenziale tecnica al Dev Agent | Un segreto cliente entra nel perimetro del modello e annulla la separazione tra analisi e accesso dati |
| Riutilizzare la stessa credenziale tecnica fra clienti | Un incidente o una revoca coinvolgono clienti distinti; audit e blast radius diventano indistinguibili |
| Copiare la configurazione da un altro cliente senza parametrizzarla | Riferimenti incrociati tra tenant diversi |
| Rinviare la knowledge base a dopo il primo ticket | Gli agenti improvvisano convenzioni, che poi vanno disfatte |
| Usare lo stesso vendor per Dev e Review Agent | La review perde valore: stesso modello, stessi punti ciechi |

> L'ultimo punto è quello che verrà proposto più spesso come "semplificazione". È anche quello
> che svuota di senso l'intera architettura: due istanze dello stesso modello condividono i
> medesimi errori sistematici, e il revisore non vedrà proprio ciò che lo sviluppatore non ha visto.
