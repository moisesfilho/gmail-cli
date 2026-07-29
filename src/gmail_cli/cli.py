#!/usr/bin/env python3
import click

from .auth import AuthError, AuthService
from .formatter import CliFormatter
from .gmail_client import GmailClient, GmailError
from .providers import create_provider, load_config, save_config


def _create_client():
    return GmailClient(AuthService().get_service())


fmt = CliFormatter()


@click.group()
def cli():
    pass


@cli.command()
def auth_url():
    """Exibe instruções para configurar a autenticação OAuth 2.0."""
    fmt.info(
        "Para usar este CLI, você precisa de um arquivo de credenciais OAuth 2.0.\n\n"
        "1. Acesse https://console.cloud.google.com/\n"
        "2. Crie um projeto e ative a Gmail API\n"
        "3. Em 'Credenciais', crie uma credencial OAuth 2.0 do tipo 'Aplicativo para desktop'\n"
        "4. Baixe o JSON e salve como ~/.gmail_cli_credentials.json\n"
        "5. Execute qualquer comando (ex: 'gmail list') para autenticar"
    )


@cli.group(name="list")
def list_cmd():
    """Listar recursos."""
    pass


@list_cmd.command("messages")
@click.option("--query", "-q", default="", help="Filtro (ex: 'from:foo@bar.com')")
@click.option("--max", "max_results", default=20, help="Número máximo")
@click.option("--label", "-l", multiple=True, help="Filtrar por label")
def list_messages(query, max_results, label):
    """Listar e-mails."""
    try:
        client = _create_client()
        msgs = client.list_messages(
            query=query, max_results=max_results, label_ids=list(label) or None
        )
        if not msgs:
            fmt.info("Nenhuma mensagem encontrada.")
            return
        fmt.list_messages(msgs)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@list_cmd.command("labels")
def list_labels():
    """Listar todas as labels."""
    try:
        client = _create_client()
        labels = client.list_labels()
        if not labels:
            fmt.info("Nenhuma label encontrada.")
            return
        fmt.list_labels(labels)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@list_cmd.command("drafts")
@click.option("--max", "max_results", default=20, help="Número máximo")
def list_drafts(max_results):
    """Listar rascunhos."""
    try:
        client = _create_client()
        drafts = client.list_drafts(max_results=max_results)
        if not drafts:
            fmt.info("Nenhum rascunho encontrado.")
            return
        fmt.list_drafts(drafts)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
@click.option("--body/--no-body", default=True, help="Exibir corpo")
def show(message_id, body):
    """Exibir detalhes de um e-mail."""
    try:
        client = _create_client()
        msg = client.get_message(message_id)
        fmt.show_message(msg)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def send():
    """Enviar e-mail."""
    pass


@send.command("message")
@click.option("--to", "-t", required=True, help="Destinatário")
@click.option("--subject", "-s", required=True, help="Assunto")
@click.option("--body", "-b", required=True, help="Corpo")
@click.option("--cc", help="Cc")
@click.option("--bcc", help="Bcc")
@click.option("--attach", "-a", multiple=True, help="Anexo (repetir)")
def send_message(to, subject, body, cc, bcc, attach):  # noqa: PLR0913, PLR0917
    """Enviar um novo e-mail."""
    try:
        client = _create_client()
        result = client.send_message(
            to, subject, body, cc=cc, bcc=bcc, attachments=list(attach) or None
        )
        fmt.info(f"E-mail enviado! ID: {result['id']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def label():
    """Gerenciar labels."""
    pass


@label.command("create")
@click.argument("name")
def create_label(name):
    """Criar uma nova label."""
    try:
        client = _create_client()
        result = client.create_label(name)
        fmt.info(f"Label criada: {result['id']} - {result['name']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@label.command("delete")
@click.argument("label_id")
def delete_label(label_id):
    """Deletar uma label."""
    try:
        client = _create_client()
        client.delete_label(label_id)
        fmt.info(f"Label {label_id} deletada.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def mark():
    """Marcar mensagens."""
    pass


@mark.command("read")
@click.argument("message_id")
def mark_read(message_id):
    """Marcar como lido."""
    try:
        client = _create_client()
        client.modify_message(message_id, remove_labels=["UNREAD"])
        fmt.info(f"Mensagem {message_id} marcada como lida.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@mark.command("unread")
@click.argument("message_id")
def mark_unread(message_id):
    """Marcar como não lido."""
    try:
        client = _create_client()
        client.modify_message(message_id, add_labels=["UNREAD"])
        fmt.info(f"Mensagem {message_id} marcada como não lida.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
@click.option("--permanent", is_flag=True, help="Deletar permanentemente")
@click.confirmation_option(prompt="Tem certeza que deseja deletar este e-mail?")
def delete(message_id, permanent):
    """Mover e-mail para lixeira (ou --permanent)."""
    try:
        client = _create_client()
        if permanent:
            client.delete_message(message_id)
            fmt.info(f"Mensagem {message_id} deletada permanentemente.")
        else:
            client.trash_message(message_id)
            fmt.info(f"Mensagem {message_id} movida para a lixeira.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", required=True, help="Filtro de busca")
@click.option("--permanent", is_flag=True, help="Deletar permanentemente")
@click.confirmation_option(prompt="Tem certeza que deseja deletar todos os e-mails?")
def delete_all(query, permanent):
    """Deletar e-mails em lote."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, max_results=500)
        if not msgs:
            fmt.info("Nenhum e-mail encontrado.")
            return
        fmt.info(f"Deletando {len(msgs)} e-mail(s)...")
        for m in msgs:
            if permanent:
                client.delete_message(m.id)
            else:
                client.trash_message(m.id)
            fmt.info(f"  {m.id[:8]} {m.subject[:60]}")
        fmt.info("Concluído.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
def restore(message_id):
    """Restaurar e-mail da lixeira."""
    try:
        client = _create_client()
        client.untrash_message(message_id)
        fmt.info(f"Mensagem {message_id} restaurada da lixeira.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", required=True, help="Filtro de busca")
@click.confirmation_option(prompt="Tem certeza que deseja restaurar todos os e-mails?")
def restore_all(query):
    """Restaurar e-mails da lixeira em lote."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, label_ids=["TRASH"], max_results=500)
        if not msgs:
            fmt.info("Nenhum e-mail encontrado na lixeira.")
            return
        fmt.info(f"Restaurando {len(msgs)} e-mail(s)...")
        for m in msgs:
            client.untrash_message(m.id)
            fmt.info(f"  {m.id[:8]} {m.subject[:60]}")
        fmt.info("Concluído.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def draft():
    """Gerenciar rascunhos."""
    pass


@draft.command("create")
@click.option("--to", "-t", required=True, help="Destinatário")
@click.option("--subject", "-s", required=True, help="Assunto")
@click.option("--body", "-b", required=True, help="Corpo")
@click.option("--cc", help="Cc")
@click.option("--bcc", help="Bcc")
def create_draft(to, subject, body, cc, bcc):
    """Criar rascunho."""
    try:
        client = _create_client()
        result = client.create_draft(to, subject, body, cc=cc, bcc=bcc)
        fmt.info(f"Rascunho criado! ID: {result['id']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@draft.command("send")
@click.argument("draft_id")
def send_draft(draft_id):
    """Enviar rascunho."""
    try:
        client = _create_client()
        result = client.send_draft(draft_id)
        fmt.info(f"Rascunho enviado! ID: {result['id']}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@draft.command("delete")
@click.argument("draft_id")
def delete_draft(draft_id):
    """Deletar rascunho."""
    try:
        client = _create_client()
        client.delete_draft(draft_id)
        fmt.info(f"Rascunho {draft_id} deletado.")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.argument("message_id")
@click.option("--output", "-o", default="./attachments", help="Diretório")
def attachments(message_id, output):
    """Baixar anexos."""
    try:
        client = _create_client()
        files = client.download_attachments(message_id, output_dir=output)
        if not files:
            fmt.info("Nenhum anexo encontrado.")
            return
        for f in files:
            fmt.info(f"Anexo salvo: {f}")
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.command()
@click.option("--query", "-q", default="", help="Termo de busca")
@click.option("--max", "max_results", default=20, help="Número máximo")
def search(query, max_results):
    """Buscar e-mails."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, max_results=max_results)
        if not msgs:
            fmt.info("Nenhum e-mail encontrado.")
            return
        fmt.list_messages(msgs)
    except (AuthError, GmailError) as e:
        fmt.error(str(e))


@cli.group()
def config():
    """Gerenciar configuração dos provedores de IA."""
    pass


@config.command("show")
def config_show():
    """Exibir configuração atual."""
    cfg = load_config()
    fmt.info(f"Provedor: {cfg.provider}")
    if cfg.api_key:
        fmt.info(f"API Key: {cfg.api_key[:8]}...")
    if cfg.provider == "ollama":
        fmt.info(f"Ollama URL: {cfg.ollama_url}")
        fmt.info(f"Modelo: {cfg.ollama_model}")
    elif cfg.provider == "openai":
        fmt.info(f"Modelo: {cfg.openai_model}")
    elif cfg.provider == "gemini":
        fmt.info(f"Modelo: {cfg.gemini_model}")


@config.command("set")
@click.option("--provider", type=click.Choice(["openai", "gemini", "ollama"]))
@click.option("--api-key")
@click.option("--ollama-url", default="http://localhost:11434")
@click.option("--ollama-model", default="llama3.2")
@click.option("--openai-model", default="gpt-4o-mini")
@click.option("--gemini-model", default="gemini-2.0-flash")
def config_set(**kwargs):
    """Definir configuração."""
    cfg = load_config()
    if kwargs.get("provider"):
        cfg.provider = kwargs["provider"]
    if kwargs.get("api_key"):
        cfg.api_key = kwargs["api_key"]
    cfg.ollama_url = kwargs.get("ollama_url", cfg.ollama_url)
    cfg.ollama_model = kwargs.get("ollama_model", cfg.ollama_model)
    cfg.openai_model = kwargs.get("openai_model", cfg.openai_model)
    cfg.gemini_model = kwargs.get("gemini_model", cfg.gemini_model)
    save_config(cfg)
    fmt.info("Configuração salva em ~/.gmail_cli_config.json")


@cli.command()
@click.argument("text", nargs=-1, required=True)
@click.option("--run", "-r", is_flag=True, help="Executar a busca após gerar a query")
@click.option("--max", "max_results", default=20, help="Número máximo de resultados")
def query(text, run, max_results):
    """Converter linguagem natural em query do Gmail.

    Exemplos:

      gmail query "emails do Joao da semana passada"

      gmail query "anexos de fevereiro com assunto relatorio" --run
    """
    try:
        cfg = load_config()
        provider = create_provider(cfg)
        natural = " ".join(text)
        fmt.info(f"Gerando query para: {natural}")
        generated = provider.generate_query(natural)
        if not generated:
            fmt.error("Não foi possível gerar uma query.")
            return
        fmt.info(f"\nQuery gerada: {generated}\n")
        if run:
            client = _create_client()
            msgs = client.list_messages(query=generated, max_results=max_results)
            if not msgs:
                fmt.info("Nenhum resultado encontrado.")
                return
            fmt.list_messages(msgs)
    except (AuthError, GmailError, ValueError, ConnectionError, TimeoutError) as e:
        fmt.error(str(e))


if __name__ == "__main__":  # pragma: no cover
    cli()
