# chamnan — para que um repositório se conheça a si próprio

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇧🇷 Português (BR)](README.pt-BR.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Esta página não contém quaisquer números, de propósito. Todas as medições estão no README em inglês e mudam a cada versão; esta página não. → [Evidence](../../README.md#evidence)

## O que é

Um plugin para o Claude Code. Constrói um índice do repositório que o agente lê em vez de percorrer os ficheiros um a um, e guarda o contexto de engenharia que se acumula durante o trabalho — o estado do trabalho, os registos de sessão, as razões por trás das decisões e os procedimentos que se voltam a deduzir de cada vez.

Tudo o que escreve é markdown simples, versionado ao lado do código. Sem chamadas de rede em execução, sem base de dados, sem daemon, sem modelo de embeddings — apenas a biblioteca padrão do Python.

## O que resolve

A cada nova sessão, e sempre que o contexto é comprimido, desaparece tudo o que o agente tinha percebido do seu código e ele volta a procurar do zero.

O chamnan faz com que essa redescoberta não tenha de acontecer: o índice é entregue no início da sessão, e o custo é um número conhecido e limitado em vez de leituras de ficheiros sem limite.

## Instalação

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Abra uma sessão nova e execute `/chamnan:bootstrap` uma vez por repositório.

## Leia antes de instalar

**O chamnan destina-se àquela pasta principal a que volta vezes sem conta.** Tudo o que faz é pago adiantado e recuperado nas sessões seguintes — num repositório que abre uma única vez, pagou tudo e não recuperou nada.

**Reporta, não reescreve o seu código.** O índice copia os comentários que já escreveu e não inventa nenhum. Os ficheiros sem comentário são nomeados um a um para que os complete.

**Os seus limites estão medidos e escritos**, incluindo as medições que jogam contra a sua própria funcionalidade principal.

## Onde está o detalhe

| | |
|---|---|
| Cada número, e como foi medido | [README › Evidence](../../README.md#evidence) |
| Conjunto de testes de regressão — pode executá-lo | [`tests/run_tests.py`](../../tests/run_tests.py) |
| O que mudou em cada versão, e porquê | [CHANGELOG.md](../../CHANGELOG.md) |
| Tudo o resto | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
