import discord
import asyncio
import textwrap
import traceback
import io
import os
import platform
import re
import argparse
from code import compile_command
from contextlib import redirect_stdout
from pathlib import Path

try:
    # input() の操作性向上のために readline をインポート
    import readline
except ImportError:
    pass


parser = argparse.ArgumentParser(prog="ddiscord")
parser.add_argument("token", nargs="?", default="-", help="Login token")
parser.add_argument(
    "-i", "--intents", nargs="*", default=["default"],
    help="Using intents('all' for all intents). If none, using Intents.default")
args = parser.parse_args()


async def run_debugger(client: discord.Client):
    print('Connecting to discord...', end='', flush=True)
    await client.wait_until_ready()
    print(f'\rLogged in as {client.user} ({client.user.id})')
    print('You can refer to your Client instance as `client` variable. '
          'i.e. client.guilds', end='\n\n')

    global env
    env = {'client': client}
    env.update(globals())

    while True:
        try:
            try:
                body = await client.loop.run_in_executor(None, input, '>>> ')
                while not compile_command(re.sub(r'(\s*)(await|async) *', r'\1', body)):
                    body += '\n' + await client.loop.run_in_executor(None, input, '... ')

            except (EOFError, KeyboardInterrupt):
                try:
                    await client.logout()
                except asyncio.CancelledError:
                    pass
                finally:
                    break

            if not body:
                continue

            # 実行するコード内部で作成された変数を env に代入
            _local_env = {}
            body = body + '\nglobal env\nenv.update(locals())'

            # 標準出力に何も出力しない式を実行した場合、式の返り値を表示するように準備
            source = f'async def func():\n{textwrap.indent(body, "  ")}'
            source_with_return = f'async def func():\n{textwrap.indent("return " + body, "  ")}'

            try:
                exec(source_with_return, env)
            except SyntaxError:
                exec(source, env)
            func = env['func']

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                retval = await func()
            if stdout.getvalue():
                print(stdout.getvalue(), end='')
            elif retval:
                print(repr(retval))

        except Exception:
            traceback.print_exc()
            continue


def get_token():
    token = args.token
    token_path = Path('./token')
    token_env = os.environ.get('DISCORD_TOKEN')

    if token_path.exists():
        token = token_path.read_text().rstrip()

    elif token_env:
        token = token_env

    print(f' - Debugger for discord.py - ')
    print(f'Running on Python {platform.python_version()}. ', end='')
    if os.name == 'posix':
        print('Send EOF (Ctrl-D) to exit.')
    elif os.name == 'nt':
        print('Send EOF (Ctrl-Z) to exit.')
    else:
        print('Send EOF to exit.')

    if token == "-":
        token = input('Input your token: ')

    return token


def get_intents():
    intents_path = Path('./intents')
    intents_env = os.environ.get('DISCORD_INTENTS')

    if intents_path.exists():
        inte = intents_path.read_text().rstrip()
    elif intents_env:
        inte = intents_env

    elif args.intents == ["default"]:
        return discord.Intents.default()
    elif args.intents in [["all"], ["All"]]:
        return discord.Intents.all()
    elif args.intents in [["none"], ["None"]]:
        return discord.Intents.none()
    else:
        inte = args.intents

    intents = discord.Intents()
    for i in inte:
        parsed = i.replace(" ", "").split("=")
        if not hasattr(intents, parsed[0]):
            raise ValueError("Invalid intents argument has passed.")
        setattr(intents, parsed[0], bool(parsed[1]) if len(parsed) > 1 else True)

    return intents


def main():
    token = get_token()

    if discord.version_info[0] < 2 and discord.version_info[1] < 5:
        # discordのバージョンは1.4以下
        client = discord.Client()
        client.loop.create_task(run_debugger(client))
    elif discord.version_info[0] < 2:
        # バージョン1.5 ~ 1.7 (intentsは利用可能)
        client = discord.Client(intents=get_intents())
        client.loop.create_task(run_debugger(client))
    else:
        # d.py2.0
        client = discord.Client(intents=get_intents())
        async def _on_ready():
            await run_debugger(client)
        client.on_ready = _on_ready

    client.run(token)


if __name__ == '__main__':
    main()
