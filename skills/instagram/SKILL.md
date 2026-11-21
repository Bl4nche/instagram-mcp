---
name: instagram
description: Analizza le performance organiche di un account Instagram (post, reel, storie, reach, follower, pubblico) con i tool del server MCP instagram, in sola lettura, e la cronologia locale degli snapshot. Usala quando l'utente chiede come vanno i contenuti Instagram, i post o reel migliori, l'andamento dei follower, le storie passate, il pubblico, o vuole salvare uno snapshot o verificare che il collegamento Instagram funzioni.
argument-hint: [domanda o periodo, es. "reel migliori del mese"]
---

# Instagram Insights

Richiesta: `$ARGUMENTS`

I dati arrivano dai tool del server MCP `instagram` di questo plugin. Il server **legge soltanto**: non pubblica, non commenta, non modifica nulla sull'account. Non proporre azioni che ne richiedano altre.

## 1. Controlla il collegamento

Chiama sempre per primo `get_profile` e scrivi su quale account stai lavorando (username e follower). Nella risposta finale ripeti l'account analizzato.

Se fallisce:

| Errore | Cosa dire all'utente |
|---|---|
| tool `instagram` non disponibili | Il plugin non è attivo o `uv` non è installato: vedi "Configurazione" sotto. |
| `IG_ACCESS_TOKEN is not set` | L'account non è ancora collegato: l'utente deve lanciare `uv run instagram-mcp setup` nel proprio terminale (vedi "Configurazione"). |
| `numeric Instagram account ID` | Manca l'ID dell'account: rilanciare `setup` e inserire il numero che inizia con 1784. |
| codice 190 / token scaduto | Con Instagram Login il token dura 60 giorni: `uv run instagram-mcp refresh-token`. Gli altri token non scadono: se non vanno più sono stati revocati, va generato un nuovo token e rilanciato `setup`. |
| codice 10 / 200 / permessi | Al token mancano permessi di insights (README, sezione 1). |

## Privacy

- Ogni utente collega **il proprio** account con il proprio token: non dare per scontato quale account sia, leggilo da `get_profile`.
- **Non chiedere mai il token in chat**, non leggere, stampare o modificare il file `.env` e non lanciare tu `setup` (chiede il token): l'utente lo lancia nel proprio terminale. Per verificare il collegamento usa `get_profile` o `uv run instagram-mcp check`, che non mostrano il token.
- Se l'utente incolla per errore un token in chat, digli di revocarlo e generarne uno nuovo.

## 2. Scegli i tool

| Domanda | Tool |
|---|---|
| Ultimi post e reel | `list_media` |
| Un contenuto nel dettaglio | `get_media_insights` (con l'`id` da `list_media`) |
| I migliori / peggiori | `top_posts` con `by` = `er_reach_pct`, `er_followers_pct`, `reach`, `views`, `saved`, `shares`… |
| Totali account (max 30 giorni) | `get_account_insights` |
| Pubblico | `get_audience` con `breakdown` = `age`, `gender`, `city`, `country` (servono almeno 100 follower) |
| Storie delle ultime 24 ore | `get_active_stories` |
| Storie più vecchie | `story_archive` (solo quelle salvate dagli snapshot) |
| Crescita follower nel tempo | `follower_history` |
| Come è cresciuto un post | `media_metric_history` |
| Salvare lo stato attuale | `snapshot` |

`top_posts` e `get_media_insights` fanno una chiamata API per contenuto: tieni `limit` basso (25) se non serve di più.

## 3. Leggi i numeri con onestà

- **Engagement rate**: `er_reach_pct` = interazioni / reach (qualità del contenuto); `er_followers_pct` = interazioni / follower (benchmark di settore). Indica sempre quale stai usando.
- Oltre 30 giorni l'API non dà totali: usa la cronologia locale e di' da quando parte (primo snapshot). Se la cronologia è vuota, dillo e suggerisci di pianificare gli snapshot (README, sezione 4) invece di stimare.
- Le storie spariscono dall'API dopo 24 ore: ciò che non è in `story_archive` non è recuperabile.
- Meta rinomina le metriche (`impressions` → `views` nel 2025): se una metrica manca, è stata saltata, non è zero.
- Confronta contenuti dello stesso tipo (reel con reel, carosello con carosello) e segnala quando il campione è piccolo.
- Non inventare cause di un calo che i dati non mostrano.

## 4. Rispondi

Apri con la risposta alla domanda in 2-3 righe, poi una tabella con i numeri (contenuto con link `permalink`, data, metriche) e chiudi con al massimo tre osservazioni pratiche. Date in formato italiano.

## Configurazione (se il collegamento manca)

1. Installa [uv](https://docs.astral.sh/uv/).
2. Crea la propria app Meta e il token seguendo `${CLAUDE_PLUGIN_ROOT}/README.md`, sezione 1. Ogni persona usa la propria app e il proprio account; per le app nuove (accesso unificato) il token non scade.
3. Nel proprio terminale: `uv run --directory "${CLAUDE_PLUGIN_ROOT}" instagram-mcp setup`. Chiede tipo di accesso, ID account e token (nascosto), li verifica con Meta e li salva in `~/.instagram-mcp/.env`, privato e fuori dal plugin. Lì viene salvata anche la cronologia.
4. Riavvia Claude e verifica con `get_profile`.

Il server lavora su **un account per volta**: per cambiarlo si rilancia `setup`.
