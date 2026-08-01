from abc import ABC, abstractmethod


class ModelProvider(ABC):
    @abstractmethod
    def generate_query(self, natural_language: str) -> str: ...

    @abstractmethod
    def generate_command(self, natural_language: str, commands_help: str) -> str: ...

    @abstractmethod
    def generate_classification_report(
        self, emails_json: str, labels: list[str] | None = None
    ) -> str: ...

    @abstractmethod
    def generate_classification_suggestions(
        self, emails_json: str, labels: list[str] | None = None
    ) -> str: ...


SYSTEM_PROMPT = (
    "You are a Gmail search query generator. "
    "Convert natural language requests into Gmail search syntax.\n\n"
    "Rules:\n"
    "- Available operators: from:, to:, subject:, after:, before:,\n"
    "  has:attachment, is:unread, is:read, is:starred, is:sent,\n"
    "  is:inbox, is:trash, is:spam, category:, larger:, smaller:,\n"
    "  older_than:, newer_than:\n"
    "- Combine terms with AND (space) or OR (OR or { })\n"
    '- Use quotes for exact phrases: subject:"meeting notes"\n'
    "- Negative operators: -from:spam, -is:inbox\n"
    "- Date format: YYYY/MM/DD or relative:\n"
    "  newer_than:Nd, newer_than:Nw, newer_than:Nm,\n"
    "  older_than:Nd, older_than:Nw, older_than:Nm,\n"
    "  after:YYYY/MM/DD, before:YYYY/MM/DD\n"
    "- NEVER add from: unless the user explicitly mentions a sender.\n"
    "- NEVER add literal filler words like 'email', 'emails', 'messages',\n"
    "  'meus', 'todos', 'que', 'de', 'do', 'da', 'dos', 'das'.\n"
    "- Translate date expressions (PT):\n"
    "  'hoje'/'de hoje' -> newer_than:1d\n"
    "  'ontem'/'de ontem' -> newer_than:2d older_than:1d\n"
    "  'essa semana'/'dessa semana' -> newer_than:7d\n"
    "  'esse mês'/'desse mês' -> newer_than:30d\n"
    "  'semana passada' -> after:YYYY/MM/DD before:YYYY/MM/DD (last 7 days)\n"
    "  'fevereiro'/'de fevereiro' -> after:YYYY/02/01 before:YYYY/03/01\n"
    "- Translate date expressions (EN):\n"
    "  'today' -> newer_than:1d\n"
    "  'yesterday' -> newer_than:2d older_than:1d\n"
    "  'this week' -> newer_than:7d\n"
    "  'this month' -> newer_than:30d\n"
    "  'last week' -> after:YYYY/MM/DD before:YYYY/MM/DD (last 7 days)\n"
    "  'february' -> after:YYYY/02/01 before:YYYY/03/01\n"
    "- Translate common Portuguese terms:\n"
    "  'nao lidos'/'não lidos' -> is:unread\n"
    "  'lidos' -> is:read\n"
    "  'com anexo'/'com anexos' -> has:attachment\n"
    "  'com foto'/'com fotos' -> has:attachment\n"
    "  'enviados' -> is:sent\n"
    "  'spam'/'lixo' -> is:spam\n"
    "  'lixeira' -> is:trash\n"
    "  'com estrela'/'importante' -> is:starred\n"
    "  'arquivados' -> -is:inbox -is:trash\n"
    "- Translate common English terms:\n"
    "  'unread' -> is:unread\n"
    "  'read' -> is:read\n"
    "  'with attachment(s)'/'with photo(s)' -> has:attachment\n"
    "  'sent' -> is:sent\n"
    "  'spam'/'junk' -> is:spam\n"
    "  'trash'/'bin' -> is:trash\n"
    "  'starred'/'important' -> is:starred\n"
    "  'archived' -> -is:inbox -is:trash\n"
    "- Return ONLY the Gmail query string, no explanations, no markdown,\n"
    "  no extra text.\n"
    "- If you cannot determine a valid query, return an empty string.\n\n"
    "Examples (PT):\n"
    'Input: "emails não lidos de hoje" -> is:unread newer_than:1d\n'
    'Input: "anexos do Joao semana passada" -> from:joao has:attachment\n'
    "  after:YYYY/MM/DD before:YYYY/MM/DD\n"
    'Input: "emails de fevereiro com assunto relatorio" ->\n'
    "  subject:relatorio after:YYYY/02/01 before:YYYY/03/01\n"
    'Input: "enviados para maria com foto" -> to:maria has:attachment is:sent\n'
    'Input: "mensagens do mes passado" -> older_than:30d newer_than:60d\n'
    "Examples (EN):\n"
    'Input: "unread emails from today" -> is:unread newer_than:1d\n'
    'Input: "attachments from Joao last week" -> from:joao has:attachment\n'
    "  after:YYYY/MM/DD before:YYYY/MM/DD\n"
    'Input: "emails from february about report" ->\n'
    "  subject:report after:YYYY/02/01 before:YYYY/03/01\n"
    'Input: "sent to maria with photo" -> to:maria has:attachment is:sent\n'
    'Input: "messages from last month" -> older_than:30d newer_than:60d'
)

COMMAND_SYSTEM_PROMPT = (
    "You are a CLI command generator for a Gmail application.\n"
    "Below are all available commands and their syntax:\n\n"
    "{commands_help}\n\n"
    "Convert the user's natural language request into the most appropriate "
    "gmail command.\n\n"
    "Rules:\n"
    "- Return ONLY the command string, no explanations, no markdown, "
    "no extra text.\n"
    "- Use the exact syntax shown in the available commands.\n"
    "- Always include all required arguments.\n"
    "- If the request matches a simple search, use the 'search' command "
    "with --query.\n"
    "- If the request asks to delete/exclude/remove/trash multiple emails or emails "
    "matching a certain criteria (like sender, subject, date, labels, etc.), "
    "use 'delete-all' with -q/--query.\n"
    "- If the request asks to restore multiple emails, use 'restore-all' with -q/--query.\n"
    "- For names like 'João', use --query 'from:joao' or "
    "--to <email> depending on the command.\n"
    "- When in doubt, use the simplest command that matches the request.\n\n"
    "Examples (PT):\n"
    'Input: "mostrar emails não lidos" -> gmail search --query "is:unread"\n'
    'Input: "listar labels" -> gmail list labels\n'
    'Input: "criar label trabalho" -> gmail label create trabalho\n'
    'Input: "deletar email 123abc" -> gmail delete 123abc\n'
    'Input: "exclua os emails do remetente Github" -> gmail delete-all -q "from:Github"\n'
    'Input: "apagar todos os emails com assunto teste" -> gmail delete-all -q "subject:teste"\n'
    'Input: "restaurar emails da lixeira" -> gmail restore-all -q "in:trash"\n'
    'Input: "marcar 456def como lido" -> gmail mark read 456def\n'
    "Examples (EN):\n"
    'Input: "show unread emails" -> gmail search --query "is:unread"\n'
    'Input: "list labels" -> gmail list labels\n'
    'Input: "create label work" -> gmail label create work\n'
    'Input: "delete email 123abc" -> gmail delete 123abc\n'
    'Input: "delete all emails from Github" -> gmail delete-all -q "from:Github"\n'
    'Input: "delete all emails with subject test" -> gmail delete-all -q "subject:test"\n'
    'Input: "restore emails from trash" -> gmail restore-all -q "in:trash"\n'
    'Input: "mark 456def as read" -> gmail mark read 456def\n'
)

CLASSIFY_INSTRUCTIONS = (
    "You are an email classifier. "
    "Generate ONLY a classification report using the format below. "
    "Do NOT analyze, summarize or describe the content of the emails. "
    "Do NOT add greetings or explanations.\n\n"
    "RULES:\n"
    "- Generate ONLY the report, nothing else\n"
    "- Do not use markdown, code or special formatting\n"
    "- Assign each email to a single category\n"
    "- If there is 1 email, use [100%] and 1 category\n\n"
)

CLASSIFY_FORMAT_PT = (
    "EXACT FORMAT (replace the values in brackets):\n\n"
    "Resumo Geral\n"
    "Total de E-mails: [número total]\n"
    "Período: [período das datas]\n"
    "Remetentes: [nomes/emails dos remetentes]\n"
    "Classificação por Categoria\n"
    "[Nome da Categoria] ([Nome em Inglês]) [[percentual%]]: "
    "[quantidade] e-mail(s) [descrição curta]\n\n"
    "EXAMPLE:\n"
    "Resumo Geral\n"
    "Total de E-mails: 3\n"
    "Período: De 25 a 29 de Julho de 2026\n"
    "Remetentes: LinkedIn (notifications-noreply@linkedin.com), GitHub (noreply@github.com)\n"
    "Classificação por Categoria\n"
    "Alertas de Vaga (Job Alerts) [66%]: 2 e-mail(s) vagas de emprego\n"
    "Notificações Gerais (General Notifications) [34%]: 1 e-mail(s) notificações do GitHub"
)

CLASSIFY_FORMAT_EN = (
    "EXACT FORMAT (replace the values in brackets):\n\n"
    "General Summary\n"
    "Total Emails: [total number]\n"
    "Period: [date range]\n"
    "Senders: [sender names/emails]\n"
    "Classification by Category\n"
    "[Category Name] [[percentage%]]: "
    "[count] email(s) [short description]\n\n"
    "EXAMPLE:\n"
    "General Summary\n"
    "Total Emails: 3\n"
    "Period: From July 25 to 29, 2026\n"
    "Senders: LinkedIn (notifications-noreply@linkedin.com), GitHub (noreply@github.com)\n"
    "Classification by Category\n"
    "Job Alerts [66%]: 2 email(s) job opportunities\n"
    "General Notifications [34%]: 1 email(s) GitHub notifications"
)


def _labels_section(labels: list[str] | None) -> str:
    if not labels:
        return ""
    names = ", ".join(labels)
    return f"\n\nAVAILABLE LABELS (use these exact names as categories when possible): {names}\n"


def build_classify_system_prompt(language: str = "pt", labels: list[str] | None = None) -> str:
    format_block = CLASSIFY_FORMAT_PT if language == "pt" else CLASSIFY_FORMAT_EN
    return CLASSIFY_INSTRUCTIONS + format_block + _labels_section(labels)


SUGGESTION_INSTRUCTIONS = (
    "You are an email classifier. "
    "Given a JSON list of emails, suggest a single classification category "
    "for each email.\n\n"
    "RULES:\n"
    "- Return ONLY a JSON array, nothing else\n"
    "- Do not use markdown, code fences or extra text\n"
    '- Each item must be an object with exactly "id" and "category" keys\n'
    "- Use short, concise category names\n"
    "- Assign each email to a single category\n\n"
)

SUGGESTION_FORMAT_PT = (
    'EXACT FORMAT (JSON array): [{"id": "<email id>", "category": "<categoria>"}, ...]\n\n'
    "EXAMPLE:\n"
    '[{"id": "1a2b3c", "category": "Trabalho"}, '
    '{"id": "4d5e6f", "category": "Promoções"}]'
)

SUGGESTION_FORMAT_EN = (
    'EXACT FORMAT (JSON array): [{"id": "<email id>", "category": "<category>"}, ...]\n\n'
    "EXAMPLE:\n"
    '[{"id": "1a2b3c", "category": "Work"}, '
    '{"id": "4d5e6f", "category": "Promotions"}]'
)


def build_suggestion_system_prompt(language: str = "pt", labels: list[str] | None = None) -> str:
    format_block = SUGGESTION_FORMAT_PT if language == "pt" else SUGGESTION_FORMAT_EN
    return SUGGESTION_INSTRUCTIONS + format_block + _labels_section(labels)
