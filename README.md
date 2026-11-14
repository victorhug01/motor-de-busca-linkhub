# Linkhub — busca híbrida

API de busca em links do PostgreSQL que combina BM25 e similaridade semântica com pesos iguais, adaptada dos componentes de busca de `PerguntaEvidencia_BuscaCientificaHibrida`. Os links são indexados em memória e o índice é atualizado quando os dados mudam. A primeira busca em um banco não vazio pode demorar: o modelo semântico é baixado automaticamente na primeira utilização.

Requer Python 3.11 ou 3.12 e PostgreSQL. Instale as dependências:

```sh
python -m pip install -r requirements.txt
```

Crie o banco PostgreSQL e execute nele o conteúdo de `schema.sql`. Copie `.env.example` para `.env` e ajuste `DATABASE_URL`. A aplicação apenas consulta a tabela; não executa o SQL automaticamente. Cadastre links na tabela `links` com seu processo de preferência.

Quando existir, o `.env` da raiz do projeto tem prioridade sobre `DATABASE_URL` herdada do terminal. Caracteres especiais na senha da URL precisam ser codificados: por exemplo, `@` deve ser escrito como `%40`.

Inicie a API:

```sh
python -m uvicorn linkhub.main:app
```

Consulte `GET /busca?q=aprendizado+de+maquina&limite=10`. A resposta contém `resultados`, uma lista de objetos com `id`, `url`, `titulo`, `descricao` e `pontuacao`. O limite padrão é 10 e o máximo é 100. A documentação interativa está em `/docs`.

Para executar os testes: `python -m unittest discover -s tests`.
