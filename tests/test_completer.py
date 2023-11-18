# Copyright (c) 2023 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.
#
# spell-checker:enableCompoundWords
# spell-checker:words
# spell-checker:ignore fuzzies unformat
''''''
from __future__ import annotations

# System imports
import logging
from operator import itemgetter
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import TypeAlias

# Third-party imports
import pytest
# Local imports
import typer
from prompt_toolkit.completion import CompleteEvent, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.formatted_text import FormattedText
from rich import print

from clyo import ClyoTyper, CommandTree

from .fixtures import base_tree

_logger = logging.getLogger(__name__)


@pytest.fixture(scope='module')
def cli() -> ClyoTyper:
    return base_tree.cli


@pytest.fixture(scope='module')
def command_tree(cli: ClyoTyper) -> CommandTree:
    command = typer.main.get_command(cli)
    ctx = command.make_context('base_tree', [])
    with ctx:
        command_tree = CommandTree(cli)

    session = command_tree.make_prompt_session()
    command_tree.current_prompt = session
    return command_tree


def unformat(text: FormattedText) -> str:
    return ''.join(map(itemgetter(1), text))


def print_completion(completion: Completion) -> None:
    print(completion)
    print(
        f"{type(completion).__name__}(text='{completion.text}', display='{completion.display}', "
        f"display_text='{completion.display_text}', start_position={completion.start_position}, "
        f"display_meta='{unformat(completion.display_meta)}')"
    )


if TYPE_CHECKING:
    CompletionFixture: TypeAlias = tuple[str | tuple[str, str], str]


@pytest.mark.parametrize(
    'path, text, fix_path, fix_len, fix_args', [
        # Root itself
        ('/', '', '/', 0, ''),
        ('/', '/', '/', 1, ''),
        ('/', '/ ', '/', 1, ''),
        ('/', ' /', '/', 2, ''),
        ('/', ' / ', '/', 2, ''),
        pytest.param('/', 'r', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/r', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        ('/', '/////////////////', '/', 17, ''),
        ('/', '   /////////////////', '/', 20, ''),

        # Root level
        ('/', 'root1', '/root1', 5, ''),
        ('/', '/root1', '/root1', 6, ''),
        ('/', '////////root1', '/root1', 13, ''),
        ('/', 'root1//', '/root1', 7, ''),
        ('/', 'root1/', '/root1', 6, ''),
        ('/', '/root1/', '/root1', 7, ''),
        ('/', 'root1///', '/root1', 8, ''),
        ('/', '/root1///', '/root1', 9, ''),
        ('/', '///root1///', '/root1', 11, ''),
        ('/', 'root1 ', '/root1', 5, ''),
        ('/', '/root1 ', '/root1', 6, ''),
        ('/', ' root1', '/root1', 6, ''),
        ('/', ' /root1', '/root1', 7, ''),
        ('/', ' root1 ', '/root1', 6, ''),
        ('/', ' /root1 ', '/root1', 7, ''),
        ('/', '   root1   ', '/root1', 8, ''),
        ('/', '   /root1   ', '/root1', 9, ''),
        ('/', 'root1 a', '/root1', 6, 'a'),
        ('/', '/root1 a', '/root1', 7, 'a'),
        ('/', 'root1 arg1', '/root1', 6, 'arg1'),
        ('/', '/root1 arg1', '/root1', 7, 'arg1'),
        ('/', '  root1 arg1', '/root1', 8, 'arg1'),
        ('/', '  /root1 arg1', '/root1', 9, 'arg1'),
        ('/', 'root1  arg1', '/root1', 7, 'arg1'),
        ('/', '/root1  arg1', '/root1', 8, 'arg1'),
        ('/', 'root1 arg1 ', '/root1', 6, 'arg1'),
        ('/', '/root1 arg1 ', '/root1', 7, 'arg1'),
        pytest.param('/', 'root1/arg1', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/root1/arg1', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', 'root1////arg1', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/root1////arg1', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        ('/', 'root1 /arg1', '/root1', 6, '/arg1'),
        ('/', '/root1 /arg1', '/root1', 7, '/arg1'),
        ('/', 'root1/ /arg1', '/root1', 7, '/arg1'),
        ('/', '/root1/ /arg1', '/root1', 8, '/arg1'),
        ('/', 'root1/// ///arg1', '/root1', 9, '///arg1'),
        ('/', '/root1/// ///arg1', '/root1', 10, '///arg1'),
        ('/', 'root1 arg1 arg2', '/root1', 6, 'arg1 arg2'),
        ('/', '/root1 arg1 arg2', '/root1', 7, 'arg1 arg2'),

        # One level
        ('/', 'level1A', '/level1A', 7, ''),
        ('/', '/level1A', '/level1A', 8, ''),
        ('/', 'level1A/', '/level1A', 8, ''),
        ('/', '/level1A/', '/level1A', 9, ''),
        ('/', '////level1A/', '/level1A', 12, ''),
        ('/', '/level1A////', '/level1A', 12, ''),
        ('/', '////level1A////', '/level1A', 15, ''),
        # Fail reason: level1A is a command group, it cannot have arguments. 'c' is then
        # attempted to be interpreted as a command, which does not exist.
        pytest.param('/', 'level1A c', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/level1A c', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', 'level1A/c', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/level1A/c', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        ('/', 'level1A command1', '/level1A/command1', 16, ''),
        ('/', '/level1A command1', '/level1A/command1', 17, ''),
        ('/', '/level1A/command1', '/level1A/command1', 17, ''),
        ('/', 'level1A/command1', '/level1A/command1', 16, ''),
        ('/', 'level1A command1/', '/level1A/command1', 17, ''),
        ('/', '/level1A command1/', '/level1A/command1', 18, ''),
        ('/', '/level1A/command1/', '/level1A/command1', 18, ''),
        ('/', 'level1A/command1/', '/level1A/command1', 17, ''),
        ('/', 'level1A    command1', '/level1A/command1', 19, ''),
        ('/', '/  level1A command1', '/level1A/command1', 19, ''),
        ('/', ' / level1A/command1', '/level1A/command1', 19, ''),
        ('/', 'level1A /command1', '/level1A/command1', 17, ''),
        ('/', 'level1A/ command1', '/level1A/command1', 17, ''),
        ('/', 'level1A / command1', '/level1A/command1', 18, ''),
        ('/', 'level1A  /  command1', '/level1A/command1', 20, ''),
        ('/', 'level1A////command1', '/level1A/command1', 19, ''),
        ('/', 'level1A/command1///', '/level1A/command1', 19, ''),
        ('/', '////level1A/command1', '/level1A/command1', 20, ''),
        ('/', '////level1A////command1', '/level1A/command1', 23, ''),
        ('/', '// //level1A// //command1', '/level1A/command1', 25, ''),
        ('/', '//   //level1A//   //command1', '/level1A/command1', 29, ''),
        ('/', 'level1A/command1// //', '/level1A/command1', 19, '//'),
        ('/', 'level1A command1 arg', '/level1A/command1', 17, 'arg'),
        ('/', '/level1A command1 arg', '/level1A/command1', 18, 'arg'),
        ('/', 'level1A/command1 arg', '/level1A/command1', 17, 'arg'),
        ('/', '/level1A/command1 arg', '/level1A/command1', 18, 'arg'),
        ('/', 'level1A   command1   arg', '/level1A/command1', 21, 'arg'),
        pytest.param('/', 'level1A command1/arg', '', 0, '',
                     marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/level1A/command1/arg', '', 0, '',
                     marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', 'level1A command1////arg', '', 0, '',
                     marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', '/level1A/command1////arg', '', 0, '',
                     marks=pytest.mark.xfail(raises=KeyError)),
        ('/', 'level1A command1 /arg', '/level1A/command1', 17, '/arg'),
        ('/', '/level1A/command1 /arg', '/level1A/command1', 18, '/arg'),
        ('/', 'level1A command1/ /arg', '/level1A/command1', 18, '/arg'),
        ('/', '/level1A/command1/ /arg', '/level1A/command1', 19, '/arg'),
        ('/', 'level1A command1/// ///arg', '/level1A/command1', 20, '///arg'),
        ('/', '/level1A/command1/// ///arg', '/level1A/command1', 21, '///arg'),
        ('/', '/level1A/command1///   ///arg', '/level1A/command1', 23, '///arg'),

        # Two levels
        ('/', 'level1A level2B', '/level1A/level2B', 15, ''),
        ('/', '/level1A level2B', '/level1A/level2B', 16, ''),
        ('/', '/level1A/level2B', '/level1A/level2B', 16, ''),
        ('/', 'level1A/level2B', '/level1A/level2B', 15, ''),
        ('/', 'level1A level2B/', '/level1A/level2B', 16, ''),
        ('/', '/level1A level2B/', '/level1A/level2B', 17, ''),
        ('/', '/level1A/level2B/', '/level1A/level2B', 17, ''),
        ('/', 'level1A/level2B/', '/level1A/level2B', 16, ''),
        ('/', 'level1A   level2B', '/level1A/level2B', 17, ''),
        ('/', '/  level1A level2B', '/level1A/level2B', 18, ''),
        ('/', ' / level1A level2B', '/level1A/level2B', 18, ''),
        ('/', 'level1A /level2B', '/level1A/level2B', 16, ''),
        ('/', 'level1A/ level2B', '/level1A/level2B', 16, ''),
        ('/', 'level1A / level2B', '/level1A/level2B', 17, ''),
        ('/', 'level1A///level2B', '/level1A/level2B', 17, ''),
        ('/', 'level1A/level2B///', '/level1A/level2B', 18, ''),
        ('/', '////level1A/level2B', '/level1A/level2B', 19, ''),
        ('/', '////level1A////level2B', '/level1A/level2B', 22, ''),
        ('/', '// //level1A// //level2B', '/level1A/level2B', 24, ''),
        ('/', '//   //level1A//   //level2B', '/level1A/level2B', 28, ''),
        ('/', 'level1A level2B command6', '/level1A/level2B/command6', 24, ''),
        ('/', '/level1A level2B command6', '/level1A/level2B/command6', 25, ''),
        ('/', '/level1A/level2B command6', '/level1A/level2B/command6', 25, ''),
        ('/', 'level1A/level2B command6', '/level1A/level2B/command6', 24, ''),
        ('/', 'level1A level2B/command6', '/level1A/level2B/command6', 24, ''),
        ('/', '/level1A level2B/command6', '/level1A/level2B/command6', 25, ''),
        ('/', '/level1A/level2B/command6', '/level1A/level2B/command6', 25, ''),
        ('/', 'level1A/level2B/command6', '/level1A/level2B/command6', 24, ''),
        ('/', 'level1A level2B command6/', '/level1A/level2B/command6', 25, ''),
        ('/', '/level1A level2B command6/', '/level1A/level2B/command6', 26, ''),
        ('/', '/level1A/level2B command6/', '/level1A/level2B/command6', 26, ''),
        ('/', 'level1A/level2B command6/', '/level1A/level2B/command6', 25, ''),
        ('/', 'level1A level2B/command6/', '/level1A/level2B/command6', 25, ''),
        ('/', '/level1A level2B/command6/', '/level1A/level2B/command6', 26, ''),
        ('/', '/level1A/level2B/command6/', '/level1A/level2B/command6', 26, ''),
        ('/', 'level1A/level2B/command6/', '/level1A/level2B/command6', 25, ''),
        ('/', '  level1A   level2B   command6  ', '/level1A/level2B/command6', 30, ''),
        ('/', '////level1A////level2B////command6//', '/level1A/level2B/command6', 36, ''),
        ('/', ' // //level1A/ / / /level2B/  ///command6//  ', '/level1A/level2B/command6', 43, ''),
        ('/', 'level1A level2B command6/// ///', '/level1A/level2B/command6', 28, '///'),
        ('/', 'level1A level2B command6 --arg1 --a-rg2=ah', '/level1A/level2B/command6', 25, '--arg1 --a-rg2=ah'),
        pytest.param('/', 'level1A level2B command6/arg', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),

        # Navigating hierarchy
        ('/level1A', '', '/level1A', 0, ''),
        ('/level1A', 'command1', '/level1A/command1', 8, ''),
        ('/level1A', './command1', '/level1A/command1', 10, ''),
        ('/level1A', '..', '/', 2, ''),
        ('/level1A', '../', '/', 3, ''),
        ('/level1A', '../..', '/', 5, ''),
        ('/level1A', './..', '/', 4, ''),
        ('/level1A', '../.', '/', 4, ''),
        ('/level1A', '.././', '/', 5, ''),
        ('/level1A', './../.', '/', 6, ''),
        ('/level1A', './.././', '/', 7, ''),
        ('/level1A', '../root1', '/root1', 8, ''),
        ('/level1A', './../root1', '/root1', 10, ''),
        ('/level1A', './.././root1', '/root1', 12, ''),
        ('/level1A', '/', '/', 1, ''),
        ('/level1A', '/./', '/', 3, ''),
        ('/level1A', '/../', '/', 4, ''),
        ('/level1A', '/../..', '/', 6, ''),
        ('/level1A', '/root1', '/root1', 6, ''),
        ('/level1A/level2A', '../level2B', '/level1A/level2B', 10, ''),
        ('/level1A/level2A', '../../root1', '/root1', 11, ''),

        # Comments
        ('/', '# root1', '/', 0, ''),
        ('/', '   # root1', '/', 0, ''),
        ('/', 'level1A#/command1', '/level1A', 7, ''),
        ('/', 'level1A/#command1', '/level1A', 8, ''),

        # Help prefixes
        ('/', 'help', '/', 4, '--help'),
        ('/', 'help root1', '/root1', 10, '--help'),
        ('/', 'help    root1', '/root1', 13, '--help'),
        pytest.param('/', 'help/root1', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        pytest.param('/', 'help///root1', '', 0, '', marks=pytest.mark.xfail(raises=KeyError)),
        ('/', 'help root1 arg', '/root1', 11, '--help'),
        ('/', '?', '/', 1, '--help'),
        ('/', '? root1', '/root1', 7, '--help'),

    ]
)
def test_get_command(
    command_tree: CommandTree,
    path: str,
    text: str,
    fix_path: str,
    fix_len: int,
    fix_args: str,
) -> None:
    command_tree.path = path

    command, args, command_len = command_tree.get_command(text, True)
    print(f'{command.name=}, {command.path=!s}, {command_len=}, {args=}')

    assert command.path == Path(fix_path)
    assert command_len == fix_len
    assert args == fix_args


completion_fixtures: dict[str, CompletionFixture] = dict(
    root1=('root1', 'Root command 1'),
    root2=('root2', 'Root command 2'),
    root3=('root3', 'Root command 3'),
    level1A=('level1A', 'Sub level 1'),
    command1=('command1', 'First command'),
    command2=('command2', 'Second command (deprecated)'),
    level2A=('level2A', 'Sub level 2A'),
    command3=('command3', 'Third command'),
    command4=('command4', 'Fourth command'),
    level2B=('level2B', 'Sub level 2B (deprecated)'),
    command5=('command5', 'Fifth command'),
    command6=('command6', 'Sixth command (deprecated)'),
)

root_level: list[CompletionFixture] = [
    completion_fixtures['root1'],
    completion_fixtures['root2'],
    completion_fixtures['root3'],
    completion_fixtures['level1A'],
]

level1A: list[CompletionFixture] = [
    completion_fixtures['command1'],
    completion_fixtures['command2'],
    completion_fixtures['level2A'],
    completion_fixtures['level2B'],
]

level2A: list[CompletionFixture] = [
    completion_fixtures['command3'],
    completion_fixtures['command4'],
]

level2B: list[CompletionFixture] = [
    completion_fixtures['command5'],
    completion_fixtures['command6'],
]

root2_params: list[CompletionFixture] = [
    (('ARG1', '<ARG1>'), 'TEXT (None)'),
]

root3_params: list[CompletionFixture] = [
    ('opt-arg1=', 'TEXT (False) An optional arg'),
    ('opt-arg2=', 'TEXT (None) A second required option arg'),
    ('--flag1', 'FLAG A flag option'),
    ('--no-flag2', 'FLAG (flag2) Another flag option'),
    ('--no-flag3', 'FLAG (flag3) Yet another flag option'),
]

command1_params: list[CompletionFixture] = [
    (('ARG1', '<ARG1>'), 'TEXT (None) The first arg'),
    (('ARG2', '<ARG2>'), 'INTEGER (None) The second arg'),
    (('ARG3', '<ARG3>'), 'INTEGER (None) The third arg'),
]


@pytest.mark.parametrize(
    'fuzzy, path, text, fixtures', [
        (None, '/', '', root_level),
        (None, '/', '/', root_level),
        (None, '/', 'r', root_level[:3]),
        (None, '/', '/r', root_level[:3]),
        (None, '/', 'ro', root_level[:3]),
        (None, '/', '/ro', root_level[:3]),
        (None, '/', 'roo', root_level[:3]),
        (None, '/', '/roo', root_level[:3]),
        (None, '/', 'root', root_level[:3]),
        (None, '/', '/root', root_level[:3]),
        (False, '/', 'root1', []),
        (True, '/', 'root1', [completion_fixtures['root1']]),
        (False, '/', '/root1', []),
        (True, '/', '/root1', [completion_fixtures['root1']]),
        (None, '/', 'root1 ', []),
        (None, '/', '/root1 ', []),
        (False, '/', 'root2', []),
        (True, '/', 'root2', [completion_fixtures['root2']]),
        (False, '/', '/root2', []),
        (True, '/', '/root2', [completion_fixtures['root2']]),
        (None, '/', 'root2 ', root2_params),
        (None, '/', '/root2 ', root2_params),
        (False, '/', 'root2 a', []),
        (True, '/', 'root2 a', root2_params),
        (False, '/', 'root3', []),
        (True, '/', 'root3', [completion_fixtures['root3']]),
        (False, '/', '/root3', []),
        (True, '/', '/root3', [completion_fixtures['root3']]),
        (None, '/', 'root3 ', root3_params),
        (None, '/', '/root3 ', root3_params),
        (False, '/', 'root3 o', root3_params[:2]),
        (True, '/', 'root3 o', root3_params[:2] + root3_params[3:]),
        (False, '/', '/root3 o', root3_params[:2]),
        (True, '/', '/root3 o', root3_params[:2] + root3_params[3:]),
        (False, '/', 'root3   o', root3_params[:2]),
        (True, '/', 'root3   o', root3_params[:2] + root3_params[3:]),
        (False, '/', '/root3   o', root3_params[:2]),
        (True, '/', '/root3   o', root3_params[:2] + root3_params[3:]),
        (None, '/', 'root3 op', root3_params[:2]),
        (None, '/', '/root3 op', root3_params[:2]),
        (None, '/', 'root3   op', root3_params[:2]),
        (None, '/', '/root3   op', root3_params[:2]),
        (False, '/', 'root3 a', []),
        (True, '/', 'root3 a', root3_params),
        (False, '/', '/root3 a', []),
        (True, '/', '/root3 a', root3_params),
        (False, '/', 'root3   a', []),
        (True, '/', 'root3   a', root3_params),
        (False, '/', '/root3   a', []),
        (True, '/', '/root3   a', root3_params),
        (False, '/', 'root3 arg', []),
        (True, '/', 'root3 arg', root3_params[:2]),
        (False, '/', '/root3 arg', []),
        (True, '/', '/root3 arg', root3_params[:2]),
        (False, '/', 'root3   arg', []),
        (True, '/', 'root3   arg', root3_params[:2]),
        (False, '/', '/root3   arg', []),
        (True, '/', '/root3   arg', root3_params[:2]),
        (False, '/', 'root3 fla', []),
        (True, '/', 'root3 fla', root3_params[2:]),
        (False, '/', '/root3 fla', []),
        (True, '/', '/root3 fla', root3_params[2:]),
        (False, '/', 'root3   fla', []),
        (True, '/', 'root3   fla', root3_params[2:]),
        (False, '/', '/root3   fla', []),
        (True, '/', '/root3   fla', root3_params[2:]),
        (False, '/', 'root3 --flag1', []),
        (True, '/', 'root3 --flag1', [root3_params[2]]),
        (False, '/', '/root3 --flag1', []),
        (True, '/', '/root3 --flag1', [root3_params[2]]),
        (None, '/', 'root3 --flag1 ', root3_params),
        (None, '/', '/root3 --flag1 ', root3_params),
        (False, '/', 'root3 --flag1 o', root3_params[:2]),
        (True, '/', 'root3 --flag1 o', root3_params[:2] + root3_params[3:]),
        (False, '/', '/root3 --flag1 o', root3_params[:2]),
        (True, '/', '/root3 --flag1 o', root3_params[:2] + root3_params[3:]),

        (None, '/', 'le', [completion_fixtures['level1A']]),
        (None, '/', '/le', [completion_fixtures['level1A']]),
        (False, '/', 'lel', []),
        (True, '/', 'lel', [completion_fixtures['level1A']]),
        (False, '/', '/lel', []),
        (True, '/', '/lel', [completion_fixtures['level1A']]),
        (False, '/', 'level1A', []),
        (True, '/', 'level1A', [completion_fixtures['level1A']]),
        (False, '/', '/level1A', []),
        (True, '/', '/level1A', [completion_fixtures['level1A']]),
        (None, '/', 'level1A ', level1A),
        (None, '/', '/level1A ', level1A),
        (None, '/', 'level1A/', level1A),
        (None, '/', '/level1A/', level1A),
        (None, '/', 'level1A c', level1A[:2]),
        (None, '/', '/level1A c', level1A[:2]),
        (None, '/', 'level1A/c', level1A[:2]),
        (None, '/', '/level1A/c', level1A[:2]),
        (None, '/', 'level1A l', level1A[2:]),
        (None, '/', '/level1A l', level1A[2:]),
        (None, '/', 'level1A/l', level1A[2:]),
        (None, '/', '/level1A/l', level1A[2:]),
        (False, '/', 'level1A command1 A', command1_params[1:]),
        (True, '/', 'level1A command1 A', command1_params),
        (False, '/', '/level1A command1 A', command1_params[1:]),
        (True, '/', '/level1A command1 A', command1_params),
        (False, '/', 'level1A command1 g', command1_params[1:]),
        (True, '/', 'level1A command1 g', command1_params),
        (False, '/', '/level1A command1 g', command1_params[1:]),
        (True, '/', '/level1A command1 g', command1_params),
        (False, '/', 'level1A command1 o', command1_params[1:]),
        (True, '/', 'level1A command1 o', []),
        (False, '/', '/level1A command1 o', command1_params[1:]),
        (True, '/', '/level1A command1 o', []),
        (False, '/', 'level1A command1 other1', command1_params[1:]),
        (True, '/', 'level1A command1 other1', []),
        (False, '/', '/level1A command1 other1', command1_params[1:]),
        (True, '/', '/level1A command1 other1', []),
        (False, '/', 'level1A command1 other1 ', command1_params[1:]),
        (True, '/', 'level1A command1 other1 ', command1_params[1:]),
        (False, '/', '/level1A command1 other1 ', command1_params[1:]),
        (True, '/', '/level1A command1 other1 ', command1_params[1:]),
        (False, '/', 'level1A command1 other1 o', command1_params[2:]),
        (True, '/', 'level1A command1 other1 o', []),
        (False, '/', '/level1A command1 other1 o', command1_params[2:]),
        (True, '/', '/level1A command1 other1 o', []),
        (False, '/', 'level1A command1 other1 other2', command1_params[2:]),
        (True, '/', 'level1A command1 other1 other2', []),
        (False, '/', '/level1A command1 other1 other2', command1_params[2:]),
        (True, '/', '/level1A command1 other1 other2', []),
        (False, '/', 'level1A command1 other1 other2 ', command1_params[2:]),
        (True, '/', 'level1A command1 other1 other2 ', command1_params[2:]),
        (False, '/', '/level1A command1 other1 other2 ', command1_params[2:]),
        (True, '/', '/level1A command1 other1 other2 ', command1_params[2:]),
        (False, '/', 'level1A command1 other1 other2 o', command1_params[3:]),
        (True, '/', 'level1A command1 other1 other2 o', []),
        (False, '/', '/level1A command1 other1 other2 o', command1_params[3:]),
        (True, '/', '/level1A command1 other1 other2 o', []),
        (False, '/', 'level1A command1 other1 other2 other3', []),
        (True, '/', 'level1A command1 other1 other2 other3', []),
        (False, '/', '/level1A command1 other1 other2 other3', []),
        (True, '/', '/level1A command1 other1 other2 other3', []),
        (False, '/', 'level1A command1 other1 other2 other3 ', []),
        (True, '/', 'level1A command1 other1 other2 other3 ', []),
        (False, '/', '/level1A command1 other1 other2 other3 ', []),
        (True, '/', '/level1A command1 other1 other2 other3 ', []),
        (False, '/', 'level1A command1 other1 other2 other3 o', []),
        (True, '/', 'level1A command1 other1 other2 other3 o', []),
        (False, '/', '/level1A command1 other1 other2 other3 o', []),
        (True, '/', '/level1A command1 other1 other2 other3 o', []),
        (False, '/', 'level1A command1 other1 other2 other3 other4', []),
        (True, '/', 'level1A command1 other1 other2 other3 other4', []),
        (False, '/', '/level1A command1 other1 other2 other3 other4', []),
        (True, '/', '/level1A command1 other1 other2 other3 other4', []),
        (False, '/', 'level1A command1 other1 other2 other3 other4 ', []),
        (True, '/', 'level1A command1 other1 other2 other3 other4 ', []),
        (False, '/', '/level1A command1 other1 other2 other3 other4 ', []),
        (True, '/', '/level1A command1 other1 other2 other3 other4 ', []),

        (None, '/', 'help', []),
        (None, '/', 'help ', root_level),
        (None, '/', 'help /', root_level),
        # (None, '/', 'help/', []),
    ]
)
def test_a(
    command_tree: CommandTree,
    fuzzy: bool | None,
    path: str,
    text: str,
    fixtures: list[CompletionFixture]
) -> None:
    command_tree.path = path
    if fuzzy is None:
        fuzzies = (False, True)
    else:
        fuzzies = (fuzzy, )

    for fuzzy in fuzzies:
        print(f'Doing {fuzzy=} of {fuzzies=}')
        command_tree.use_fuzzy_completer = fuzzy
        completer = command_tree.completer

        doc = Document(text, len(text))
        event = CompleteEvent(text_inserted=True)
        results = list(completer.get_completions(doc, event))
        # print(f'{results=}')
        for fix_text, fix_meta in fixtures:
            completion = results.pop(0)
            print_completion(completion)
            if isinstance(fix_text, tuple):
                if fuzzy and not text.endswith(' '):
                    # Special case when it's fuzzy and we start to type,
                    # apparently it removes special characters like < and >.
                    # Since we use this fixture form only for <ARGS>,
                    # this special treatment is easy.
                    assert completion.text == fix_text[0]
                else:
                    assert completion.text == fix_text[0]
                    assert completion.display_text == fix_text[1]
            else:
                assert completion.text == fix_text
            assert completion.display_meta_text == fix_meta

        assert not results, results

    # assert False
