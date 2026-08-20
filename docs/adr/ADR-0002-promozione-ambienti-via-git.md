# ADR-0002 — Promozione degli ambienti via Git anziché Deployment Pipelines

| Campo | Valore |
|---|---|
| Stato | **SUPERATO da [ADR-0007](ADR-0007-pipeline-cicd-come-rail.md)** (2026-08-20b) |
| Data | 2026-08-20 · superato il 2026-08-20b |
| Autore | Ralph (Fabric Solution Architect) |
| Contesto originato da | `docs/technical/07-architecture-review.md` §3 |
| Decisori | Owner · @marco (Power BI) · @reza (Data Engineering) |

---

> ## ⚠ Questo ADR è superato
>
> Dopo la sua stesura è emerso che esiste già un asset di deploy Fabric funzionante
> (`IP.dai_fabric_environments`) e l'owner ha deciso che **i deploy passano dalle pipeline CI/CD
> esistenti** (Azure DevOps Pipelines e GitHub Actions). Vedi
> `docs/technical/07-architecture-review.md` §13.
>
> **Cosa resta valido di questo ADR:**
> - il rifiuto delle **Fabric Deployment Pipelines** (incompatibilità con PBIR, assenza di traccia
>   in Git): confermato e rafforzato;
> - i **tre ambienti** `dev` / `test` / `prod`;
> - **Variable Library** come punto unico di parametrizzazione — ma affiancata dalla
>   configurazione per istanza in `config/<istanza>/`, che è il pattern dell'asset;
> - il divieto di deploy per gli agenti imposto dall'**assenza di ruolo** su `test` e `prod`.
>
> **Cosa è superato:** la promozione come *update from Git* eseguito manualmente da un umano
> nell'interfaccia Fabric. La promozione è ora eseguita da una **pipeline CI/CD**, innescata da un
> umano e protetta da approvazione di environment. Git resta la sorgente di verità; cambia chi
> applica il commit al workspace.
>
> **Attenzione — verifica non fatta:** ADR-0002 nasceva dall'incompatibilità PBIR delle Deployment
> Pipelines. Che il nuovo canale (fabric-cicd) supporti PBIR **non è verificato** ed è uno spike
> obbligatorio di S1-01. Cambiare canale non risolve automaticamente il problema che ha motivato
> il cambio.

---

## Contesto

Il design descrive due workspace di ambiente (`ws_agentic_dev`, `ws_agentic_prod`), ammette un
terzo ambiente `test` in `CONTEXT.md` §3.2 che nessun documento crea, e stabilisce che il deploy
verso test e produzione sia un'azione **esclusivamente umana** (RF-72, NO-1). **Nessun documento
dichiara però attraverso quale meccanismo la promozione avvenga.**

Microsoft Fabric offre due canali: **Deployment Pipelines** e **Git integration**. La scelta non è
neutra rispetto a una decisione già presa dal progetto.

Fatti verificati su documentazione ufficiale Microsoft (2026-08-20):

- `CONTEXT.md` §6 impone il formato **PBIR/TMDL** e vieta il `.pbix` binario nel repo (RF-40).
- Le Deployment Pipelines dichiarano tra le limitazioni generali: **«PBIR reports aren't
  supported»**.
- Un semantic model **Direct Lake** promosso con Deployment Pipelines **non si ri-aggancia** al
  lakehouse dello stage di destinazione: resta legato a quello di origine, salvo *datasource rules*.
- Le Deployment Pipelines copiano metadati tra workspace: **non lasciano traccia in Git** di cosa
  sia effettivamente in produzione.
- Un workspace Fabric può essere connesso a **un solo branch**; il pattern documentato per lo
  sviluppo isolato è il *branched workspace*, che il design già adotta correttamente.
- **Variable Library** è item supportato sia da Git integration sia da Deployment Pipelines.

## Decisione

**1. La topologia degli ambienti comprende tre workspace**: `ws_agentic_dev`, `ws_agentic_test`,
`ws_agentic_prod`. `ws_agentic_test` viene creato nello Slice 1 insieme agli altri due, anche se
inizialmente vuoto.

**2. La promozione tra ambienti avviene tramite Git integration**, non tramite Deployment Pipelines:

```
                    main ──────────────► ws_agentic_dev            (sync)
                      │
                      ├── branch/tag di release ──► ws_agentic_test   (update from Git, umano)
                      └── branch/tag di release ──► ws_agentic_prod   (update from Git, umano)

feature/wi-<id> ─────────────────────────► ws_agentic_feature_wi<id>  (effimero)
```

**3. La parametrizzazione per ambiente** (identificativi di lakehouse, connessioni, path) è
realizzata con **Variable Library**, che diventa il punto unico previsto da RF-80 e da
`05-struttura-repository.md` §5. Il prefisso di naming va aggiunto a `CONTEXT.md` §3.1.

**4. Il divieto di deploy per gli agenti** (RF-72) è imposto dall'**assenza di qualunque ruolo**
del service principal del Dev Agent su `ws_agentic_test` e `ws_agentic_prod`, ed è verificato
praticamente al bootstrap.

## Alternative considerate

| Alternativa | Perché scartata |
|---|---|
| **Deployment Pipelines** | Incompatibile con PBIR, che è una decisione già presa e più importante: il versionamento testuale dei report è un requisito, il canale di promozione è un mezzo. Inoltre non lascia in Git l'evidenza di cosa sia in produzione |
| **Modello ibrido**: Git per la lane dati, Deployment Pipelines per la lane Power BI | Due meccanismi di promozione, due modi di sbagliare, e la lane Power BI è proprio quella colpita dal limite PBIR |
| **Rinunciare a PBIR** per poter usare le Deployment Pipelines | Rinuncerebbe al versionamento leggibile dei report, cioè a una delle due ragioni per cui la lane Power BI esiste (RF-43: validazione strutturale del PBIR) |
| **Due soli ambienti (dev/prod)** | Coerente e più economico, ma indebolisce l'asset come demo commerciale (OB-4): una catena CI/CD senza ambiente di test è difficile da presentare a un cliente enterprise. Il costo marginale di un workspace vuoto è trascurabile |

## Conseguenze

**Positive**
- Ciò che è in produzione è **un commit identificabile**, non il risultato di una copia opaca.
- Compatibilità piena con PBIR e TMDL.
- Un solo meccanismo di promozione da imparare, documentare e presidiare.
- Il divieto di deploy diventa imponibile con un controllo semplice e verificabile (assenza di ruolo).

**Negative**
- Si perde la comodità delle *deployment rules*: la parametrizzazione va progettata a mano con
  Variable Library, e va progettata **prima** del primo item che ne dipende.
- La promozione è un'operazione manuale di *update from Git* sul workspace di destinazione: va
  scritto un runbook, perché un'operazione umana non documentata è un'operazione che verrà fatta
  in modi diversi.
- I semantic model **Direct Lake** richiedono comunque un ri-aggancio esplicito al lakehouse
  dell'ambiente di destinazione: il problema non sparisce cambiando canale, cambia solo forma.

**Da fare**
- Aggiornare `CONTEXT.md` §3.1 (prefisso Variable Library) e §3.2 (tre ambienti effettivi).
- Aggiornare il ticket S1-04 del backlog: tre workspace anziché due.
- Scrivere il runbook di promozione in `docs/functional/`.
- Aggiornare il PRD §6.1 e RF-72.
