# ADR-0015 — Pacchetto riutilizzabile alla radice invece del layout `src/`

| Campo | Valore |
|---|---|
| Stato | Accettata |
| Data | 2026-08-31 |
| Contesto | Work item #123, #125 |

## Contesto

Il repository conteneva insieme framework riutilizzabile, deployment di riferimento e script
operativi, tutti sotto `scripts/`. Per distribuire il kit a colleghi e a nuovi progetti serve un
confine esplicito fra il core riutilizzabile e ciò che appartiene alla singola istanza.

Il vincolo pratico è la catena di verifica: il workflow `validate-rail-contract` esegue i test
**senza alcuno step di installazione**, e gli script vengono lanciati come `python -m scripts.x`
dalla radice del repository. Anche i colleghi devono poter clonare ed eseguire senza build.

## Decisione

1. Il core riutilizzabile vive in un pacchetto `fabric_agentic/` **alla radice**, importabile
   subito dopo il clone, senza installazione e senza manipolare `sys.path`.
2. `scripts/` resta il perimetro **operativo**: dispatcher, rail e publisher. Può importare il
   core; il core non importa mai `scripts`, e un test lo verifica.
3. `pyproject.toml` dichiara il pacchetto per l'installazione e il versionamento, ma
   l'installazione resta facoltativa.
4. Gli entry point documentati mantengono un wrapper retrocompatibile in `scripts/`, così i runbook
   esistenti continuano a funzionare.

## Alternative scartate

| Alternativa | Motivo del rifiuto |
|---|---|
| Layout `src/fabric_agentic/` | Non importabile senza installazione: richiederebbe uno step `pip install -e .` in CI e un build prima di ogni esecuzione locale, contro l'obiettivo di configurazione rapida |
| Lasciare tutto in `scripts/` | Nessun confine fra capacità riutilizzabile e istanza: è il problema che il kit deve risolvere |
| Repository separato per il core | Costo di sincronizzazione e versionamento prima che il riuso sia dimostrato |

## Conseguenze

- Il confine core/operativo diventa verificabile, non solo dichiarato.
- La CI resta senza dipendenze installate.
- Il pacchetto è versionabile e distribuibile quando servirà.
- Si rinuncia alla protezione del layout `src/` contro l'import accidentale della working directory:
  è un compromesso accettato in cambio dell'esecuzione immediata dopo il clone.
