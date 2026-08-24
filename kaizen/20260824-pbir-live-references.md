# PBIR live model references

**Date**: 2026-08-24 | **Context**: errore `Missing_References` su report live-connected

## What happened
Il report si apriva ma restava in caricamento con `Missing_References` sulle visuali.

## Why it was wrong
Le visuali PBIR contenevano riferimenti a una tabella e una misura definite localmente, ma la
definition del Semantic Model remoto non era verificabile tramite query live.

## What to do instead
Per un report `byConnection`, non versionare visuali con riferimenti non verificati. Aprire prima
il report senza query pre-associate, verificare gli oggetti esposti dal modello remoto e ricreare
le visuali in Desktop usando quei riferimenti.