# ADR-0004 — Ciclo di vita dei feature workspace: TTL e cleanup schedulato

| Campo | Valore |
|---|---|
| Stato | **Proposto** — richiede decisione prima dello Slice 1 |
| Data | 2026-08-20 |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §8 R-9 (rilievo bloccante RB-3) |
| Decisori | Owner · @mike (FinOps) |

---

## Contesto

RF-18 stabilisce che «il Dev Agent effettua il cleanup del feature workspace **dopo il merge**»
(priorità *Should*). RNF-06 chiede che i workspace orfani vengano rimossi. R-4 identifica il
consumo non controllato come rischio.

Il dispatcher del Dev Agent (`02-dispatcher.md` §3) ha **tre trigger**: work item taggato in
*To Do*, commento umano su work item in *Waiting input*, thread aperti sulla propria PR.

**Nessuno di questi si verifica dopo un merge.** RF-18 è quindi inattuabile per costruzione: non
esiste alcun evento che possa risvegliare l'agente per eseguire il cleanup. Il requisito fallisce
nel modo peggiore — **silenziosamente**: i workspace restano, il consumo cresce, nessuno riceve
un errore.

Esiste inoltre un caso che il trigger sul merge non coprirebbe nemmeno se esistesse: un ticket
**abbandonato o bloccato in *Waiting input* per sempre** non viene mai mergiato, e il suo
workspace non verrebbe mai rimosso. È anche il caso più probabile in un sistema che, per
progetto, preferisce fermarsi piuttosto che indovinare.

## Decisione

**1. Il cleanup non dipende dal merge: dipende dal tempo.** Ogni feature workspace ha un **TTL di
72 ore** dalla creazione.

**2. Viene introdotto un quarto componente: il rail *Sweep***, schedulato (una volta al giorno),
deterministico, che:

- elenca i workspace il cui nome corrisponde al pattern `ws_<progetto>_feature_wi<id>`;
- per ciascuno determina lo stato del work item corrispondente sul tracker;
- **cancella** i workspace il cui ticket è in *Done* o la cui PR è chiusa;
- **segnala all'owner**, senza cancellare, i workspace oltre TTL il cui ticket è ancora aperto;
- **cancella** i workspace orfani, cioè quelli il cui work item non esiste più.

**3. Il rail *Sweep* non è invocato dall'agente**: è invocato dallo scheduler, con l'identità del
Dev Agent. È il naming deterministico imposto da `CONTEXT.md` §3.2 a renderlo possibile — quella
regola trova qui la sua giustificazione operativa.

**4. Il tetto di 5 feature workspace concorrenti** (ADR-0001) è verificato dal rail *Branch out*
prima della creazione. Se il tetto è raggiunto, il rail **fallisce ed escala come blocco B4**: la
correzione è umana, perché significa che qualcosa non sta venendo chiuso.

**5. Il rail *Sweep* non cancella mai un workspace il cui ticket è aperto.** Cancellare un
workspace significa cancellare i dati che contiene: la distruzione automatica di lavoro in corso
non è un rischio che valga la pena correre per risparmiare CU su dati sintetici.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Aggiungere un quarto trigger "PR mergiata" al dispatcher** | Risolve solo il caso felice. Non copre i ticket abbandonati, che sono il caso in cui il cleanup serve davvero. Aggiunge inoltre uno stato al dispatcher, che il design vuole deliberatamente stupido |
| **Cleanup manuale dell'owner** | Contraddice il principio per cui ogni intervento tecnico umano nel ciclo è un difetto del sistema. Ed è la prima cosa che si smette di fare |
| **Cancellazione automatica al TTL, senza distinzione di stato** | Rischio di distruggere lavoro in corso su un ticket legittimamente lungo. Un falso positivo qui costa una sessione intera di lavoro |
| **Nessun TTL, solo il tetto di 5** | Il tetto trasforma la crescita silenziosa in un blocco improvviso: il sesto ticket fallisce e nessuno sa perché. Il TTL rende il problema visibile prima che diventi bloccante |

## Conseguenze

**Positive**
- RF-18 diventa attuabile e verificabile, invece di essere un requisito che nessun meccanismo può soddisfare.
- Il caso patologico reale (ticket abbandonato) è coperto.
- Il naming deterministico dei workspace acquista una funzione operativa, non solo estetica.
- Il consumo di capacity ha un limite superiore noto e imposto da script.

**Negative**
- Nuovo componente da costruire, versionare e presidiare (`scripts/`), con la propria schedulazione.
- Lo scheduler è un secondo punto di esecuzione oltre ai due dispatcher: in fase 1 gira sulla
  stessa macchina locale, con gli stessi limiti di disponibilità.
- Il rail *Sweep* deve leggere lo stato del work item: attraversa il confine tracker↔Fabric ed è
  quindi il primo script sensibile all'astrazione del tracker prevista da RF-06.

**Da fare**
- Riformulare RF-18 nel PRD: da «cleanup dopo il merge» a «cleanup schedulato con TTL», priorità **Must**.
- Aggiungere il contratto del rail *Sweep* a `03-rail-script.md` (§2: da 3 a 4 rail per l'MVP).
- Aggiungere al backlog dello Slice 1 l'item corrispondente.
- Aggiornare `02-dispatcher.md` chiarendo che lo Sweep **non** è un trigger del dispatcher.

---

## Revisione 2026-08-20b — lo Sweep è una pipeline schedulata

> Origine: `docs/technical/07-architecture-review.md` §13.2, buco 7. La **decisione resta
> invariata**; cambia l'esecutore.

**Cosa cambia.** Il punto 3 («il rail *Sweep* è invocato dallo scheduler con l'identità del Dev
Agent») è sostituito da:

> **3′.** Lo Sweep è una **pipeline CI/CD schedulata** (`pipe_sched_sweep`), che gira con
> l'identità di deploy. Il Dev Agent non lo invoca, non lo può invocare e non ha i permessi per
> eseguirlo.

**Perché.** Cancellare un workspace richiede il ruolo **Admin** sul workspace stesso **[V]**
roles-workspaces. Con ADR-0008 il Dev Agent è al massimo `Viewer`: non potrebbe eseguire lo Sweep
nemmeno volendo. L'identità di deploy della pipeline è già Admin, e l'operazione è già
implementata nell'asset `IP.dai_fabric_environments` (`.github/workflows/delete-workspace.yml`).

**Vincoli di piattaforma da rispettare, pena uno Sweep silenziosamente inerte** — tutti **[V]**
ado-schedules:

| Vincolo | Conseguenza |
|---|---|
| Una pipeline schedulata **non parte se il codice non è cambiato** dall'ultima esecuzione riuscita | `always: true` è **obbligatorio**: senza, lo Sweep smette di girare proprio nei periodi di inattività, cioè quando serve |
| Le schedulazioni definite nell'interfaccia **prevalgono** su quelle YAML | Nessuna schedulazione va aggiunta da UI. Va scritto nel runbook |
| La schedulazione è letta dallo YAML **del branch a cui si applica** | `pipe_sched_sweep` va schedulata su `main` |
| Limiti: ~1000 run per pipeline a settimana, 10 per 15 minuti | Non vincolanti per una schedulazione giornaliera |

**Criterio di selezione — correzione di merito.** Lo Sweep **non deve dipendere dal tracker** per
decidere. Il criterio primario è deterministico: nome conforme a `ws_<progetto>_feature_wi<id>` ed
età oltre TTL. La consultazione del work item resta un **filtro di sicurezza** che impedisce la
cancellazione di lavoro in corso, non il criterio di innesco. Così lo Sweep continua a funzionare
quando l'astrazione del tracker (RF-06) cambierà per GitHub, e non è il primo script a rompersi.

**Conseguenza positiva non prevista:** cade la nota negativa «lo scheduler è un secondo punto di
esecuzione oltre ai due dispatcher, con gli stessi limiti di disponibilità della macchina locale».
Lo scheduler è quello della piattaforma CI/CD: **funziona a macchina spenta**, che era uno dei
limiti dichiarati dell'opzione A di hosting in ADR-0005.

**Da fare, in aggiunta:** l'item di backlog dello Slice 1 diventa «pipeline `pipe_sched_sweep`»
e non «script `scripts/sweep`»; `03-rail-script.md` deve dichiarare che lo Sweep è l'unico dei
quattro rail **non invocabile da alcun agente**.
