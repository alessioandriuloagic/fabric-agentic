# Distinguere motore Issue Agent

**Date**: 2026-09-04 | **Context**: Issue Agent in VS Code/chat versus dispatcher

## What happened
Ho scritto che l'Issue dispatcher resta acceso anche quando si usa l'Issue Agent in chat, senza distinguere quale motore esegue quel singolo pacchetto.

## Why it was wrong
La sessione VS Code/chat usa il runtime Copilot, mentre il dispatcher usa il comando configurato in `claude_command`; per lo stesso intake manuale non girano entrambi i motori.

## What to do instead
Documentare il modo ibrido: Copilot/VS Code prepara il pacchetto ricco, poi Dev e Review possono proseguire via dispatcher. Tenere acceso anche Issue ha senso per intake automatici futuri o pubblicazione automatica, non per rieseguire lo stesso pacchetto manuale.