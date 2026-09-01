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

<!-- generated: build_sections.py -->

## Todas as funcionalidades

Quatro capacidades. Tudo o que aparece abaixo corre mesmo na versão atual. Cada parte pode ser desligada em separado em `.chamnan/config.json`, e nenhuma depende das outras.

### Perceber — o que existe e o que está ligado a quê

| | |
|---|---|
| **Índice** | `MAP.md` — uma linha por ficheiro, gerada a partir do próprio código. O agente lê o índice e faz grep do detalhe de que precisa, em vez de percorrer a árvore. |
| **Impacto** | Quem depende deste ficheiro e que testes o cobrem. Os imports dele já estão no topo do ficheiro; caro é o sentido inverso — faça grep do caminho antes de mexer. |
| **Modelo de dados** | Nomes de tabelas e modelos com uma linha de descrição, retirados de DDL, migrações e modelos ORM — não um despejo do esquema inteiro. Só aparece se o repositório definir algum. |
| **Superfície da API** | Método, caminho e handler, a partir de decoradores de rotas, documentos OpenAPI e definições de serviço `.proto` — não a especificação toda. |
| **Configuração** | Os nomes das variáveis de ambiente que o repositório lê. **Só nomes, nunca valores** — e avisa se `.env` não estiver no gitignore. |
| **Implantação** | O que corre de facto, lido de manifestos de Kubernetes, Ansible, Compose, Helm e CI: tipos e nomes, imagens, papéis, pipelines. De um Secret retira apenas o nome, nada do que está por baixo. |
| **Material que não é código** | Papéis digitalizados, exportações, arquivos — apenas contagens, tamanhos e extensões dominantes. Existe para que o agente não vá ver por si, o que sai muito mais caro. **Nunca é aberto, nunca é lido.** |

### Lembrar — o que estava a ser feito, e porquê

| | |
|---|---|
| **Estado do trabalho** | `STATE.md` — aquilo em que se trabalha neste momento; injetado no início da sessão para que a compactação do contexto deixe de o apagar. |
| **Registo de sessão** | Um por sessão em `.chamnan/sessions/`. À sessão seguinte chega **só o que ficou por acabar**; uma sessão fechada em condições não injeta nada. |
| **Memória** | `decisions/`, `lessons/`, `rules/`. As regras são restrições permanentes, por isso ficam à frente do agente em todas as sessões; decisões e lições dão apenas um título e são lidas quando o título parece pertinente. |
| **Fios abertos** | Linhas de trabalho ainda por fechar, com o historial dos ficheiros que esse fio tocou — e continuam a segui-los depois de o ficheiro mudar de nome. |

### Reutilizar — o que já foi resolvido

| | |
|---|---|
| **Procedimentos** | Competências que o agente escreve **por si** quando esbarra em algo complexo ou repetido. Não é uma biblioteca já feita, é um mecanismo. |
| **Ferramentas** | Repara que o mesmo script descartável foi escrito outra vez e propõe guardá-lo — e lembra-o antes de escrever um novo. |
| **Fluxos de trabalho** | Repara que os mesmos comandos correram pela mesma ordem em dias distintos, e propõe pôr essa sequência por escrito. |

### Acumular — o que o repositório aprendeu sobre si próprio

| | |
|---|---|
| **Marcos** | As poucas mudanças que refizeram a forma do repositório: o que se moveu, porque valeu a pena, que zonas tocou. |
| **Candidatos** | As sequências repetidas de comandos detetadas ficam **sempre à espera de confirmação humana**. Nada é promovido automaticamente. |
| **Ambientes** | Declare o que é production ou staging e o que lá é proibido — e ele avisa quando essa declaração envelhece. |
| **Relatório** | O que o espaço de trabalho guarda, se está mesmo ao alcance, e como mudou o contexto por turno no seu repositório. O seu número, não o nosso. |

Trabalho de engenharia repetido torna-se conhecimento reutilizável do repositório — **não é treinar um modelo nem automatizar o programador.** É uma forma de guardar trabalho que, de outro modo, só existiria na cabeça de quem o fez.

## Comandos

Todos podem ser chamados da shell, e o agente também os chama por si.

| | |
|---|---|
| `chamnan-map` | constrói e atualiza o índice |
| `chamnan-report` | o que o espaço de trabalho guarda e como mudou o contexto por turno |
| `chamnan-impact` | quem depende deste ficheiro e que testes o cobrem |
| `chamnan-timeline` | o que já aconteceu a este ficheiro |
| `chamnan-peek` | diz o que há dentro de um ficheiro grande sem o ler para o contexto |
| `chamnan-promote` | guarda um script como ferramenta permanente do repositório |
| `chamnan-candidates` | ver, confirmar ou rejeitar as repetições detetadas |
| `chamnan-env` | declarar um ambiente e as suas proibições, e verificar se a declaração ainda está fresca |
| `chamnan-age` | onde o conhecimento guardado começou a envelhecer |

E as competências chamadas de dentro da sessão: `/chamnan:bootstrap` `/chamnan:remap` `/chamnan:resume` `/chamnan:remember` `/chamnan:milestone` `/chamnan:capture` `/chamnan:promote` `/chamnan:report`

## O que escreve, e onde

Tudo dentro de `.chamnan/`, markdown e JSON vulgares. Lê-se, edita-se à mão e apaga-se a qualquer momento sem partir nada.

| | |
|---|---|
| `MAP.md` | o que existe e o que depende de quê |
| `STATE.md` | em que se trabalha neste momento |
| `sessions/` | onde parou o trabalho anterior |
| `memory/` | decisões, lições e regras permanentes |
| `threads/` | linhas de trabalho ainda abertas |
| `skills/` · `tools/` | procedimentos e scripts que vale a pena guardar |
| `milestones.md` | as mudanças que refizeram a forma do repositório |
| `config.json` | ligar e desligar cada parte, e o teto em bytes do bloco injetado na sessão |

**A única escrita fora de `.chamnan/`** é um hook de Git pre-commit opcional que mantém o índice a par da árvore — só é instalado se disser que sim, e pode ser retirado.

**O agente não aprende.** Nada é treinado, nada fica fora desta pasta, e a sessão seguinte continua a começar do zero — só que começa do zero *num repositório que se explica a si próprio*. A continuidade está nos artefactos, não no modelo.

## Segurança

| | |
|---|---|
| **Nenhuma chamada de rede em execução** | Nem uma. Não é preciso chave de API e nada é enviado para lado nenhum. |
| **Não reescreve o seu código** | Relata, não edita. O índice copia os comentários que já escreveu, não os inventa; os ficheiros sem comentário são nomeados para que os preencha você. |
| **Sem daemon, sem trabalho em segundo plano** | Nenhum processo residente, nenhuma base de dados, nenhum modelo de embeddings — apenas a biblioteca padrão do Python. |
| **Os segredos são filtrados primeiro** | Tudo o que vai ser escrito ou injetado na sessão passa antes pelo filtro de segredos: ficam os *nomes* das variáveis, não os valores. E o limite a que esse filtro não chega está escrito ao lado do seu próprio número no README em inglês. |
| **O que um plugin instalado lhe pode fazer** | Explicado por inteiro no README em inglês, incluindo onde o chamnan quebra a cadeia de exfiltração. |

## Requisitos

Claude Code · Python · Git · macOS, Linux ou Windows

Mais nada, e nenhuma dependência a instalar. A versão mínima do Python está em [README › Requirements](../../README.md#requirements) — esta página não leva números, porque o que muda são os números.

## Desligar ou remover

Desligue por partes em `.chamnan/config.json` · pare-o num único repositório · remova o plugin da máquina toda · apague `.chamnan/` quando quiser sem partir nada — os passos detalhados em [README › Update, disable, uninstall](../../README.md#update-disable-uninstall)

<!-- /generated -->

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
