# Next Step - 06/10/2026

**Data della nota: 06/10/2026**
**Ripartenza prevista: 07/10/2026**

Questa nota fotografa la sessione del 06/10/2026. Stati di tracker, processi, login e capacity
devono essere verificati di nuovo domani: quanto riportato non dimostra che siano ancora attivi.
I next step sono un ordine di lavoro proposto, non un'autorizzazione a merge, deploy o cancellazioni.

## Obiettivo

Portare il kit a un primo ciclo Dev Agent realmente eseguito senza SP cliente di esecuzione:
il collega fa login/MFA, lavora durante la propria sessione e ottiene evidenze e una PR.
Il setup deve essere ripetibile da un secondo collega senza modificare codice o copiare credenziali.

## Decisioni Confermate

- Tracker, Fabric e runtime AI hanno autenticazioni indipendenti.
- Sul tracker AGIC manteniamo le identita' applicative esistenti: GitHub Apps su GitHub,
  SP Entra nel percorso Azure DevOps. Non sono lo stesso oggetto.
- Sul tracker cliente e' ammessa un'utenza nominale o di servizio autorizzata.
- Per Fabric partiamo senza SP di esecuzione, con login/MFA interattivo del collega.
- Non serve operativita' unattended: il flusso lavora quando il collega lavora.
- Il merge resta umano. Una review nominale sulla propria PR pubblica COMMENT, non un voto.
- Cache distinte e wrapper non costituiscono isolamento dei processi dello stesso utente OS.

Decisione registrata in [ADR-0019](../adr/ADR-0019-identita-per-sistema-e-login-assistito.md).

## Stato Alla Fine Della Sessione

| Area | Evidenza | Cosa NON dimostra |
|---|---|---|
| Fabric nominale | Login, tenant/account e lettura workspace verificati live | Non prova deploy/carichi dal Dev Agent |
| Riuso sessione | Secondo `session status` riuscito senza nuovo login | Non prova durata della sessione o rinnovo dopo revoca |
| Workspace test | Creazione reale e capacity verificata con GET | Non e' stata una sessione Dev dispatchata |
| Tracker nominali | Implementati e testati offline | Nessuno smoke live nominale dei tre ruoli |
| Validazione locale equivalente alla CI | 292 test eseguiti, uno skipped su Windows; diagnostiche e diff puliti | Non e' un run CI remoto o una review indipendente |
| Documentazione | ADR, guida, contesto, runbook e changelog aggiornati localmente | Non sono stati eseguiti commit, push o merge |

### Riferimenti Operativi

- Profilo assistito locale: `%USERPROFILE%\.fabric-agentic\profiles\agic_dev_assisted\instance.json`.
- Tenant sandbox: `1cf6db06-3e00-48b6-a65c-be932526610e` (Agic Dev).
- Il profilo conserva il workspace DEV del preflight: `abb3a689-6a8a-4a98-88da-b3f7c6de05c5`.
- Workspace creato per il test: `ws_agentic_auth_test_20261006`.
- ID workspace test: `1e661f8f-e641-4a0d-a79a-e1577b149b0c`.
- Capacity: `fabricalessiodev`, F2, ID `8626d394-40c1-4872-a1f1-25b8cfcbf6ad`.
- Il workspace era vuoto alla creazione: niente Git, item, carichi o ruoli aggiuntivi configurati.
- Il workspace non e' stato cancellato. Non cambiare il profilo al nuovo ID automaticamente:
  il contesto della cache dipende anche dal workspace e potrebbe richiedere un nuovo login.

Questi identificativi sono configurazione sandbox, non valori da incorporare nel core riusabile.

## Ordine Di Ripartenza

### 1. Mettere In Sicurezza Il Lavoro Locale

- [ ] Controllare `git status` e distinguere le modifiche di questa sessione da quelle gia' presenti.
- [ ] Non fare reset, checkout distruttivi o staging indiscriminato dei file temporanei.
- [ ] Preparare la consegna su branch dedicato, con review e PR; non commit diretto su `main`.
- [ ] Verificare nuovamente le PR #197 (dispatcher, #184) e #198 (demo, #196).
- [ ] Non confondere le PR pendenti con le modifiche locali dell'autenticazione.

Ultimo controllo live in questa sessione: entrambe le PR erano aperte, CI verde e senza review.
T1 #183 era chiuso; T2 #184 era ancora aperto. Non mergeare automaticamente.

**Esito atteso:** perimetro di consegna chiaro, nessuna modifica preesistente persa.

### 2. Ricontrollare La Sessione Fabric

```powershell
python -m fabric_agentic session status --config "$env:USERPROFILE\.fabric-agentic\profiles\agic_dev_assisted\instance.json"
```

Se restituisce `login_required`, effettuare `session login` con lo stesso profilo e completare
MFA nella finestra Microsoft. Password, token e OTP non vanno in chat, file del repo o log.
Verificare stato della capacity e workspace test prima di qualsiasi nuova scrittura.

**Esito atteso:** identita' nominale e destinazione confermate, oppure blocco esplicito da risolvere.

### 3. Collaudare I Tracker Nominali Live

- [ ] Scegliere account e repository autorizzati per il test, con contesto dedicato.
- [ ] Non sostituire le identita' applicative AGIC attive durante il collaudo.
- [ ] Provare GitHub nominale: identita' effettiva, discovery read-only e tre dispatcher in dry-run.
- [ ] Dopo autorizzazione delle scritture, provare pacchetto Issue e Review su intake/PR di test.
- [ ] Verificare marcatori, autore effettivo, idempotenza e auto-review limitata a COMMENT.
- [ ] Provare scadenza/login assente e account errato: nessun fallback ad App e nessun token esposto.
- [ ] Provare separatamente Azure Boards nominale per il tracker Dev, quando il contesto e' disponibile.

**Esito atteso:** evidenze live attribuibili per i percorsi realmente supportati.
Issue/Review Azure Boards e PR Azure Repos non sono implementati: non dichiararli collaudati.

### 4. Collegare Fabric Nominale Al Dev Agent

Questo e' il prossimo incremento funzionale principale: oggi l'autenticazione funziona,
ma il dispatcher non consegna ancora un ciclo Fabric nominale completo.

- [ ] Definire il contratto tra agente ed esecutore deterministico autenticato.
- [ ] Decidere esplicitamente il canale assistito: esecuzione locale controllata oppure rail CI/CD
  con contesto utente separato. Non riutilizzare una cache personale in un runner hosted.
- [ ] Registrare l'eventuale variazione di ADR-0007 prima di abilitare scritture fuori CI/CD.
- [ ] Limitare destinazioni e operazioni; il modello non deve ottenere token o una shell libera
  sul contesto autenticato. Dichiarare quali limiti sono tecnici e quali solo organizzativi.
- [ ] Implementare una sola slice verticale: ticket approvato, operazione Fabric autorizzata,
  evidenza strutturata correlata al tentativo e commento/PR del Dev Agent.
- [ ] Gestire login scaduto, 403, timeout ed esito incerto senza ripetere automaticamente una scrittura.
- [ ] Non usare il comando one-off di creazione workspace come prova di un rail riusabile gia' disponibile.

**Esito atteso:** una sessione Dev dispatchata compie una prima operazione verificabile senza SP
di esecuzione cliente, senza interventi tecnici umani nascosti oltre al login approvato.

### 5. Eseguire Un Tracer End-To-End

- [ ] Usare dati sintetici e perimetro non produttivo esplicito.
- [ ] Percorso: intake -> pacchetto -> approvazione -> Dev -> esecuzione reale -> evidenza -> PR
  -> Review -> decisione umana di merge.
- [ ] Raccogliere ID tentativo, revisione, run, conteggi/esiti e ogni intervento umano necessario.
- [ ] Verificare una ripresa controllata dopo blocco, senza doppia esecuzione o doppia pubblicazione.
- [ ] Provare il setup con un secondo collega e misurare tempo, passaggi e richieste di supporto.

**Esito atteso:** prova integrata della catena, non una somma di login e smoke separati.
Pubblicazione automatica DEV e cleanup non vanno dichiarati funzionanti se non implementati e provati.

### 6. Riprendere Il Backlog Dati Senza Confonderlo Con L'Autenticazione

- [ ] #158 CRM `accounts`: verificare il blocco corrente prima di riattivare `dev-agent`.
- [ ] Il delta controllato e la corrispondenza dell'evidenza per-run restano da chiudere.
- [ ] PR #176 era gia' mergiata al controllo del 06/10/2026: non trattarla come fix ancora pendente.
- [ ] Non modificare nuovamente il record demo senza prima verificare i delta gia' tentati.
- [ ] #196/#198: esecuzione manuale autorizzata dell'owner, due run e registrazione test in CI da verificare.
- [ ] Tracciare il limite di esecuzione notebook generica senza assorbirlo come correzione manuale invisibile.

**Esito atteso:** chiusura basata su artefatti del run e verifiche dati, non su CI verde o PR aperta.

## Fuori Scope Per La Prima Ripartenza

Produzione, promozioni, cancellazioni di workspace, cambio di permessi/identita' o policy tenant,
disattivazione MFA, migrazione unattended, nuovi connettori e completamento della lane Power BI.
Il provisioning dei seat AI aziendali resta una decisione organizzativa separata dal login cliente.

## Documenti Da Tenere Allineati

- [Guida autenticazione e limiti](15-identita-e-autenticazione.md).
- [ADR-0019](../adr/ADR-0019-identita-per-sistema-e-login-assistito.md).
- [Contesto vincolante](../../CONTEXT.md) e [changelog](../../CHANGELOG.md).
- [Inventario CRM accounts](14-inventario-catena-crm-accounts.md).
- [Ciclo di vita del ticket](../functional/01-ciclo-di-vita-ticket.md).

Ogni collaudo di domani deve aggiornare esito, data e riferimenti alle evidenze, distinguendo
test offline, osservazione live e punti ancora non verificati. Nessun segreto nelle evidenze.

## Primo Passo Domani

Ripartire dal punto 1, verificare `session status`, quindi fare il dry-run GitHub nominale del punto 3.
Solo dopo affrontare il collegamento Fabric al Dev Agent: e' il passaggio mancante per ottenere
la soluzione utilizzabile dai colleghi, non soltanto una credenziale che funziona.