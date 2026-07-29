# gmail-cli

**Versão:** `v1.0.0-alpha`
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
│       └── models.py      # Dataclasses: Message, Label, Draft
├── tests/
│   ├── conftest.py        # Fixtures compartilhadas
│   ├── test_auth.py
│   ├── test_cli.py        # Testes via Click CliRunner
│   ├── test_formatter.py
│   ├── test_gmail_client.py
│   └── test_models.py
├── pyproject.toml          # Config (ruff, pytest, packaging)
├── README.md               # English version
└── README.pt-BR.md         # Este arquivo
```

## Testes

```bash
pytest                    # 134 testes
pytest --cov=             # Cobertura (100%)
```

## Qualidade

```bash
ruff check .              # Linter (0 issues)
ruff format --check .     # Formatação
bandit -r src/gmail_cli/  # SAST
```
