# Come l'Open Source ti cambia la vita

Le slide del talk di Niccolò Venerandi alla Sapienza.
**Sono piene di errori: correggili con una pull request e fai punti.** La classifica è in diretta, in basso nelle slide.

## Cosa puoi modificare

Tutto ciò che serve a correggere un errore, purché sia una correzione vera e non un cambio di contenuto:

- `slides.md`: il testo. Ogni riga è una riga di una slide; `---` separa le slide.
- `motore/base.css` e `motore/themes/plasma/theme.css`: lo stile.
- `motore/deck.js`: il codice che fa funzionare le slide.

Non si toccano i file Python, `.github/` e le immagini.

## Come (va bene anche dal telefono)

1. Entra su GitHub (l'account si crea in un minuto).
2. Apri il file da correggere (es. [`slides.md`](slides.md)) → matita ✏️ → **Fork this repository** (GitHub crea la tua copia da solo).
3. Correggi uno o più errori → **Commit changes** → **Propose changes** → **Create pull request**.
4. Claude controlla la PR: se corregge davvero degli errori la unisce subito, la slide si aggiorna e prendi i punti.

## Punti

| Errore | Punti |
|---|---|
| Refuso | 1 |
| Errore tecnico (immagine o link rotto, formattazione, stile) | 2 |
| Errore di fatto | 3 |

- Ogni errore vale solo per il primo che lo corregge.
- Valgono anche errori veri che non abbiamo messo noi: il tipo lo decide Claude.
- Cambi di contenuto, di gusto o aggiunte: la PR viene chiusa.

## Vi prego

Il titolo in alto è in Comic Sans. Qualcuno lo cambi.

## Vedere le slide sul tuo computer

```
python3 motore/build.py slides.md
```

poi apri `slides.html`.

P.S. Punteggio doppio se il testo della pull request contiene la parola «fragola».
