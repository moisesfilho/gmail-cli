from abc import ABC, abstractmethod


class ModelProvider(ABC):
    @abstractmethod
    def generate_query(self, natural_language: str) -> str: ...

    @abstractmethod
    def generate_command(self, natural_language: str, commands_help: str) -> str: ...

    @abstractmethod
    def generate_classification_report(self, emails_json: str) -> str: ...


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
    "- Translate date expressions:\n"
    "  'hoje'/'de hoje' -> newer_than:1d\n"
    "  'ontem'/'de ontem' -> newer_than:2d older_than:1d\n"
    "  'essa semana'/'dessa semana' -> newer_than:7d\n"
    "  'esse mês'/'desse mês' -> newer_than:30d\n"
    "  'semana passada' -> after:YYYY/MM/DD before:YYYY/MM/DD (last 7 days)\n"
    "  'fevereiro'/'de fevereiro' -> after:YYYY/02/01 before:YYYY/03/01\n"
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
    "- Return ONLY the Gmail query string, no explanations, no markdown,\n"
    "  no extra text.\n"
    "- If you cannot determine a valid query, return an empty string.\n\n"
    "Examples:\n"
    'Input: "emails não lidos de hoje" -> is:unread newer_than:1d\n'
    'Input: "anexos do Joao semana passada" -> from:joao has:attachment\n'
    "  after:YYYY/MM/DD before:YYYY/MM/DD\n"
    'Input: "emails de fevereiro com assunto relatorio" ->\n'
    "  subject:relatorio after:YYYY/02/01 before:YYYY/03/01\n"
    'Input: "enviados para maria com foto" -> to:maria has:attachment is:sent\n'
    'Input: "mensagens do mes passado" -> older_than:30d newer_than:60d'
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
    "Examples:\n"
    'Input: "mostrar emails não lidos" -> gmail search --query "is:unread"\n'
    'Input: "listar labels" -> gmail list labels\n'
    'Input: "criar label trabalho" -> gmail label create trabalho\n'
    'Input: "deletar email 123abc" -> gmail delete 123abc\n'
    'Input: "exclua os emails do remetente Github" -> gmail delete-all -q "from:Github"\n'
    'Input: "apagar todos os emails com assunto teste" -> gmail delete-all -q "subject:teste"\n'
    'Input: "restaurar emails da lixeira" -> gmail restore-all -q "in:trash"\n'
    'Input: "marcar 456def como lido" -> gmail mark read 456def\n'
)


CLASSIFY_SYSTEM_PROMPT = (
    "Você é um classificador de e-mails. "
    "Gere APENAS um relatório de classificação com o formato abaixo. "
    "NÃO analise, resuma ou descreva o conteúdo dos e-mails. "
    "NÃO adicione saudações ou explicações.\n\n"
    "FORMATO EXATO (substitua os valores entre colchetes):\n\n"
    "Resumo Geral\n"
    "Total de E-mails: [número total]\n"
    "Período: [período das datas]\n"
    "Remetentes: [nomes/emails dos remetentes]\n"
    "Classificação por Categoria\n"
    "[Nome da Categoria] ([Nome em Inglês]) [[percentual%]]: "
    "[quantidade] e-mail(s) [descrição curta]\n\n"
    "EXEMPLO:\n"
    "Resumo Geral\n"
    "Total de E-mails: 3\n"
    "Período: De 25 a 29 de Julho de 2026\n"
    "Remetentes: LinkedIn (notifications-noreply@linkedin.com), GitHub (noreply@github.com)\n"
    "Classificação por Categoria\n"
    "Alertas de Vaga (Job Alerts) [66%]: 2 e-mail(s) vagas de emprego\n"
    "Notificações Gerais (General Notifications) [34%]: 1 e-mail(s) notificações do GitHub\n\n"
    "REGRAS:\n"
    "- Gere SOMENTE o relatório, nada mais\n"
    "- Não use markdown, código ou formatação especial\n"
    "- Atribua cada e-mail a uma única categoria\n"
    "- Se houver 1 e-mail, use [100%] e 1 categoria"
)


