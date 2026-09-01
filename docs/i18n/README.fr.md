# chamnan — pour qu'un dépôt se connaisse lui-même

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Cette page ne contient volontairement aucun chiffre. Toutes les mesures figurent dans le README anglais et changent à chaque version ; cette page, non. → [Evidence](../../README.md#evidence)

## Ce que c'est

Une extension pour Claude Code. Elle construit un index du dépôt que l'agent lit au lieu de parcourir les fichiers un à un, et conserve le contexte technique accumulé pendant le travail — l'état des travaux, les comptes rendus de session, les raisons derrière les décisions, et les procédures que l'on redéduit à chaque fois.

Tout ce qu'elle écrit est du markdown ordinaire, versionné à côté du code. Aucun appel réseau à l'exécution, pas de base de données, pas de démon, pas de modèle d'embedding — uniquement la bibliothèque standard de Python.

## Ce qu'elle résout

À chaque nouvelle session, et chaque fois que le contexte est compacté, tout ce que l'agent avait compris de votre code disparaît et il repart à la recherche depuis le début.

chamnan fait que cette redécouverte n'a pas lieu d'être : l'index est remis au démarrage de la session, et le coût est un nombre connu et borné plutôt qu'une lecture de fichiers sans limite.

## Installation

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Ouvrez une nouvelle session, puis lancez `/chamnan:bootstrap` une fois par dépôt.

## À lire avant d'installer

**chamnan s'adresse au dossier principal où vous revenez encore et encore.** Tout ce qu'il fait se paie d'avance et se récupère lors des sessions suivantes — sur un dépôt ouvert une seule fois, vous avez tout payé et rien récupéré.

**Il signale, il ne réécrit pas votre code.** L'index reprend les commentaires que vous avez déjà écrits et n'en invente aucun. Les fichiers sans commentaire sont nommés pour que vous les complétiez vous-même.

**Ses limites sont mesurées et écrites**, y compris les mesures qui vont à l'encontre de sa propre fonction principale.

## Où trouver le détail

| | |
|---|---|
| Chaque chiffre, et comment il a été mesuré | [README › Evidence](../../README.md#evidence) |
| Suite de tests de régression — à lancer vous-même | [`tests/run_tests.py`](../../tests/run_tests.py) |
| Ce qui a changé à chaque version, et pourquoi | [CHANGELOG.md](../../CHANGELOG.md) |
| Tout le reste | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
