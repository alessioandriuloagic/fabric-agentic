# ADR-0014 — Innesco dell'Issue Agent e cancello umano prima del work item

| Campo | Valore |
|---|---|
| Stato | Accettata |
| Data | 2026-08-31 |
| Contesto | Catena `Issue Agent` -> approvazione umana -> ticket -> `Dev Agent` -> PR -> `Review Agent` |

## Contesto

Dev Agent e Review Agent hanno un innesco deterministico: un work item etichettato per il primo,
una pull request aperta e non ancora revisionata per il secondo. L'Issue Agent invece veniva
avviato solo a mano dall'owner con il prompt `define-work`. La catena documentata in `AGENTS.md`
partiva quindi da un passo non tracciabile: non esisteva una coda, non esisteva un record di quando
un pacchetto era stato prodotto, e l'esito viveva nella sessione invece che nel tracker.

Il vincolo non negoziabile è che l'Issue Agent **non crea work item senza approvazione umana**.
Un innesco automatico non deve trasformarsi in creazione automatica di backlog.

## Decisione

1. L'innesco è una **issue di intake** etichettata `issue-agent`, aperta e senza pacchetto già
   pubblicato. È la coda esplicita, come il tag lo è per il Dev Agent.
2. Un dispatcher deterministico, `scripts/issue_dispatcher.py`, rileva le intake, avvia una sessione
   nuova e senza memoria nella clone dedicata, e attende l'esito.
3. Il pacchetto è pubblicato da un **rail deterministico**, `scripts/issue_package_publish.py`, non
   dal modello. Il rail valida la struttura del pacchetto e pubblica **un solo commento**.
4. Il pacchetto è una **proposta**, non un backlog: il rail non crea, non modifica e non chiude
   alcun work item.
5. Il cancello umano resta esplicito. L'owner legge il pacchetto e, se lo approva, applica
   l'etichetta `dev-agent` sul ticket risultante. Solo allora il Dev Agent lo vede.
6. L'Issue Agent ha una **GitHub App dedicata**, distinta da quella del Dev Agent e del Review
   Agent, con i soli permessi necessari a leggere il repository e commentare le issue.

## Alternative scartate

| Alternativa | Motivo del rifiuto |
|---|---|
| Lasciarlo manuale per scelta | Il passo iniziale della catena resterebbe fuori dal tracker: nessuna coda, nessuna evidenza, nessuna misura del lead time |
| Far creare i ticket direttamente all'agente | Violerebbe il vincolo di approvazione umana e produrrebbe backlog non revisionato |
| Riusare l'identità del Dev Agent | Chi propone il lavoro coinciderebbe con chi lo implementa e l'audit non distinguerebbe le due fasi |
| Far pubblicare il pacchetto al modello | Metterebbe una credenziale di scrittura nel runtime del modello, come già rifiutato in ADR-0013 |

## Conseguenze

- La catena diventa tracciabile dall'inizio: intake, pacchetto, approvazione, ticket.
- L'approvazione umana resta l'unico passaggio che trasforma una proposta in lavoro.
- Il modello non detiene mai il token: il confine è strutturale, non dichiarato.
- Serve un terzo runtime e una terza identità da mantenere: è il costo accettato per rendere
  osservabile il primo passo della catena.
- Finché il runtime non è indipendente, l'Issue Agent resta un controllo assistito, non un
  controllo di produzione.
