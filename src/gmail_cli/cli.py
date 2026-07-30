#!/usr/bin/env python3
import json
import os
import shlex

import click

from .auth import AuthError, AuthService
from .formatter import CliFormatter
from .gmail_client import GmailClient, GmailError
from .models import Message
from .providers import create_provider, load_config, save_config


def _create_client():
    return GmailClient(AuthService().get_service())


def _export_messages(messages, export_path: str):
    is_single = isinstance(messages, Message)
    msgs_list = [messages] if is_single else messages

    ext = os.path.splitext(export_path)[1].lower()

    if ext == ".json":
        data = []
        for m in msgs_list:
            data.append(
                {
                    "id": m.id,
                    "thread_id": m.thread_id,
                    "from": m.from_,
                    "to": m.to,
                    "subject": m.subject,
                    "date": m.date,
                    "label_ids": m.label_ids,
                    "body": m.body,
                }
            )
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(
                data[0] if (is_single and len(data) == 1) else data,
                f,
                indent=2,
                ensure_ascii=False,
            )

    elif ext == ".jsonl":
        with open(export_path, "w", encoding="utf-8") as f:
            for m in msgs_list:
                line_data = {
                    "id": m.id,
                    "thread_id": m.thread_id,
                    "from": m.from_,
                    "to": m.to,
                    "subject": m.subject,
                    "date": m.date,
                    "label_ids": m.label_ids,
                    "body": m.body,
                }
                f.write(json.dumps(line_data, ensure_ascii=False) + "\n")

    elif ext == ".md":
        with open(export_path, "w", encoding="utf-8") as f:
            for i, m in enumerate(msgs_list):
                if i > 0:
                    f.write("\n\n---\n\n")
                f.write(f"# Email: {m.subject}\n\n")
                f.write(f"- **ID:** {m.id}\n")
                f.write(f"- **Thread ID:** {m.thread_id}\n")
                f.write(f"- **From:** {m.from_}\n")
                f.write(f"- **To:** {m.to}\n")
                f.write(f"- **Date:** {m.date}\n")
                labels_str = ", ".join(m.label_ids)
                f.write(f"- **Labels:** {labels_str}\n\n")
                f.write("## Body\n\n")
                f.write(m.body or "(No Body)")

    else:
        # Default to JSON
        _export_messages(messages, export_path + ".json")


def _classify_messages(client, msgs):
    full_msgs = []
    with click.progressbar(msgs, label="Carregando dados dos e-mails") as bar:
        for m in bar:
            full_msgs.append(client.get_message(m.id))
    data = []
    for m in full_msgs:
        data.append(
            {
                "id": m.id,
                "thread_id": m.thread_id,
                "from": m.from_,
                "to": m.to,
                "subject": m.subject,
                "date": m.date,
                "label_ids": m.label_ids,
                "body": m.body,
            }
        )
    emails_json = json.dumps(data, ensure_ascii=False)
    config = load_config()
    provider = create_provider(config)
    report = provider.generate_classification_report(emails_json)
    click.echo(report)


fmt = CliFormatter()


@click.group()
def cli():
    pass


@cli.group()
def auth():
    """Gerenciar autenticação OAuth 2.0."""
    pass


@auth.command("login")
def auth_login():
    """Autenticar no Gmail (abre o navegador)."""
    AuthService().login()
    fmt.info("Autenticação concluída! Token salvo em ~/.gmail-cli/token.json")


@auth.command("logout")
def auth_logout():
    """Remover token de autenticação."""
    svc = AuthService()
    svc.revoke()
    fmt.info("Token removido.")


@auth.command("status")
def auth_status():
    """Verificar status da autenticação."""
    svc = AuthService()
    if svc._load_credentials():
        fmt.info("Autenticado — token encontrado em ~/.gmail-cli/token.json")
    elif os.path.exists(svc.CREDENTIALS_FILE):
        fmt.info("Credenciais encontradas, mas token ainda não gerado.")
        fmt.info("Execute 'gmail auth login' para autenticar.")
    else:
        fmt.info("Nenhuma credencial encontrada.")
        fmt.info("Execute 'gmail auth login' para configurar.")


@cli.group(name="list")
def list_cmd():
    """Listar recursos."""
    pass


@list_cmd.command("messages")
@click.option("--query", "-q", default="", help="Filtro (ex: 'from:foo@bar.com')")
@click.option("--max", "max_results", default=20, help="Número máximo")
@click.option("--label", "-l", multiple=True, help="Filtrar por label")
@click.option("--export", "-e", help="Caminho do arquivo para exportação (.json, .jsonl, .md)")
@click.option("--classify", "-c", is_flag=True, help="Gerar relatório de classificação via IA")
def list_messages(query, max_results, label, export, classify):
    """Listar e-mails."""
    try:
        client = _create_client()
        msgs = client.list_messages(
            query=query, max_results=max_results, label_ids=list(label) or None
        )
        if not msgs:
            fmt.info("Nenhuma mensagem encontrada.")
            return
        if classify:
            _classify_messages(client, msgs)
        elif export:
            full_msgs = []
            with click.progressbar(msgs, label="Carregando dados dos e-mails") as bar:
                for m in bar:
                    full_msgs.append(client.get_message(m.id))
            _export_messages(full_msgs, export)
            fmt.info(f"Dados exportados com sucesso para: {export}")
        else:
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
@click.option("--export", "-e", help="Caminho do arquivo para exportação (.json, .jsonl, .md)")
def show(message_id, body, export):
    """Exibir detalhes de um e-mail."""
    try:
        client = _create_client()
        msg = client.get_message(message_id)
        if export:
            _export_messages(msg, export)
            fmt.info(f"Dados exportados com sucesso para: {export}")
        else:
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
        msgs = client.list_messages(query=query, max_results=None)
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
        msgs = client.list_messages(query=query, label_ids=["TRASH"], max_results=None)
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
@click.option("--export", "-e", help="Caminho do arquivo para exportação (.json, .jsonl, .md)")
@click.option("--classify", "-c", is_flag=True, help="Gerar relatório de classificação via IA")
def search(query, max_results, export, classify):
    """Buscar e-mails."""
    try:
        client = _create_client()
        msgs = client.list_messages(query=query, max_results=max_results)
        if not msgs:
            fmt.info("Nenhum e-mail encontrado.")
            return
        if classify:
            _classify_messages(client, msgs)
        elif export:
            full_msgs = []
            with click.progressbar(msgs, label="Carregando dados dos e-mails") as bar:
                for m in bar:
                    full_msgs.append(client.get_message(m.id))
            _export_messages(full_msgs, export)
            fmt.info(f"Dados exportados com sucesso para: {export}")
        else:
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
    elif cfg.provider == "opencode_go":
        fmt.info(f"Modelo: {cfg.opencode_go_model}")


@config.command("set")
@click.option("--provider", type=click.Choice(["openai", "gemini", "ollama", "opencode_go"]))
@click.option("--api-key")
@click.option("--ollama-url", default="http://localhost:11434")
@click.option("--ollama-model", default="llama3.2")
@click.option("--openai-model", default="gpt-4o-mini")
@click.option("--gemini-model", default="gemini-2.0-flash")
@click.option("--opencode-go-model", default="deepseek-v4-flash")
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
    cfg.opencode_go_model = kwargs.get("opencode_go_model", cfg.opencode_go_model)
    save_config(cfg)
    fmt.info("Configuração salva em ~/.gmail-cli/config.json")


def _build_commands_help(ctx: click.Context) -> str:
    def build_help(cmd, ctx, path=None):
        if path is None:
            path = []
        name = "gmail" if not path else cmd.name
        current_path = [*path, name]
        full_name = " ".join(current_path)

        sub_ctx = ctx if not path else click.Context(cmd, info_name=name, parent=ctx)

        lines = []
        lines.append(f"Command: {full_name}")
        help_text = cmd.get_help(sub_ctx)
        lines.append(help_text)
        lines.append("-" * 40)

        if isinstance(cmd, click.Group):
            for sub_name, sub_cmd in cmd.commands.items():
                if sub_name == "prompt":
                    continue
                sub_help = build_help(sub_cmd, sub_ctx, current_path)
                if sub_help:
                    lines.append(sub_help)

        return "\n".join(lines)

    root_ctx = ctx.find_root()
    return build_help(root_ctx.command, root_ctx)


@cli.command()
@click.argument("text", nargs=-1, required=True)
@click.option("--yes", "-y", is_flag=True, help="Executar diretamente sem pedir confirmação")
@click.pass_context
def prompt(ctx, text, yes):
    """Converter linguagem natural em comando do gmail-cli."""
    try:
        cfg = load_config()
        provider = create_provider(cfg)
        natural = " ".join(text)
        fmt.info(f"Gerando comando para: {natural}")

        commands_help = _build_commands_help(ctx)
        generated = provider.generate_command(natural, commands_help)

        if not generated:
            fmt.error("Não foi possível gerar um comando.")
            return

        highlighted = click.style(generated, fg="cyan", bold=True)
        fmt.info(f"\nComando sugerido: {highlighted}\n")

        should_run = yes or click.confirm("Deseja executar o comando sugerido?", default=True)

        if should_run:
            cmd_to_run = generated.strip()
            if cmd_to_run.startswith("gmail "):
                cmd_to_run = cmd_to_run[len("gmail ") :].strip()
            elif cmd_to_run.startswith("gmail"):
                cmd_to_run = cmd_to_run[len("gmail") :].strip()

            args_list = shlex.split(cmd_to_run)

            try:
                ctx.find_root().command.main(args=args_list, standalone_mode=False)
            except click.ClickException as e:
                fmt.error(e.format_message())
            except click.Abort:
                fmt.info("Operação abortada.")
            except SystemExit as e:
                if e.code != 0:
                    fmt.error(f"O comando saiu com código {e.code}")
            except Exception as e:  # noqa: BLE001
                fmt.error(f"Erro inesperado: {e}")
    except (AuthError, GmailError, ValueError, ConnectionError, TimeoutError) as e:
        fmt.error(str(e))


if __name__ == "__main__":  # pragma: no cover
    cli()
