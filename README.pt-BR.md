# gmail-cli

<p>
  <img src="https://img.shields.io/badge/vers%C3%A3o-v1.1.0--alpha-blue" alt="Versão">
  <img src="https://img.shields.io/badge/licen%C3%A7a-MIT-green" alt="Licença">
  <img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python">
  <img src="https://img.shields.io/badge/testes-184%20passando-brightgreen" alt="Testes">
  <img src="https://img.shields.io/badge/cobertura-100%25-brightgreen" alt="Cobertura">
</p>

**Idiomas:** [English](README.md) | [Português](#)

CLI para gerenciar e-mail, labels, rascunhos e anexos do Gmail via terminal.

## Funcionalidades

- **Listar** e-mails, labels e rascunhos com filtros
- **Exibir** detalhes de uma mensagem (cabeçalhos e corpo)
- **Enviar** e-mail com cc, bcc e anexos
- **Gerenciar labels** — criar e deletar
- **Marcar** como lido / não lido
- **Mover para lixeira**, **deletar permanentemente** e **restaurar**
- **Operações em lote** — deletar/restaurar múltiplos e-mails por query
- **Rascunhos** — criar, enviar e deletar
- **Baixar anexos** de uma mensagem

## Instalação

```bash
pip install .
```

Desenvolvimento:

```bash
pip install -e ".[test,dev]"
```

## Configuração

1. Acesse [console.cloud.google.com](https://console.cloud.google.com/)
2. Crie um projeto e ative a **Gmail API**
3. Em **Credenciais**, crie uma credencial OAuth 2.0 do tipo "Aplicativo para desktop"
4. Baixe o JSON e salve como `~/.gmail_cli_credentials.json`
5. Execute qualquer comando para autenticar na primeira vez

## Uso

### Listar e-mails

```bash
gmail list messages
gmail list messages -q "from:joao@email.com"
gmail list messages -l INBOX --max 50
```

### Buscar

```bash
gmail search -q "assunto:reunião"
```

### Exibir detalhes

```bash
gmail show <message_id>
```

### Enviar e-mail

```bash
gmail send message -t "destino@email.com" -s "Assunto" -b "Corpo"
gmail send message -t "a@b.com" -s "Oi" -b "Hello" --cc "cc@b.com" --bcc "bcc@b.com" -a ./arquivo.pdf
```

### Labels

```bash
gmail list labels
gmail label create "MinhaLabel"
gmail label delete <label_id>
```

### Marcar

```bash
gmail mark read <message_id>
gmail mark unread <message_id>
```

### Deletar / Restaurar

```bash
gmail delete <message_id>
gmail delete --permanent <message_id>
gmail restore <message_id>

gmail delete-all -q "from:spam"
gmail restore-all -q "in:trash"
```

### Rascunhos

```bash
gmail list drafts
gmail draft create -t "a@b.com" -s "Rascunho" -b "Corpo" --cc "c@c.com"
gmail draft send <draft_id>
gmail draft delete <draft_id>
```

### Anexos

```bash
gmail attachments <message_id>
gmail attachments <message_id> -o ./downloads
```

### Comando em Linguagem Natural

```bash
# Gera e pede confirmação para executar o comando (padrão)
gmail prompt "listar minhas labels"

# Executa diretamente sem pedir confirmação (yes por padrão)
gmail prompt "marcar email 123abc como lido" --yes
gmail prompt "deletar e-mails do Joao" -y
```

### Configuração dos Provedores

```bash
# Ver configuração atual
gmail config show

# Usar OpenAI
gmail config set --provider openai --api-key sk-xxxxx

# Usar Google Gemini
gmail config set --provider gemini --api-key g-xxxxx

# Usar Ollama local (padrão)
gmail config set --provider ollama --ollama-url http://localhost:11434

# Customizar modelo por provedor
gmail config set --openai-model gpt-4 --ollama-model llama3.1
```

A configuração é salva em `~/.gmail_cli_config.json`.
Variáveis de ambiente sobrescrevem o arquivo: `GMAIL_CLI_PROVIDER`, `GMAIL_CLI_API_KEY`, `GMAIL_CLI_OLLAMA_URL`, `GMAIL_CLI_OLLAMA_MODEL`, `GMAIL_CLI_OPENAI_MODEL`, `GMAIL_CLI_GEMINI_MODEL`.

## Estrutura do Projeto

```
gmail-cli/
├── src/
│   └── gmail_cli/
│       ├── __init__.py    # API pública com __all__
│       ├── __main__.py    # python -m gmail_cli
│       ├── auth.py        # Autenticação OAuth 2.0 (AuthService)
│       ├── cli.py         # Interface CLI (click)
│       ├── formatter.py   # Formatação de saída (CliFormatter)
│       ├── gmail_client.py# Wrapper da API Gmail (GmailClient)
│       ├── models.py      # Dataclasses: Message, Label, Draft
│       └── providers/     # Provedores LLM (OpenAI, Gemini, Ollama)
├── tests/
│   ├── conftest.py        # Fixtures compartilhadas
│   ├── test_auth.py
│   ├── test_cli.py        # Testes via Click CliRunner
│   ├── test_formatter.py
│   ├── test_gmail_client.py
│   ├── test_models.py
│   └── test_providers.py
├── pyproject.toml          # Config (ruff, pytest, packaging)
├── README.md               # English version
└── README.pt-BR.md         # Este arquivo
```

## Testes

```bash
pytest                    # 184 testes
pytest --cov=             # Cobertura (100%)
```

## Qualidade

```bash
ruff check .              # Linter (0 issues)
ruff format --check .     # Formatação
bandit -r src/gmail_cli/  # SAST
```
