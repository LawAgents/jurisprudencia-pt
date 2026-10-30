- Portuguese court decisions as markdown: metadata and sumário (headnote) only, one file per decision, from the DGSI legal databases of the IGFEJ (13 databases, 396,733 decisions of the 409,009 listed on 2026-10-22).
- Layered indices by court and year plus an index of descritores (subject keywords), every index file at most 40 KB.
- No full texts and no names of parties: only fields the DGSI publishes. An ECLI appears only for courts where the CSM portal pattern was confirmed.
- Step-by-step guides in European Portuguese for non-programmers, plus a ready-made kit: system prompt, checklist and ten test questions.
- Only the decision published by the court is authentic. Scripts are MIT; decisions are public court decisions published via DGSI, non-commercial use, cite the source. Written confirmation of the reuse terms from IGFEJ/CSM has not been obtained yet (the request is still to be sent).

# Jurisprudência dos tribunais portugueses: sumários e metadados

O sumário e os metadados das decisões dos tribunais portugueses publicadas no DGSI (as Bases Jurídico-Documentais do IGFEJ),
convertidos para markdown, um ficheiro por decisão, com cabeçalho estruturado e ligação ao DGSI em cada ficheiro. O sumário diz a
regra jurídica de cada decisão, por isso serve para encontrar a decisão certa; o texto integral fica na fonte. Os índices em
camadas (por tribunal e ano, e por descritor) dizem ao agente que ficheiro abrir. O repositório irmão da lei portuguesa é
[LawAgents/pt](https://github.com/LawAgents/pt) e o da lei da União Europeia é [LawAgents/ue-pt](https://github.com/LawAgents/ue-pt).

> [!IMPORTANT]
> Só a decisão publicada pelo tribunal faz fé. Os ficheiros daqui têm o sumário e os metadados, nunca o texto integral: confirma
> sempre no DGSI pela ligação do cabeçalho antes de citar. O DGSI não publica nenhum aviso de reutilização e a confirmação escrita
> do IGFEJ/CSM ainda não foi obtida (o pedido ainda não foi enviado) (ver "Avisos legais e política de reutilização").

---

## O que contém

Estado desta versão: descarga completa de 2026-10-25 a 2026-10-29. O repositório tem 396.733 decisões, 97,0 % das 409.009 que a
página inicial do DGSI anunciava em 2026-10-22. A diferença (12.276 decisões) não vem de falhas na descarga: a lista de cada base
acabou sem ligação "Seguinte" e trouxe menos linhas do que o número anunciado, sobretudo no TCA Sul (26.499 de 31.317), no TCA Norte
(15.329 de 20.830) e no STJ (71.812 de 73.758). A causa não está confirmada.

O DGSI lista, por base (contagens da página inicial do DGSI, 2026-10-22), e o repositório tem:

| Tribunal | Id | Decisões no DGSI | Neste repositório |
| --- | --- | ---: | ---: |
| Supremo Tribunal de Justiça | stj | 73.758 | 71.812 |
| Supremo Tribunal Administrativo | sta | 90.341 | 90.318 |
| Tribunal Constitucional (até 1998) | tc | 6.107 | 6.107 |
| Tribunal dos Conflitos | conflitos | 1.257 | 1.257 |
| Tribunal da Relação do Porto | trp | 64.306 | 64.308 |
| Tribunal da Relação de Lisboa | trl | 61.899 | 61.926 |
| Tribunal da Relação de Coimbra | trc | 16.834 | 16.833 |
| Tribunal da Relação de Guimarães | trg | 15.994 | 15.982 |
| Tribunal da Relação de Évora | tre | 18.652 | 18.652 |
| Tribunal Central Administrativo Sul | tcas | 31.317 | 26.499 |
| Tribunal Central Administrativo Norte | tcan | 20.830 | 15.329 |
| Julgados de Paz | jp | 7.322 | 7.322 |
| Cláusulas contratuais abusivas | dgpj | 392 | 388 |
| **Total** | | **409.009** | **396.733** |

Nem todas as decisões têm sumário: 16.387 das 396.733 (4,1 %) não têm. Os Julgados de Paz e as Cláusulas contratuais abusivas não
têm campo de sumário. Nesses ficheiros há só os metadados e a ligação à fonte, com a frase fixa "Sem sumário publicado. Texto
integral na fonte.". Há ainda 105 decisões cujo sumário tinha mais de 20.000 caracteres e foi substituído pela mesma frase.

Tamanho: 396.733 ficheiros de decisão, 738 MB sem compressão (medido em 2026-10-30 por `scripts/estatisticas.py`), abaixo do limite
de 1 GiB do repositório (`scripts/check_size.py`).

Verificação: 60 decisões escolhidas ao acaso em cada uma das 13 bases (780 no total) foram comparadas com a página ao vivo do DGSI
(número do processo e primeiras 40 palavras do sumário): as 780 coincidem.

`COBERTURA.md` e `estatisticas.html` são gerados por `python -I scripts/estatisticas.py` e refazem-se na atualização semanal sempre
que há alterações.

### O que fica de fora

- O texto integral das decisões. É a Fase 2 do projeto, depende da resposta do IGFEJ/CSM e do tamanho (o texto integral de tudo não cabe num repositório). A descarga guarda a página completa de cada decisão numa cache fora do repositório, para essa fase.
- Os nomes das partes (campos como Autor, Réu, Recorrente, Recorrido ou Requerente de algumas bases) e qualquer outro campo de texto livre além do sumário. Também não se faz anonimização nem desanonimização.
- Um sumário com mais de 20.000 caracteres: quase sempre é o texto integral colado pelo tribunal no campo do sumário. Esse ficheiro leva a frase fixa de "sem sumário", e `COBERTURA.md` conta quantos foram.
- Os anexos em PDF das Cláusulas contratuais abusivas, o campo "Texto Integral" quando traz texto ou nomes de ficheiros, e as bibliotecas e os pareceres do Ministério Público que o DGSI também tem.
- Jurisprudência do Tribunal de Justiça da União Europeia e do Tribunal Europeu dos Direitos Humanos, e decisões que não estão no DGSI.
- Versões anteriores de uma decisão: o histórico fica no git.

---

## Estrutura

```
<tribunal>/<ano>/<id>.md                    um ficheiro por decisão (tribunal: stj, sta, tc, conflitos, trp, trl, trc, trg, tre, tcas, tcan, jp, dgpj)
indice.md                                   um índice por tribunal
indice-<tribunal>.md                        um índice por ano (e as faixas de datas dos anos grandes)
indice-<tribunal>-<ano>[-a].md              id, data, processo, relator, descritores e caminho (ficheiros de até 40 KB, por data)
descritores.md  descritores-*.md            descritor sem acentos nem maiúsculas, número de decisões e ficheiros de índice onde aparece
COBERTURA.md                                números por tribunal, década e ano, relatores, descritores e decisões sem sumário
estatisticas.html                           página com gráficos, um único ficheiro para abrir no navegador
config/tribunais.txt                        as 13 bases (id, nome, caminho no DGSI, sigla ECLI)
config/retirada.txt                         ids de decisões que o pipeline nunca publica
scripts/                                    o código que descarrega, converte, valida e gera os índices e as estatísticas
docs/kit.md                                 kit de agente jurídico pessoal
```

O id de uma decisão é `<tribunal>-<processo>-<aaaa-mm-dd>`, com o processo em minúsculas, sem acentos e com tudo o que não é letra
ou número trocado por `-`: o processo `1571/19.3T8OAZ-E.P1.S1` do STJ, decidido em 2026-10-20, dá
`stj-1571-19-3t8oaz-e-p1-s1-2026-10-20`. Quando o mesmo processo tem duas decisões no mesmo dia, uma fica com o id simples e a outra
leva no fim os primeiros 8 caracteres do identificador do DGSI.

---

## Formato dos ficheiros

Todo o ficheiro tem cabeçalho YAML e, no corpo, o título em `#` e o sumário tal como o tribunal o publicou (só com as quebras de
linha refeitas):

```markdown
---
id: "stj-14737-23-2t8lsb-l1-s1-2026-10-07"
title: "Supremo Tribunal de Justiça, processo 14737/23.2T8LSB.L1.S1, 2026-10-07"
tribunal: "stj"
processo: "14737/23.2T8LSB.L1.S1"
relator: "JÚLIO GOMES"
data: 2026-10-07
votacao: "UNANIMIDADE"
meio_processual: "REVISTA"
decisao: "CONCEDIDA A REVISTA"
descritores: ["PEDIDO GENÉRICO"]
texto_integral: "S"
privacidade: "1"
source: "https://www.dgsi.pt/jstj.nsf/954f0ce6ad9dd8b980256b5f003fa814/a40426586cf6ae7280258e910029e59a?OpenDocument"
ecli: "ECLI:PT:STJ:2026:14737.23.2T8LSB.L1.S1"
ecli_confirmed: true
retrieved: 2026-10-22
text_version: "sumário e metadados, sem texto integral"
legal_notice: "Sem valor legal: só a decisão publicada pelo tribunal faz fé. Confirma na fonte (DGSI) antes de citar. Não substitui aconselhamento jurídico."
---

# Supremo Tribunal de Justiça, processo 14737/23.2T8LSB.L1.S1, 2026-10-07

## Sumário

Dependendo a fixação do quantitativo do prémio apenas da informação sobre a fórmula de cálculo que os Réus devem prestar, o pedido genérico da Autora enquadra-se perfeitamente na letra e no espírito do artigo 556.º n.º 1 alínea c), devendo ter-se em conta o dever de cooperação processual das Partes e não havendo qualquer necessidade de impor à Autora o ónus de propor uma prévia ação judicial.
```

- Só os campos que o DGSI publica para a decisão aparecem. O relator é o juiz identificado na decisão. `secao` aparece quando a base publica a secção.
- `texto_integral` é o valor S ou N que o DGSI publica (STJ e Relações). Nas outras bases o campo traz texto ou nada e fica de fora. `privacidade` é o valor publicado (`1`, `01` ou ausente).
- `ecli` aparece só nos tribunais em que a medição confirmou o padrão do portal de jurisprudência do CSM (STJ e as cinco Relações), com `ecli_confirmed: true`. Nos outros, `ecli_confirmed: false` e nenhum ECLI. O ECLI é construído pelo padrão (`ECLI:PT:<tribunal>:<ano>:<processo com / e - trocados por .>`) e não é verificado decisão a decisão: na medição, 8 de 9 consultas manuais devolveram a decisão certa e 1 (um processo com dois hífenes) não. O portal do CSM nunca é consultado em massa.
- `retrieved` é a data em que a página foi descarregada.
- Nas decisões sem sumário, a secção `## Sumário` tem só a frase "Sem sumário publicado. Texto integral na fonte.".

---

## Atualização

Uma tarefa do GitHub corre todos os domingos às 05:00 UTC, pede ao DGSI as primeiras páginas de cada lista (as decisões mais recentes
vêm primeiro), descarrega as decisões que ainda não tem e pára na primeira página de lista em que todas já estavam descarregadas.
Os Julgados de Paz têm a lista ordenada por processo e não por data, por isso essa lista lê-se sempre até ao fim. Depois converte,
valida, refaz os índices e as estatísticas e faz um commit por atualização. Se algo falhar, não publica dados parciais e abre uma
issue com o erro.

O descarregador faz no máximo 4 pedidos por segundo, medidos pela hora de início de cada pedido, identifica-se com o
`User-Agent` "LawAgents-jurisprudencia (github.com/LawAgents)", pára depois de 3 erros seguidos e baixa para 2 e depois 1 pedido por
segundo se um pedido demorar mais de 5 segundos ou o servidor responder 429 ou 503 (nunca volta a subir na mesma execução). Se o
IGFEJ pedir menos, cumpre-se o que pedir.

Estado: a descarga completa fez-se entre 2026-10-25 e 2026-10-29 com o mesmo descarregador, com paragens e retomas. A atualização
semanal ainda não correu no GitHub: foi testada com um servidor simulado e falta o ensaio com `dry_run`.

---

## Passo a passo para quem não programa

Escolhe um dos três caminhos.

### Caminho 1: plugin no Claude Code

Os comandos para jurisprudência (`/acordao` e `/pesquisar-jurisprudencia`) ainda não existem: vêm numa fase seguinte do plugin
[legislacao-pt](https://github.com/LawAgents/legislacao-pt-plugin). Até lá usa os caminhos 2 e 3.

### Caminho 2: Projeto do Claude.ai com decisões como conhecimento

1. Abre o claude.ai e cria um Projeto novo.
2. Em https://github.com/LawAgents/jurisprudencia-pt abre `indice.md`, depois o ficheiro do tribunal e do ano, e descarrega os ficheiros das decisões de que precisas (em cada ficheiro, botão "Download raw file").
3. No Projeto, abre a zona de conhecimento (Project knowledge) e carrega esses ficheiros.
4. Nas instruções do Projeto, cola o texto abaixo.

```text
Responde sobre jurisprudência portuguesa usando apenas os ficheiros carregados neste Projeto.
Cita sempre o tribunal, o processo, a data e a ligação do DGSI que consta no cabeçalho (campo source) do ficheiro de onde tiraste a informação.
Nunca inventes processos, datas, relatores, decisões, sumários nem ligações, e nunca completes de memória.
Transcreve o sumário tal como está no ficheiro. Estes ficheiros não têm o texto integral: se a pergunta depende dele, diz isso e manda ler a decisão no DGSI.
Se a resposta não estiver nos ficheiros carregados, responde "Não encontrado nos ficheiros carregados." e não cites nada.
Só indiques um ECLI se o campo ecli_confirmed for true.
Termina sempre com: "Sem valor legal: só a decisão publicada pelo tribunal faz fé. Confirma na fonte (DGSI) antes de citar. Não substitui aconselhamento jurídico."
```

### Caminho 3: qualquer agente que leia ficheiros markdown ou abra ligações da web

Forma A, o agente lê ficheiros. Descarrega o repositório (em https://github.com/LawAgents/jurisprudencia-pt, botão "Code", "Download ZIP"), descomprime e aponta o agente para a pasta.

Forma B, o agente abre ligações. Dá-lhe o endereço https://github.com/LawAgents/jurisprudencia-pt e diz-lhe que pode abrir os ficheiros pelo endereço "raw" do GitHub (https://raw.githubusercontent.com/LawAgents/jurisprudencia-pt/main/, seguido do caminho do ficheiro). Pede-lhe que comece por `indice.md`, e que só abra os índices e as decisões de que precisar.

Em ambas as formas, cola nas instruções do agente o texto abaixo.

```text
Tens acesso a sumários e metadados de jurisprudência portuguesa no repositório LawAgents/jurisprudencia-pt (ficheiros markdown, um por decisão).
Para encontrar uma decisão lê primeiro indice.md, depois o índice do tribunal e do ano; para procurar por tema lê descritores.md.
Responde só com o que lês nos ficheiros. Cita sempre o tribunal, o processo, a data, o ficheiro (caminho no repo) e a ligação do DGSI (campo source do cabeçalho).
Nunca inventes processos, datas, decisões, sumários nem ligações, e nunca respondas de memória.
Estes ficheiros não têm o texto integral: se a pergunta depende dele, diz isso e manda ler a decisão no DGSI.
Se não encontrares, responde "Não encontrado no repo." e não cites nada.
Só indiques um ECLI se o campo ecli_confirmed for true.
Termina sempre com: "Sem valor legal: só a decisão publicada pelo tribunal faz fé. Confirma na fonte (DGSI) antes de citar. Não substitui aconselhamento jurídico."
```

O [kit de agente jurídico pessoal](docs/kit.md) tem um modelo de prompt de sistema mais completo, uma lista de verificação e dez perguntas de teste com a resposta esperada, tiradas de decisões que foram descarregadas.

---

## Avisos legais e política de reutilização

Os textos deste repositório vêm do DGSI, o sítio das Bases Jurídico-Documentais do Instituto de Gestão Financeira e Equipamentos da
Justiça (IGFEJ), onde os tribunais publicam as suas decisões. O portal de jurisprudência do Conselho Superior da Magistratura
(CSM), que dá o identificador europeu de jurisprudência (ECLI) dos tribunais judiciais superiores, tem esta advertência
(https://jurisprudencia.csm.org.pt/advertencia, consultada em 2026-10-22):

> as informações que constam deste sítio são públicas e podem ser reproduzidas, desde que a respectiva fonte seja mencionada. No entanto, é proibida a sua utilização para fins comerciais ou ofensivos

A mesma página declara que a informação não vincula o CSM e que não garante que o texto em linha reproduza de forma exata o texto
adotado oficialmente.

O DGSI não publica nenhum aviso de reutilização e não tem `robots.txt`. A confirmação escrita do IGFEJ/CSM sobre as condições de
reutilização e sobre o descarregamento automático ainda não foi obtida (o pedido ainda não foi enviado). Até haver resposta, este repositório aplica o
que o aviso do CSM cobre: indica a fonte em cada ficheiro e deve ser usado sem fins comerciais.

Dados pessoais: copiam-se só os campos que o DGSI publica, tal como estão. Não se anonimiza nem se desanonimiza nada, não se copiam
os nomes das partes e o texto integral não está aqui. O relator é o juiz que assina a decisão.

## Pedido de retirada

Se uma decisão não devia estar aqui, abre uma issue com o número do processo e o tribunal. A resposta chega em 72 horas. O id da
decisão entra em `config/retirada.txt`, o pipeline nunca mais o publica, e o ficheiro e as linhas dos índices saem na atualização
seguinte. Se também for preciso retirar a versão antiga do histórico do git, pede-o na mesma issue.

## Licenças

- Os scripts têm a licença MIT.
- As decisões são decisões públicas de tribunais, publicadas pelos próprios tribunais no DGSI. Usam-se sem fins comerciais e com indicação da fonte (DGSI/IGFEJ e o tribunal), nos termos da advertência do CSM citada acima. Este repositório não reivindica direitos sobre o seu conteúdo.

## Como contribuir

- Pull requests só são aceites para `config/`, `docs/` e `README.md`.
- Os ficheiros das decisões, os índices e as estatísticas não aceitam edições à mão, porque são gerados a partir do DGSI.
- Encontraste um erro numa decisão? Abre uma issue com o número do processo e a ligação do DGSI onde se vê o texto correto.

## Kit de agente jurídico pessoal

Em [docs/kit.md](docs/kit.md): modelo de prompt de sistema com citação obrigatória da ligação do DGSI, lista de verificação e dez perguntas de teste com a resposta esperada.
