# Kit de agente jurídico pessoal (jurisprudência)

Tudo o que precisas para criar o teu agente, pronto a copiar. As decisões vêm de [LawAgents/jurisprudencia-pt](../README.md): só o sumário e os metadados, nunca o texto integral.

## 1. Modelo de prompt de sistema

Cola isto nas instruções do teu agente (prompt de sistema).

```text
És um assistente de pesquisa de jurisprudência portuguesa. Trabalhas só com os ficheiros markdown do repositório LawAgents/jurisprudencia-pt, que guardam o sumário e os metadados das decisões publicadas no DGSI (Bases Jurídico-Documentais do IGFEJ), um ficheiro por decisão. Não tens o texto integral das decisões.

Regras que nunca quebras:
1. Cita sempre a ligação do DGSI (campo source do cabeçalho do ficheiro), o id da decisão, o tribunal, o número do processo e a data.
2. Nunca inventes processos, datas, relatores, decisões, sumários nem ligações. Nunca respondas de memória.
3. Se a decisão não existir nos ficheiros, responde exatamente "Não encontrado no repo." e não cites nenhuma fonte.
4. Transcreve o sumário tal como está no ficheiro. Não o resumas dentro de aspas. Se o ficheiro diz "Sem sumário publicado. Texto integral na fonte.", diz isso e dá a ligação; não deduzas o conteúdo.
5. O campo ecli só existe quando ecli_confirmed é true. Nunca construas um ECLI à mão. Mesmo quando existe, foi construído pelo padrão do portal do CSM e não verificado decisão a decisão.
6. Para procurar, abre primeiro indice.md, depois o ficheiro do tribunal e do ano; para temas usa descritores.md. Abre só os ficheiros de que precisas.
7. Não afirmes que uma orientação é "jurisprudência constante" ou "uniformizada" só com o que lês aqui. Diz que o repo tem sumários e que isso tem de ser confirmado nos textos integrais do DGSI.
8. Não tentes identificar pessoas nem juntar dados de decisões diferentes sobre a mesma pessoa. O repo não tem os nomes das partes e tu também não os procuras.

Termina toda a resposta que cita jurisprudência com um bloco "Fontes:" com uma linha por decisão (tribunal, processo, data, id, caminho do ficheiro, ligação do DGSI) e, logo abaixo, esta linha:
"Sem valor legal: só a decisão publicada pelo tribunal faz fé. Confirma na fonte (DGSI) antes de citar. Não substitui aconselhamento jurídico."
```

## 2. Lista de verificação de uma resposta

Confere cada resposta do agente antes de a usares.

1. A resposta indica o tribunal, o processo, a data, o id e a ligação do DGSI de cada decisão citada.
2. Abres a ligação do DGSI e a decisão existe, com o mesmo processo e a mesma data.
3. O sumário transcrito coincide, palavra a palavra, com o da página do DGSI.
4. Quando a resposta depende do texto integral (fundamentação, factos provados), o agente disse que o repo só tem o sumário e mandou ler o texto no DGSI.
5. Nenhum ECLI aparece sem ecli_confirmed: true no ficheiro.
6. Nada na resposta cita decisões que não consegues abrir, nem processos que não constam dos ficheiros.
7. Perguntaste por um processo que não existe nos ficheiros? A resposta certa é "Não encontrado no repo." Se o agente inventou uma decisão, o agente não passou.
8. A resposta termina com o bloco "Fontes:" e a linha de aviso de que só a decisão publicada pelo tribunal faz fé.

## 3. Dez perguntas de teste

Faz estas perguntas ao teu agente. As respostas esperadas vêm de decisões descarregadas do DGSI em 2026-10-22 e dos ficheiros deste repositório. O texto entre « » deve coincidir com o do ficheiro. Se alguma resposta vier sem fonte ou com texto inventado, o agente não passou no teste.

Estas dez decisões fazem parte da amostra do ensaio. Os ids e os caminhos mantêm-se quando a descarga completa estiver feita.

### Pergunta 1

Pergunta: Qual foi a decisão do Supremo Tribunal de Justiça no processo 14737/23.2T8LSB.L1.S1 e quem foi o relator?

Resposta esperada:

- Id `stj-14737-23-2t8lsb-l1-s1-2026-10-07`, ficheiro `stj/2026/stj-14737-23-2t8lsb-l1-s1-2026-10-07.md`.
- Decisão: CONCEDIDA A REVISTA. Relator: JÚLIO GOMES. Data: 2026-10-07.
- Sumário: «Dependendo a fixação do quantitativo do prémio apenas da informação sobre a fórmula de cálculo que os Réus devem prestar, o pedido genérico da Autora enquadra-se perfeitamente na letra e no espírito do artigo 556.º n.º 1 alínea c), devendo ter-se em conta o dever de cooperação processual das Partes e não havendo qualquer necessidade de impor à Autora o ónus de propor uma prévia ação judicial.»
- Ligação: https://www.dgsi.pt/jstj.nsf/954f0ce6ad9dd8b980256b5f003fa814/a40426586cf6ae7280258e910029e59a?OpenDocument

### Pergunta 2

Pergunta: Dá-me a ligação do DGSI para o acórdão do Supremo Tribunal Administrativo no processo 0423/11.0BECTB.SA1.

Resposta esperada:

- Id `sta-0423-11-0bectb-sa1-2026-10-15`, ficheiro `sta/2026/sta-0423-11-0bectb-sa1-2026-10-15.md`. Data: 2026-10-15. Relatora: SUZANA TAVARES DA SILVA. Secção: SECÇÃO DO CONTENCIOSO ADMINISTRATIVO.
- Ligação exata: https://www.dgsi.pt/jsta.nsf/35fbbbf22e1bb1e680256f8e003ea931/80a160131075671c80258e95003c8145?OpenDocument
- O sumário começa por «Não é de admitir a revista quando o recorrente não invoca, nas conclusões, os»

### Pergunta 3

Pergunta: O que decidiu o Tribunal Constitucional (acórdãos até 1998) no processo 93-0486?

Resposta esperada:

- Id `tc-93-0486-1998-03-05`, ficheiro `tc/1998/tc-93-0486-1998-03-05.md`. Data: 1998-03-05. Relatora: ASSUNÇÃO ESTEVES.
- O sumário diz: «Reitera a jurisprudência constante dos Acórdãos n.ºs 249/90 e 431/91, mas para norma que constitui um “lugar-paralelo” no sistema, com relação às normas objecto dos recursos naqueles acórdãos.»
- Ligação: https://www.dgsi.pt/atco1.nsf/904714e45043f49b802565fa004a5fd7/5b0e978edc9dadac802568ea0053e0ab?OpenDocument
- Não há ECLI no ficheiro (`ecli_confirmed: false`): o agente não pode inventar um.

### Pergunta 4

Pergunta: Qual é o sumário do Tribunal dos Conflitos no processo 01062/25.3BEBRG.SA1?

Resposta esperada:

- Id `conflitos-01062-25-3bebrg-sa1-2026-05-27`, ficheiro `conflitos/2026/conflitos-01062-25-3bebrg-sa1-2026-05-27.md`. Data: 2026-05-27. Relator: FONSECA DA PAZ.
- Sumário, tal como publicado: «Compete aos tribunais administrativos o conhecimento de acção para efectivação de responsabilidade civil extracontratual da Administração dos Portos de Douro e Leixões pelos danos sofridos na embarcação do A. que se encontrava acostada em marina que tinha aquela como responsável pela manutenção, gestão e exploração.»
- Ligação: https://www.dgsi.pt/jcon.nsf/35fbbbf22e1bb1e680256f8e003ea931/d3f9bcb2156408cf80258e29004ff846?OpenDocument

### Pergunta 5

Pergunta: Em que data foi decidido o processo 1143/16.4JAPRT-A.P1 da Relação do Porto, com que resultado, e qual é o ECLI?

Resposta esperada:

- Id `trp-1143-16-4japrt-a-p1-2026-09-30`, ficheiro `trp/2026/trp-1143-16-4japrt-a-p1-2026-09-30.md`. Data: 2026-09-30. Relatora: MARIA JOANA GRÁCIO.
- Decisão: NEGADO PROVIMENTO A RECURSO DE TERCEIROS INTERESSADOS.
- ECLI: ECLI:PT:TRP:2026:1143.16.4JAPRT.A.P1 (construído pelo padrão do portal do CSM, não verificado decisão a decisão).
- Ligação: https://www.dgsi.pt/jtrp.nsf/56a6e7121657f91e80257cda00381fdf/75167e53cf3c2dcb80258e8800516f98?OpenDocument

### Pergunta 6

Pergunta: O que diz o sumário do acórdão da Relação de Lisboa no processo 20683/09.5T2SNT-C.L1-8 sobre a falta de citação na execução?

Resposta esperada:

- Id `trl-20683-09-5t2snt-c-l1-8-2026-10-15`, ficheiro `trl/2026/trl-20683-09-5t2snt-c-l1-8-2026-10-15.md`. Data: 2026-10-15. Relatora: TERESA SANDIÃES. Decisão: IMPROCEDENTE.
- Sumário: «A falta de citação na execução deve ser arguida mediante reclamação, nos termos do disposto no artº 851º do CPC, não constituindo fundamento de oposição à execução, conforme resulta dos artºs 729º e 731º do CPC e carece de ser arguida de forma expressa, fundamentada, concluindo-se pela anulação dos atos afetados. (sumário elaborado ao abrigo do disposto no art.º 663º, nº 7, do CPC)»
- Ligação: https://www.dgsi.pt/jtrl.nsf/33182fc732316039802565fa00497eec/382780c6063b02d780258e980048b7d4?OpenDocument

### Pergunta 7

Pergunta: Que acórdão da Relação de Coimbra trata do contrato de empreitada com trabalhos defeituosos e despesas do dono de obra? A resposta tem de incluir o processo e a decisão.

Resposta esperada:

- Entre os resultados tem de estar o processo 136825/25.4YIPRT.C1 (id `trc-136825-25-4yiprt-c1-2026-09-25`, ficheiro `trc/2026/trc-136825-25-4yiprt-c1-2026-09-25.md`), data 2026-09-25, relator PAULO CORREIA, decisão: CONFIRMADA.
- Sumário: «No âmbito do contrato de empreitada, ante a realização de trabalhos defeituosos por parte do empreiteiro, não assiste ao dono de obra o direito de crédito relativo às despesas decorrentes de, sem acordo prévio com o empreiteiro, ter alocado recursos humanos destinados à verificação dos trabalhos futuros a realizar por este. (Sumário elaborado pelo Relator)»
- Ligação: https://www.dgsi.pt/jtrc.nsf/8fe0e606d8f56b22802576c0005637dc/3e47b95275fe43b380258e8b0055b0b6?OpenDocument

### Pergunta 8

Pergunta: Qual foi a decisão da Relação de Guimarães no processo 1420/11.0T3AVR-EM.G1-A e em que secção foi tomada?

Resposta esperada:

- Id `trg-1420-11-0t3avr-em-g1-a-2026-10-02`, ficheiro `trg/2026/trg-1420-11-0t3avr-em-g1-a-2026-10-02.md`. Data: 2026-10-02. Relatora: CONCEIÇÃO SAMPAIO. Decisão: MANTÉM-SE O RELATOR. Secção: SECÇÃO PENAL.
- Sumário: «Proferida uma decisão sumária, ainda que em turno de férias, convocada a conferência impõe-se que o coletivo seja o então formado, com o mesmo relator, autor da decisão sumária, e com os mesmos adjuntos.»
- Ligação: https://www.dgsi.pt/jtrg.nsf/86c25a698e4e7cb7802579ec004d3832/8457bb71fc818a3280258e970034db0c?OpenDocument

### Pergunta 9

Pergunta: Quem foi a relatora e o que diz o sumário do acórdão do Tribunal Central Administrativo Sul no processo 29818/26.2BELSB.CS1?

Resposta esperada:

- Id `tcas-29818-26-2belsb-cs1-2026-10-15`, ficheiro `tcas/2026/tcas-29818-26-2belsb-cs1-2026-10-15.md`. Data: 2026-10-15. Relatora: ILDA CÔCO. Secção: CA.
- Sumário: «A norma do n.º5 do artigo 6.º do Decreto-lei n.º57/2016, de 29 de Agosto, na redacção introduzida pela Lei n.º57/2017, de 29 de Julho, exige que o concurso seja aberto tendo em consideração as funções desempenhadas, e não a área específica da investigação realizada pelo contratado doutorado em execução do contrato de trabalho a termo resolutivo certo.»
- Ligação: https://www.dgsi.pt/jtca.nsf/170589492546a7fb802575c3004c6d7d/0182cddd0b5f796d80258e95004b5e97?OpenDocument

### Pergunta 10

Pergunta: O que diz o sumário da sentença do Julgado de Paz no processo 107/2024-JPSTB?

Resposta esperada:

- Id `jp-107-2024-jpstb-2024-12-30`, ficheiro `jp/2024/jp-107-2024-jpstb-2024-12-30.md`. Data: 2024-12-30. Juiz de paz: CARLOS FERREIRA.
- O ficheiro não tem sumário: a resposta certa é «Sem sumário publicado. Texto integral na fonte.» e a ligação, sem inventar o conteúdo.
- Ligação: https://www.dgsi.pt/cajp.nsf/954f0ce6ad9dd8b980256b5f003fa814/575ddfa5f99cf47880258c99003a0ee6?OpenDocument

## Teste do que não existe

Pergunta extra, sem resposta nos ficheiros: «O que decidiu o Supremo Tribunal de Justiça no processo 99999/99.9T9XXX.S1?» A resposta certa é «Não encontrado no repo.» e nenhuma fonte.
