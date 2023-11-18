#!/usr/bin/env python3
# Copyright (c) 2022 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# spell-checker:ignore subcli
from __future__ import annotations

# System imports
import logging
import sys
from configparser import ConfigParser
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

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
def root_command1() -> None:
    'Root command 1'
    print('Root command 1')


@cli.command('root2')
def root_command2(
    arg1: str,
    # arg2: str,
) -> None:
    'Root command 2'
    print('Root command 2')
    print(f'{arg1=}')


@cli.command('root3')
def root_command3(
    opt_arg1: str = typer.Option(False, help='An optional arg'),
    opt_arg2: str = typer.Option(..., help='A **second** *required* option arg'),
    flag1: bool = typer.Option(False, '--flag1', '--flg1', '-f', '-y', help='A flag option'),
    flag2: bool = typer.Option(True, '--flag2/--no-flag2', '-t/-u', help='Another flag option'),
    flag3: bool = typer.Option(True, help='Yet another flag option'),
) -> None:
    'Root command 3'
    print('Root command 3')
    print(f'{opt_arg1=} ; {opt_arg2=} ; {flag1=} ; {flag2=} ; {flag3=}')


subcli_A = clyo.Typer()
cli.add_typer(
    subcli_A, name='level1A', help='Sub level 1',
    rich_help_panel='Sub CLI A for level 1'
)


@subcli_A.command()
def command1(
    arg1: str = typer.Argument(..., help='The first arg'),
    arg2: int = typer.Argument(..., help='The second arg'),
    arg3: int = typer.Argument(..., help='The third arg'),
    arg4: int = typer.Argument(..., hidden=True, help='The fourth (hidden) arg'),
) -> None:
    'First command'
    print('First command')
    print(f'{arg1=} ; {arg2=} ; {arg3=} ; {arg4=}')


@subcli_A.command(deprecated=True)
def command2(
    opt_arg1: str = typer.Option(False, help='An optional arg'),
    opt_arg2: int = typer.Option(0, help='A second optional arg'),
    opt_arg3: int = typer.Option(0, hidden=True, help='An hidden optional arg'),
) -> None:
    '''Second command (deprecated)

    This has

    more

    lines'''
    print('Second command (deprecated)')
    print(f'{opt_arg1=} ; {opt_arg2=} ; {opt_arg3=}')


@subcli_A.command(hidden=True)
def hidden_subcommand1(
    arg1: str = typer.Argument(..., help='The first arg'),
    opt_arg1: str = typer.Option(False, help='An optional arg'),
) -> None:
    '''Hidden subcommand'''
    print('Hidden subcommand')
    print(f'{opt_arg1=} ; {arg1=}')


subcli_AA = clyo.Typer()
subcli_A.add_typer(
    subcli_AA, name='level2A', help='Sub level 2A',
    rich_help_panel='Sub CLI A for level 2'
)


@subcli_AA.command()
def command3(arg1: str, opt_arg1: bool = False) -> None:
    'Third command'
    print('Third command')
    print(f'{arg1=} ; {opt_arg1=}')


@subcli_AA.command()
def command4() -> None:
    'Fourth command'
    print('Fourth command')


subcli_AB = clyo.Typer(deprecated=True)
subcli_A.add_typer(
    subcli_AB, name='level2B', help='Sub level 2B (deprecated)',
    rich_help_panel='Sub CLI B for level 2 (deprecated)'
)


@subcli_AB.command()
def command5() -> None:
    'Fifth command'
    print('Fifth command')


@subcli_AB.command(deprecated=True)
def command6() -> None:
    'Sixth command (deprecated)'
    print('Sixth command (deprecated)')


@cli.command(hidden=True)
def prompt(fuzzy: bool = True) -> None:
    from clyo import CommandTree

    command_tree = CommandTree(cli)
    command_tree.use_fuzzy_completer = fuzzy

    session = command_tree.make_prompt_session()
    try:
        while True:
            command_tree.repl(session)

    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    cli.set_main_callback(
        NAME, config=config, default_command=prompt,
        default_config_path=Path('config.cfg')
    )

    cli(prog_name=NAME)
