# chamnan — para que um repositório conheça a si mesmo

<sub>[🇬🇧 English](../../README.md) · [🇨🇳 中文](README.zh-CN.md) · [🇹🇼 繁體中文](README.zh-TW.md) · [🇯🇵 日本語](README.ja.md) · [🇰🇷 한국어](README.ko.md) · [🇹🇭 ไทย](README.th.md) · [🇻🇳 Tiếng Việt](README.vi.md) · [🇮🇩 Indonesia](README.id.md) · [🇮🇳 हिन्दी](README.hi.md) · [🇧🇩 বাংলা](README.bn.md) · [🇵🇰 اردو](README.ur.md) · [🇸🇦 العربية](README.ar.md) · [🇮🇱 עברית](README.he.md) · [🇹🇷 Türkçe](README.tr.md) · [🇷🇺 Русский](README.ru.md) · [🇺🇦 Українська](README.uk.md) · [🇵🇱 Polski](README.pl.md) · [🇨🇿 Čeština](README.cs.md) · [🇩🇪 Deutsch](README.de.md) · [🇳🇱 Nederlands](README.nl.md) · [🇫🇷 Français](README.fr.md) · [🇪🇸 Español](README.es.md) · [🇵🇹 Português](README.pt-PT.md) · [🇮🇹 Italiano](README.it.md) · [🇷🇴 Română](README.ro.md) · [🇬🇷 Ελληνικά](README.el.md) · [🇭🇺 Magyar](README.hu.md) · [🇸🇪 Svenska](README.sv.md) · [🇫🇮 Suomi](README.fi.md) · [🇩🇰 Dansk](README.da.md) · [🇳🇴 Norsk](README.no.md) · [🇵🇭 Tagalog](README.tl.md)</sub>

> Esta página não traz nenhum número, de propósito. Todas as medições estão no README em inglês e mudam a cada versão; esta página não. → [Evidence](../../README.md#evidence)

## O que é

Um plugin do Claude Code. Ele monta um índice do repositório que o agente lê em vez de varrer arquivo por arquivo, e guarda o contexto de engenharia que se acumula durante o trabalho — o estado do trabalho, os registros de sessão, os motivos por trás das decisões e os procedimentos que você deduz de novo toda vez.

Tudo o que ele escreve é markdown comum, commitado ao lado do código. Sem chamadas de rede em execução, sem banco de dados, sem daemon, sem modelo de embedding — só a biblioteca padrão do Python.

## O que resolve

A cada sessão nova, e toda vez que o contexto é compactado, some tudo o que o agente tinha entendido do seu código e ele volta a procurar do zero.

O chamnan faz essa redescoberta não precisar acontecer: o índice é entregue no início da sessão, e o custo é um número conhecido e limitado em vez de leituras de arquivo sem limite.

## Instalação

```bash
claude plugin marketplace add ArcticFox2029/chamnan
claude plugin install chamnan@chamnan
```

Abra uma sessão nova e rode `/chamnan:bootstrap` uma vez por repositório.

## Leia antes de instalar

**O chamnan é para aquela pasta principal em que você volta sempre.** Tudo o que ele faz é pago adiantado e recuperado nas sessões seguintes — num repositório que você abre uma vez só, você pagou tudo e não recuperou nada.

**Ele relata, não reescreve seu código.** O índice copia os comentários que você já escreveu e não inventa nenhum. Os arquivos sem comentário são citados pelo nome para você completar.

**Os limites dele foram medidos e escritos**, inclusive as medições que pesam contra o próprio recurso principal.

## Onde está o detalhe

| | |
|---|---|
| Cada número, e como foi medido | [README › Evidence](../../README.md#evidence) |
| Suíte de testes de regressão — você mesmo pode rodar | [`tests/run_tests.py`](../../tests/run_tests.py) |
| O que mudou em cada versão, e por quê | [CHANGELOG.md](../../CHANGELOG.md) |
| Todo o resto | [README.md](../../README.md) |

---

<sub>MIT · [github.com/ArcticFox2029/chamnan](https://github.com/ArcticFox2029/chamnan)</sub>
