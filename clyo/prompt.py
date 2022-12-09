# Copyright (c) 2022 Contributors as noted in the AUTHORS file
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

# System imports
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import chain
from pathlib import Path

# Third-party imports
import click
import typer
from click.parser import split_opt
from prompt_toolkit.completion import NestedCompleter, Completer, FuzzyCompleter, WordCompleter
from prompt_toolkit.document import Document
from typer.main import get_command

# Local imports


class RootCompleter(Completer):

    def __init__(self, level, root):
        self._level = level
        self._root = root

    def get_completions(self, document, complete_event):
        if document.text.startswith('/'):
            new_doc = Document(
                document.text[1:].replace('/', ' '),
                cursor_position=document.cursor_position - 1,
            )
            yield from self._root.completer.get_completions(new_doc, complete_event)
        else:
            new_doc = Document(
                document.text.replace('/', ' '),
                cursor_position=document.cursor_position,
            )
            yield from self._level.get_completions(new_doc, complete_event)


class NestedCompleterWithExtra(NestedCompleter):

    def __init__(self, options_with_extra, *args, **kwargs):
        self._extra_dict = {}
        options = {}
        for name, (option, extra) in options_with_extra.items():
            self._extra_dict[name] = extra
            options[name] = option
        super().__init__(options, *args, **kwargs)

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        if ' ' in text:
            yield from super().get_completions(document, complete_event)
        else:
            completer = WordCompleter(
                list(self.options.keys()),
                ignore_case=self.ignore_case,
                meta_dict=self._extra_dict,
            )
            yield from completer.get_completions(document, complete_event)


class CommandTree:

    ROOT_PATH = Path('/')

    @dataclass
    class Node:
        name: str
        command: click.Command = None
        # parser: click.parser.OptionParser = field(init=False)
        completer: Completer = None
        children: dict = field(default_factory=dict)
        parent: Node = None
        path: Path = field(init=False)

        def __post_init__(self):
            if self.parent:
                self.path = self.parent.path / self.name
            else:
                self.path = CommandTree.ROOT_PATH / self.name

        @property
        def _options_trans(self):
            parser = self.command.make_parser(click.get_current_context())
            return {
                split_opt(opt)[1]: opt
                for opt in chain(parser._short_opt.keys(), parser._long_opt.keys())
            }

        def make_args(self, args_string):
            args = None
            if args_string:
                args = []
                opts = self._options_trans
                for arg in args_string.split(' '):
                    if not arg:
                        continue
                    if '=' in arg:
                        opt, value = arg.split('=', maxsplit=1)
                        if opt in opts:
                            args.append(f'{opts[opt]}={value}')
                        else:
                            args.append(arg)
                    else:
                        args.append(arg)

            return args or None

    def __init__(self, cli):
        self._cli = cli
        root_command = self._cli
        if isinstance(root_command, typer.Typer):
            root_command = get_command(root_command)
        self._root = self.Node(
            name='',
            command=root_command,
            children=dict(self._make_model(root_command)),
        )
        self._make_group_completer(self._root)
        self._pointer = self._root
        self._parents = []

        # self.path = Path(self.ROOT_PATH)
        # self.path = self._pointer.path

    @property
    def path(self):
        return self._pointer.path

    def _make_group_completer(self, node):
        def _completion_dict(base):
            for node in base.children.values():
                yield node.name, (
                    node.completer, (node.command.help or ' ').splitlines()[0].strip())

        node.completer = NestedCompleterWithExtra(dict(_completion_dict(node)))

    def _make_command_completer(self, node):
        completion_dict = {}
        for param in node.command.params:
            if not isinstance(param, click.Option):
                continue
            for opt in param.opts:
                completion_dict[f'{split_opt(opt)[1]}='] = (
                    None, (param.help or ' ').splitlines()[0].strip())

        if completion_dict:
            node.completer = NestedCompleterWithExtra(completion_dict)

    def _make_model(self, command, parent=None):
        for subcommand in command.commands.values():
            node = self.Node(
                name=subcommand.name,
                command=subcommand,
                parent=parent,
            )
            if isinstance(subcommand, click.Group):
                node.children = dict(self._make_model(subcommand, node))
                self._make_group_completer(node)
            else:
                self._make_command_completer(node)

            yield node.name, node

    @property
    def completer(self):
        return FuzzyCompleter(RootCompleter(self._pointer.completer, self._root))

    @property
    def at_root(self):
        return (self.path == self.ROOT_PATH)

    def __getitem__(self, name):
        pointer = self._pointer
        if name.lstrip().startswith('/'):
            pointer = self._root

        remain = name.replace('/', ' ').strip()
        while remain:
            fields = remain.split(' ', maxsplit=1)
            if len(fields) > 1:
                subpath, remain = fields
            else:
                subpath, = fields
                remain = ''

            if not subpath:
                continue

            if subpath == '..':
                pointer = pointer.parent if pointer.parent else pointer
            else:
                pointer = pointer.children[subpath]

            if not pointer.children:
                break

        return pointer, remain
