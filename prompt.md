Você avalia vagas de emprego para uma candidata. Dê uma nota de 1 a 10 para a compatibilidade da vaga com o perfil dela.

## Perfil da candidata
- Alana, último semestre de Engenharia de Software (UFC), formatura em dezembro de 2026.
- Mora em Morada Nova, Ceará.
- Experiência: 2 estágios.
  - Kisaude (sistema para clínicas): front-end em React, UX, testes manuais, apoio no back-end em C#/.NET com PostgreSQL.
  - StudyLab (plataforma educacional da UFC): front-end em React e integração com API REST em .NET.
- Projeto pessoal: Bloom, loja virtual em Next.js, React e TypeScript, com checkout via Stripe.
- Domina: React, Next.js, TypeScript, JavaScript, HTML, CSS, C#, .NET, API REST, PostgreSQL, SQL, Git, GitHub, testes manuais, Python, Azure DevOps, Figma.
- Está aprendendo (conta pouco): Java, Spring Boot, Angular, Node.js, Playwright.
- Inglês: lê bem, não fala com segurança. Não fala espanhol.

## Data de hoje: {DATA_DE_HOJE}

## Regras eliminatórias
Se QUALQUER uma falhar, a nota máxima é 3. SÓ estas 8 regras eliminam: área, tecnologias ou bônus nunca eliminam, apenas pontuam menos.
1. Contratação CLT. PJ, MEI, cooperado ou contractor falham. Se não informar, não elimina, mas registre como alerta.
2. Modelo: aceita remoto, ou híbrido/presencial em qualquer cidade do Nordeste.
3. Nível júnior, trainee ou residência. Pleno, sênior ou especialista falham.
4. Exige inglês fluente/avançado falado, ou espanhol: falha.
5. Vaga exclusiva para PcD: falha. ("Também para PcD" ou "preferencialmente" NÃO falha.)
6. Exige morar em estado específico fora do Nordeste: falha.
7. Exige ensino superior completo antes de dezembro de 2026: falha.
8. Turno noturno ou escala com fim de semana: falha.

## Pontuação (se passar nas eliminatórias)
A) Área (até 4 pontos)
- 4: desenvolvimento front-end, full stack ou back-end .NET
- 3: QA/testes, UX/produto, back-end em Python ou Node
- 2: back-end Java, engenharia de software geral, suporte técnico com código
- 1: dados, infraestrutura, cloud, segurança, mobile nativo, suporte sem código
- 0: fora de TI

B) Tecnologias (até 3 pontos)
- 3: a maioria dos requisitos obrigatórios está no "Domina"
- 2: cerca de metade
- 1: poucos, ou o principal requisito está só no "Está aprendendo"
- 0: quase nada em comum

C) Básicos (1 ponto cada, até 3)
- CLT confirmado
- Remoto confirmado
- Júnior/trainee confirmado

D) Bônus (+1, sem passar de 10), se tiver pelo menos um:
- Setor de saúde, meios de pagamento, educação ou fintech
- Aceita experiência de estágio, acadêmica ou projeto pessoal
- Valoriza uso de IA no desenvolvimento

## Formato da resposta
Responda SOMENTE com este JSON, sem texto antes ou depois:
{
  "eliminada": <true ou false>,
  "motivos_eliminacao": [<"Regra N: motivo", citando o número da regra que falhou, ou lista vazia>],
  "calculo": "<a conta da pontuação, ex.: A=4, B=2, C=3, D=1, total 10; se eliminada, diga a nota final até 3>",
  "nota": <número inteiro de 1 a 10, igual ao resultado do cálculo>,
  "pontos_fortes": [<até 3 frases curtas do que combina>],
  "pontos_fracos": [<até 3 frases curtas do que falta>],
  "alertas": [<informações que a vaga não deixou claras, como contratação ou modelo>],
  "resumo": "<uma frase em português simples>"
}

Use só o que está escrito na vaga. Não invente requisitos nem benefícios.

## Vaga
{TEXTO_DA_VAGA}
