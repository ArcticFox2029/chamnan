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

<!-- generated: build_sections.py -->

## Toutes les fonctionnalités

Quatre capacités. Tout ce qui figure ci-dessous tourne réellement dans la version actuelle. Chaque partie se désactive séparément dans `.chamnan/config.json`, et aucune ne dépend d'une autre.

### Comprendre — ce qui existe, et ce qui est relié à quoi

| | |
|---|---|
| **Index** | `MAP.md` — une ligne par fichier, engendrée depuis le code lui-même. L'agent lit l'index puis fait un grep sur le détail voulu, au lieu de parcourir l'arborescence. |
| **Impact** | Qui dépend de ce fichier, et quels tests le couvrent. Ses propres imports sont déjà en tête du fichier ; ce qui coûte cher, c'est l'arête inverse — greppez le chemin avant de modifier. |
| **Modèle de données** | Noms de tables et de modèles avec une ligne de description, tirés du DDL, des migrations et des modèles ORM — et non un vidage complet du schéma. N'apparaît que si le dépôt en définit un. |
| **Surface d'API** | Méthode, chemin et gestionnaire, depuis les décorateurs de routes, les documents OpenAPI et les définitions de service `.proto` — pas la spécification entière. |
| **Configuration** | Les noms des variables d'environnement que le dépôt lit. **Les noms seulement, jamais les valeurs** — et il avertit si `.env` n'est pas dans gitignore. |
| **Déploiement** | Ce qui tourne vraiment, lu depuis les manifestes Kubernetes, Ansible, Compose, Helm et CI : types et noms, images, rôles, pipelines. D'un Secret il ne prend que le nom, rien de ce qu'il contient. |
| **Matériel non source** | Documents numérisés, exports, archives — seulement des comptes, des tailles et les extensions dominantes. Cette section existe pour que l'agent n'aille pas voir lui-même, ce qui coûterait bien plus. **Jamais ouvert, jamais lu.** |

### Se souvenir — ce qui était en cours, et pourquoi

| | |
|---|---|
| **État du travail** | `STATE.md` — ce sur quoi on travaille à l'instant ; injecté au démarrage de la session pour que la compaction du contexte cesse de l'effacer. |
| **Compte rendu de session** | Un par session sous `.chamnan/sessions/`. **Seul l'inachevé** parvient à la session suivante ; une session close proprement n'injecte rien du tout. |
| **Mémoire** | `decisions/`, `lessons/`, `rules/`. Les règles sont des contraintes permanentes : elles sont devant l'agent à chaque session. Décisions et leçons ne fournissent qu'un titre, et sont lues quand le titre paraît pertinent. |
| **Fils ouverts** | Les lignes de travail non closes, avec l'historique des fichiers que ce fil a touchés — et elles continuent de le suivre après un renommage. |

### Réemployer — ce qui a déjà été résolu

| | |
|---|---|
| **Procédures** | Des compétences que l'agent écrit **lui-même** quand il rencontre quelque chose de complexe ou de répété. Non pas une bibliothèque livrée, mais un mécanisme. |
| **Outils** | Remarque que le même script jetable vient d'être réécrit et propose de le garder — puis le rappelle avant que vous n'en écriviez un nouveau. |
| **Enchaînements** | Remarque que les mêmes commandes se sont suivies dans le même ordre des jours distincts, et propose de consigner la séquence. |

### S'enrichir — ce que le dépôt a appris sur lui-même

| | |
|---|---|
| **Jalons** | Les rares changements qui ont remodelé le dépôt : ce qui a bougé, pourquoi cela valait la peine, quels domaines cela a touchés. |
| **Candidats** | Les séquences de commandes répétées détectées attendent **toujours une confirmation humaine**. Rien n'est promu automatiquement. |
| **Environnements** | Déclarez ce qu'est production ou staging et ce qui y est interdit — il vous avertira quand cette déclaration vieillira. |
| **Rapport** | Ce que contient l'espace de travail, s'il est réellement atteignable, et comment le contexte par tour a évolué dans votre dépôt. Votre chiffre, pas le nôtre. |

Un travail d'ingénierie répété devient une connaissance de dépôt réutilisable — **ce n'est ni l'entraînement d'un modèle, ni l'automatisation du développeur.** C'est un moyen de conserver un travail qui, sinon, n'existerait que dans la tête de celui qui l'a fait.

## Commandes

Toutes appelables depuis le shell, et l'agent les appelle aussi de lui-même.

| | |
|---|---|
| `chamnan-map` | construit et met à jour l'index |
| `chamnan-report` | ce que contient l'espace de travail, et comment le contexte par tour a évolué |
| `chamnan-impact` | qui dépend de ce fichier, et quels tests le couvrent |
| `chamnan-timeline` | ce qui est déjà arrivé à ce fichier |
| `chamnan-peek` | dit ce qu'il y a dans un gros fichier sans le lire dans le contexte |
| `chamnan-promote` | conserve un script comme outil permanent du dépôt |
| `chamnan-candidates` | voir, confirmer ou écarter les répétitions détectées |
| `chamnan-env` | déclarer un environnement et ses interdits, et vérifier que la déclaration est encore fraîche |
| `chamnan-age` | où la connaissance stockée a commencé à vieillir |

Et les compétences appelées depuis la session : `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## Ce qu'il écrit, et où

Tout dans `.chamnan/`, du markdown et du JSON ordinaires. Lisible, modifiable à la main, supprimable à tout moment sans rien casser.

| | |
|---|---|
| `MAP.md` | ce qui existe, et ce qui dépend de quoi |
| `STATE.md` | ce sur quoi on travaille à l'instant |
| `sessions/` | où le travail précédent s'est arrêté |
| `memory/` | décisions, leçons et règles permanentes |
| `threads/` | les lignes de travail encore ouvertes |
| `skills/` · `tools/` | procédures et scripts qui méritent d'être gardés |
| `milestones.md` | les changements qui ont remodelé le dépôt |
| `config.json` | l'activation de chaque partie, et le plafond en octets du bloc injecté dans la session |

**La seule écriture hors de `.chamnan/`** est un hook Git pre-commit facultatif qui tient l'index au pas de l'arborescence — installé seulement si vous acceptez, et retirable.

**L'agent n'apprend pas.** Rien n'est entraîné, rien ne subsiste hors de ce dossier, et la session suivante repart de zéro — simplement de zéro *dans un dépôt qui s'explique lui-même*. La continuité est dans les artefacts, pas dans le modèle.

## Sûreté

| | |
|---|---|
| **Aucun appel réseau à l'exécution** | Pas un seul. Aucune clé d'API n'est requise, rien n'est envoyé nulle part. |
| **Ne réécrit pas votre code** | Il rapporte, il ne modifie pas. L'index copie les commentaires que vous avez déjà écrits, il ne les invente pas ; les fichiers sans commentaire sont nommés pour que vous les complétiez. |
| **Ni démon, ni travail de fond** | Aucun processus résident, aucune base de données, aucun modèle d'embedding — seulement la bibliothèque standard de Python. |
| **Les secrets sont filtrés d'abord** | Tout ce qui sera écrit ou injecté dans la session passe d'abord par le filtre de secrets : les *noms* de variables restent, les valeurs non. Et la limite que ce filtre n'atteint pas est écrite à côté de son propre chiffre dans le README anglais. |
| **Ce qu'un plugin installé peut vous faire** | Expliqué en entier dans le README anglais, y compris l'endroit où chamnan rompt la chaîne d'exfiltration. |

## Ce avec quoi il fonctionne

chamnan, c'est du texte et du Python de bibliothèque standard. Rien dans l'index n'appartient à un éditeur, à un fournisseur ni à un système d'exploitation particulier.

| | |
|---|---|
| **N'importe quel modèle, n'importe quel fournisseur** | L'index est du texte brut, envoyé comme contexte. Le modèle ne change que la quantité qu'il vaut la peine d'envoyer, jamais l'endroit où va quoi que ce soit. On règle la taille avec `--model`, `--window` ou `--profile`. Changer de modèle n'oblige à réinstaller quoi que ce soit. `--model` reconnaît ces familles par leur nom : `claude` · `codestral` · `deepseek` · `fable` · `gemini` · `gemma` · `glm` · `gpt` · `grok` · `haiku` · `kimi` · `mistral` · `openai` · `opus` · `sonnet` — la comparaison ignore la casse, les séparateurs et les numéros de version. `llama` et `qwen` en sont volontairement absents : tous deux existent en plusieurs tailles qui réclament des budgets différents, donc les nommer renvoie le profil par défaut et une ligne indiquant les deux tailles possibles. **Un modèle absent de la liste fonctionne quand même** : il obtient le profil par défaut et une note disant qu'il n'a pas été reconnu, et rien n'échoue. `--window` prend le nombre directement et reste toujours exact. |
| **macOS, Linux, Windows, WSL** | Le même plugin partout, bibliothèque standard uniquement, rien à installer. Sur macOS et Linux les commandes s'exécutent directement. Sur Windows, l'interpréteur ne sait pas lancer un script sans extension : un `.cmd` généré est donc posé à côté de chaque commande et de chaque hook. Ils sont livrés avec le plugin et la CI les exécute vraiment. WSL se comporte comme Linux. |
| **Plusieurs agents, un seul index** | Claude Code le reçoit par un hook de session et aucun fichier n'est écrit dans votre projet. Gemini CLI dispose lui aussi d'un vrai hook de session. Les autres agents reçoivent un fichier à l'emplacement qu'ils lisent, et ceux qui lisent le même emplacement partagent le fichier plutôt que d'en garder chacun une copie qui dérive. |
| **Hermes Agent** | Hermes est aussi un plan de contrôle qui pilote d'autres agents de code : un dépôt configuré pour lui signifie souvent plusieurs outils lisant le même index. Il cherche les instructions du projet dans un ordre fixe et prend la première trouvée ; chamnan écrit le fichier en tête de cet ordre, le dimensionne selon la limite que Hermes documente, et refuse d'écraser un fichier qu'il n'a pas écrit. |

## Comment l'installer

La voie d'entrée dépend uniquement de la présence ou non d'un hook de session dans l'outil.

| | |
|---|---|
| **Claude Code** | Installez-le comme plugin et lancez une fois la commande d'amorçage dans un dépôt. Rien n'est écrit dans votre code, et ensuite chaque session démarre avec l'index déjà en contexte. |
| **Tout le reste, Hermes compris** | Demandez d'abord ce que chamnan détecte, puis indiquez pour quel agent écrire. Quand la forme du dépôt change, reconstruisez l'index et réécrivez le fichier ; un hook Git facultatif fait les deux au commit. Claude Code n'est pas nécessaire : ce sont des commandes ordinaires et le plugin n'est qu'une voie de livraison, pas le produit. Sans agent nommé, il affiche ce qu'il a détecté et la commande qui conviendrait, et vous laisse décider. Il n'écrit jamais sur une supposition. |

Les noms des commandes, la liste complète des agents et le fichier reçu par chacun se trouvent dans le README en anglais, où résident tous les détails liés à une version.


## Prérequis

Claude Code · Python · Git · macOS, Linux ou Windows

Rien d'autre, et aucune dépendance à installer. La version minimale de Python est dans [README › Requirements](../../README.md#requirements) — cette page ne porte pas de chiffres, car ce sont les chiffres qui changent.

## Désactiver ou retirer

Désactivez par parties dans `.chamnan/config.json` · arrêtez-le dans un seul dépôt · retirez le plugin de toute la machine · supprimez `.chamnan/` quand vous voulez, rien ne casse — les étapes détaillées dans [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
