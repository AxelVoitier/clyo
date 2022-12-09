#!/usr/bin/env python3
# Copyright (c) 2022 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# System imports
import logging
import sys
from configparser import ConfigParser
from pathlib import Path

# Third-party imports
import typer

# Local imports
import clyo


OURSELF = Path(__file__).resolve()
BASE_PATH = OURSELF.parent
NAME = Path(sys.argv[0]).stem  # Or use OURSELF.stem

logger = logging.getLogger(NAME)
config = ConfigParser()
cli = clyo.Typer(help='Application testing Clyo features')


@cli.command('root1')
def root_command1():
    'Root command 1'
    print('Root command 1')


@cli.command('root2')
def root_command2(arg1):
    'Root command 2'
    print('Root command 2')
    print(f'{arg1=}')


subcli_A = clyo.Typer()
cli.add_typer(subcli_A, name='level1A', rich_help_panel='Sub CLI A for level 1')


@subcli_A.command()
def command1(
    arg1: str = typer.Argument(..., help='The first arg'),
    arg2: int = typer.Argument(..., help='The second arg')
):
    'First command'
    print('First command')
    print(f'{arg1=} ; {arg2=}')


@subcli_A.command(deprecated=True)
def command2(
    opt_arg1: str = typer.Option(False, help='An optional arg'),
):
    '''Second command (deprecated)

    This has

    more

    lines'''
    print('Second command (deprecated)')
    print(f'{opt_arg1=}')


subcli_AA = clyo.Typer()
subcli_A.add_typer(subcli_AA, name='level2A', rich_help_panel='Sub CLI A for level 2')


@subcli_AA.command()
def command3(arg1, opt_arg1=False):
    'Third command'
    print('Third command')
    print(f'{arg1=} ; {opt_arg1=}')


@subcli_AA.command()
def command4():
    'Fourth command'
    print('Fourth command')


subcli_AB = clyo.Typer(deprecated=True)
subcli_A.add_typer(subcli_AB, name='level2B', rich_help_panel='Sub CLI B for level 2 (deprecated)')


@subcli_AB.command()
def command5():
    'Fifth command'
    print('Fifth command')


@subcli_AB.command(deprecated=True)
def command6():
    'Sixth command (deprecated)'
    print('Sixth command (deprecated)')


@cli.command()
def prompt():
    import click
    from clyo.prompt import CommandTree
    from prompt_toolkit import PromptSession
    from prompt_toolkit.output import ColorDepth
    from rich import print as rprint

    command_tree = CommandTree(cli)

    session = PromptSession(color_depth=ColorDepth.TRUE_COLOR)
    try:
        while True:
            prompt = [
                ('#00aa00', '['),
                ('ansibrightcyan', str(command_tree.path)),
                ('#00aa00', '] ')
            ]

            input = session.prompt(prompt, completer=command_tree.completer)

            try:
                command, remain = command_tree[input]
            except KeyError:
                print('Command not found:', input)
                continue

            if command.children:
                command_tree._pointer = command
            else:
                try:
                    command.command(
                        command.make_args(remain),
                        prog_name=str(command.path),
                        # standalone_mode=False,
                    )
                except SystemExit:
                    pass
                except click.ClickException as ex:
                    # print('ctx', click.get_current_context(silent=True),
                    #       click.get_current_context(silent=True).color)
                    # print('ex.ctx', ex.ctx, ex.ctx.color)
                    # ex.ctx = click.get_current_context()
                    # ex.ctx.color = True
                    # with ex.ctx:
                    # with click.get_current_context():
                    # ex.show(file=sys.stderr)
                    ex.show()
                except click.Abort:
                    rprint('[rrd]Aborted![/]', file=sys.stderr)
                except Exception as ex:
                    rprint('[red]Exception:[/]', ex, file=sys.stderr)

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    cli.set_main_callback(
        NAME, config=config,  default_command=prompt,
        default_config_path=Path('config.cfg')
    )

    cli(prog_name=NAME)
