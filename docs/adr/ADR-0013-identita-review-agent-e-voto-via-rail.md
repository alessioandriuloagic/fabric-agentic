# ADR-0013 — Identità GitHub del Review Agent e pubblicazione del voto via rail

| Campo | Valore |
|---|---|
| Stato | Accettata |
| Data | 2026-08-27 |
| Contesto | Work item #96, #97 |

## Contesto

Il Review Agent produceva l'esito A1-F4 corretto, ma il voto non entrava mai nel record di GitHub:
la sessione chiamava l'API con l'identità umana, che è anche l'autore della pull request. GitHub
rifiutava la submission con `Review Can not request changes on your own pull request`, osservato su
PR #94 e su PR #95 in tre iterazioni. L'esito viveva solo come commento e non aveva peso.

## Decisione

1. Il Review Agent ha una **GitHub App dedicata**, distinta da quella del Dev Agent, installata sul
   solo repository della soluzione.
2. I permessi dell'installazione sono `metadata:read`, `contents:read`, `issues:read` e
   `pull_requests:write`. `contents:read` nega push e merge: votare non richiede scrittura sul codice.
3. Il voto è pubblicato da un **rail deterministico**, `scripts/review_vote_publish.py`, non dal
   modello. La sessione emette l'esito; il rail conia l'installation token e invia una sola review.
4. Il publisher rifiuta di eseguire se la copia non è allineata a `main`.

## Alternative scartate

| Alternativa | Motivo del rifiuto |
|---|---|
| Riusare la GitHub App del Dev Agent | Chi implementa voterebbe sul proprio lavoro; l'audit non distinguerebbe più implementazione e giudizio, e i permessi si sommerebbero al massimo comune |
| Machine user con PAT | Segreto a vita lunga, revoca manuale, identità di forma umana che confonde l'audit |
| `GITHUB_TOKEN` di un workflow | Attribuirebbe il voto a un'identità di CI condivisa con il perimetro di deploy |
| Installation token iniettato nella sessione | Metterebbe una credenziale con `pull_requests:write` nel runtime del modello, garantendo il confine con la sola prosa |

## Conseguenze

- Il modello non detiene mai il token: il vincolo «il Review Agent non accede alle credenziali»
  diventa strutturale invece che dichiarato.
- Commento e voto sono un'unica submission atomica.
- L'ancoraggio a `main` impedisce che il Dev Agent, che ha scrittura sui branch, riscriva il
  publisher sulla propria pull request e si autoapprovi. È l'escalation che non passa dai permessi
  ma dal codice, descritta in `docs/technical/04-identita-e-permessi.md` sezione 3.3.

## Limiti accettati

- `pull_requests:write` è la granularità minima offerta da GitHub e porta capacità residue —
  chiudere o riaprire una pull request, gestire label, richiedere revisori. Non sono eliminabili via
  permessi e restano contenute dalle sole istruzioni.
- Sul piano GitHub corrente `CHANGES_REQUESTED` **non** blocca tecnicamente il merge. Il controllo è
  attribuibile e auditabile, non bloccante; il blocco resta processuale, come da ADR-0010 e S0-06.
- La private key di review risiede sullo stesso utente Windows del Dev Agent. È custodia, non
  isolamento: la separazione reale richiede un utente di sistema o un host distinto.
