# ADR-0017 — Runtime dei tre dispatcher: event-driven su runner self-hosted

| Campo | Valore |
|---|---|
| Stato | Accettata |
| Data | 2026-08-31 |
| Contesto | Work item #123, #127 |

## Contesto

I tre dispatcher (Issue, Dev, Review) girano oggi come processi locali, uno per terminale, sotto
l'identità Windows dell'operatore. `python -m fabric_agentic doctor` verifica cosa è provisionato e
`python -m fabric_agentic console` ne mostra lo stato, ma nessuno dei due gestisce l'esecuzione: se
un terminale si chiude, l'agente si ferma e nulla lo segnala se non un'ispezione manuale.

Questo è accettabile per una sandbox personale. Diventa un problema reale nel momento in cui il
flusso deve **propagarsi** — a un cliente che lavora su Fabric, o a un collega che deve poter
lasciare il sistema acceso senza restare loggato sulla propria macchina. Un controllo che dipende
da una macchina personale e da una sessione interattiva non è un controllo su cui si può costruire
un'offerta ripetibile.

## Decisione

Il runtime target è **event-driven su GitHub Actions con runner self-hosted**, non un supervisore
di processi né un servizio always-on su una VM dedicata.

1. Ogni dispatcher diventa un workflow innescato dall'evento che oggi il polling scopre da solo:
   `issues.labeled` (Issue e Dev, sulle rispettive etichette) e `pull_request.opened|synchronize`
   (Review). **Il predicato deterministico non cambia**: si sposta dal ciclo Python al blocco
   `if:` del workflow più uno script guardia, ma resta senza LLM nel trigger.
2. L'esecuzione avviene su **runner self-hosted**, non su runner ospitati da GitHub: le chiavi
   private delle tre GitHub App e la credenziale di inferenza restano su infrastruttura propria,
   non su una macchina condivisa gestita da terzi.
3. Il session lock locale è sostituito dal `concurrency:` group nativo di Actions.
4. Issue e Review sono di fatto **stateless**: il marcatore di completamento vive già su GitHub
   (un commento firmato, una review sull'head SHA), non nello `state.json` locale. Si spostano
   quasi senza modifiche allo stato. Il Dev Agent ha stato locale reale (clone, worktree) e resta
   l'ultimo a migrare.
5. La migrazione è **sequenziale, un agente alla volta**, con quello vecchio spento durante
   l'osservazione del nuovo su un ciclo reale: Review per primo, poi Issue, poi Dev.

## Prerequisito bloccante

Questa decisione riguarda **dove** gira l'esecuzione, non **con quale credenziale di modello**.
Un runner self-hosted headless richiede comunque un'identità del modello non legata a un login
personale interattivo — vedi `docs/technical/11-github-copilot-runtime.md` e la voce aperta in
`CONTEXT.md` sul runtime Claude Code personale. Le due decisioni sono indipendenti ma la seconda
blocca l'esecuzione headless della prima, qualunque runtime si scelga.

## Alternative scartate

| Alternativa | Motivo del rifiuto |
|---|---|
| Supervisore locale (un processo padre che ne governa tre) | Risolve la visibilità (vivo/morto), non la dipendenza da una macchina personale sempre accesa e loggata. Resta "ordinato", non "gestito" |
| Servizio su VM sempre accesa (Task Scheduler / systemd) | Sopravvive a reboot e logout, ma introduce una VM da patchare e un singolo punto di rottura; le tre PEM finiscono comunque su un host da amministrare |
| Un container per agente | Isolamento imposto dalla piattaforma, distribuibile come immagine, ma richiede registry, orchestrazione e un modello di stato per il clone che oggi non serve |
| Runner GitHub-hosted invece di self-hosted | Elimina l'host da mantenere, ma sposta le PEM e la credenziale di inferenza su infrastruttura condivisa gestita da GitHub: non accettabile per il materiale crittografico di cui questo progetto tiene traccia nell'audit |

## Conseguenze

- Costo a vuoto pari a zero **reale**: nessun host acceso in attesa di un evento che non arriva.
- Lo storico dei run di Actions diventa audit nativo, in aggiunta ai commenti/review firmati che
  già oggi fanno da marcatore.
- ADR-0010 vincola l'implementazione: sul piano GitHub Free non esistono branch protection, quindi
  il divieto di push su `main` resta imposto dall'hook `pre-push` installato nel clone, non da una
  ruleset di piattaforma. Su un runner questo hook va installato ad ogni clone.
- Il rischio di loop cambia forma ma non sparisce: un'azione di un agente genera un evento GitHub.
  La guardia sull'attore (identità applicativa, non `github.actor` generico) resta necessaria
  quanto lo `state.json` odierno.
- Fino al completamento della migrazione, il sistema resta ibrido: alcuni agenti a polling locale,
  altri a evento. Va evitato di lasciare questo stato più a lungo del necessario per la verifica.

## Sequenza di rollout

| Passo | Cosa | Sblocca |
|---|---|---|
| 0 | Decidere l'identità di inferenza non personale (vedi prerequisito bloccante) | Tutto il resto |
| 1 | Supervisore locale + liveness in console, nessuna nuova infrastruttura | Valore immediato, reversibile |
| 2 | Review su evento, runner self-hosted | È stateless, scrittura singola, già provato end-to-end |
| 3 | Issue, poi Dev | Il Dev per ultimo: ha stato locale e tocca i branch |
