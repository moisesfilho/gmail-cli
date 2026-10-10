# gmail-cli Code Map

CLI Python para gerenciar mensagens, marcadores, rascunhos e anexos do Gmail,
com classificacao de emails por provedores de modelos de linguagem.

## Estrutura

| Caminho | Responsabilidade |
| --- | --- |
| `src/gmail_cli/cli.py` | Comandos Click standalone/JSON harness, processamento de prompts, classificacao e exportacao. |
| `src/gmail_cli/cli.py` (`cli`) | Grupo raiz exposto pelo comando instalado `gmail`. |
| `src/gmail_cli/__main__.py` | Execucao do CLI como modulo Python. |
| `src/gmail_cli/auth.py` | Autenticacao OAuth do Google e ciclo de vida das credenciais. |
| `src/gmail_cli/gmail_client.py` | Operacoes da API do Gmail e tratamento de erros do cliente. |
| `src/gmail_cli/models.py` | Modelos de dados `Message`, `Label` e `Draft`. |
| `src/gmail_cli/formatter.py` | Formata saidas para exibicao no terminal. |
| `src/gmail_cli/labels_cache.py` | Cache local de marcadores e atualizacao a partir do Gmail. |
| `src/gmail_cli/logging_utils.py` | Configuracao do logger e retencao dos logs da aplicacao. |
| `src/gmail_cli/providers/` | Configuracao, interface e implementacoes dos provedores de LLM. |
| `src/gmail_cli/providers/base.py` | Interface dos provedores e prompts de classificacao/sugestao. |
| `src/gmail_cli/providers/config.py` | Leitura e persistencia da configuracao do provedor. |
| `src/gmail_cli/providers/{openai,gemini,ollama,opencode_go}_provider.py` | Adaptadores para OpenAI, Gemini, Ollama e OpenCode Go; este último envia identificacao do cliente e ID de sessao exigidos pela API. |
| `tests/` | Testes automatizados de CLI, autenticacao, Gmail, modelos, provedores, formatacao, cache e logging. |
| `tests/conftest.py` | Fixtures compartilhadas dos testes. |
| `Pendencias.md` | Pendencias conhecidas do projeto. |
| `README.md`, `README.pt-BR.md` | Documentacao de uso em ingles e portugues. |
| `pyproject.toml` | Metadados, dependencias, entry point e configuracao de pytest, cobertura e Ruff. |

## Stack

Python >=3.10, Click, Google API Client, Google Auth HTTP/OAuth, pytest,
pytest-mock, pytest-cov, Ruff, mypy e Bandit. Os provedores de LLM incluem
OpenAI, Gemini, Ollama e OpenCode Go.

## Validacao

O entry point e `gmail = gmail_cli.cli:cli`. O pytest usa `tests/` e configura
`src` no `PYTHONPATH`. Comandos documentados:

```bash
pytest
pytest --cov=
ruff check .
ruff format --check .
bandit -r src/gmail_cli/
```

`.coverage`, `coverage.xml`, `.pytest_cache/` e `.ruff_cache/` sao artefatos
gerados.
