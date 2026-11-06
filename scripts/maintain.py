#!/usr/bin/env python3
"""Explicit, checkout-only research maintenance; no unattended effects by default."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if sys.version_info < (3, 11):
    print('AIC maintenance requires Python 3.11 or newer.', file=sys.stderr)
    raise SystemExit(2)
sys.path.insert(0, str(ROOT))

from maintenance import collector, policy, service
from maintenance.agents import AgentError
from maintenance.controller import Controller, MaintenanceBlocked
from maintenance.github import GitHub, GitHubError
from maintenance.state import State, StateError


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    commands = result.add_subparsers(dest='command', required=True)
    for name, description in (
        ('plan', 'Show policy without model, GitHub or filesystem effects'),
        ('discover', 'Read bounded primary sources without model or GitHub writes'),
        ('configure', 'Explicitly install repository protection and owned task labels'),
        ('run-once', 'Execute one approved bounded maintenance cycle'),
        ('status', 'Read durable usage, queue and source-check state'),
        ('install-service', 'Preview or explicitly activate a new immutable macOS scheduler'),
        ('service-status', 'Read the owned scheduler status'),
        ('uninstall-service', 'Preview or explicitly remove only the owned scheduler'),
    ):
        command = commands.add_parser(name, help=description)
        command.add_argument('--project', type=Path, default=ROOT)
        if name in ('discover', 'run-once'):
            command.add_argument('--bootstrap', help='Explicit allowed historical source; never represented as a new paper')
        if name == 'run-once':
            command.add_argument('--publish', action='store_true', help='Enable only the owner-approved research-record lane')
        if name in ('configure', 'install-service', 'uninstall-service'):
            command.add_argument('--approve', action='store_true', help='Explicit approval within the documented owner scope')
        if name == 'install-service':
            command.add_argument('--published-sha', required=True, help='Exact verified commit published in approved main')
            command.add_argument('--python', type=Path, default=Path(sys.executable))
    return result


def main(argv=None) -> int:
    args = parser().parse_args(argv)
    now = datetime.now(timezone.utc)
    project = args.project.absolute()
    try:
        if args.command == 'plan':
            value = Controller(project).run()
        elif args.command == 'discover':
            batch = (collector.CollectionBatch((collector.fetch_candidate(args.bootstrap, now=now),), (), now.isoformat())
                     if args.bootstrap else collector.collect(now))
            value = dict(status='partial' if batch.errors else 'checked', checked_at=batch.checked_at,
                         candidates=[dict(key=item.key, title=item.title, authors=list(item.authors), url=item.url,
                                          published=item.published, updated=item.updated, tier=item.tier,
                                          source_fetch_complete=bool(item.documents) and all(doc.complete for doc in item.documents),
                                          source_digest=policy.source_digest([item])) for item in batch.candidates],
                         errors=list(batch.errors), model_runs=0, published=False)
        elif args.command == 'configure':
            if not args.approve:
                value = dict(status='preview', repository=policy.REPO, required_checks=list(policy.CONTEXTS), side_effects=False)
            else:
                github = GitHub(write_enabled=True, working_directory=project)
                protection = github.protect_main()
                github.ensure_labels()
                value = dict(status='configured', repository=policy.REPO, protection=protection)
        elif args.command == 'run-once':
            value = Controller(project, publish=args.publish).run(bootstrap=args.bootstrap)
        elif args.command == 'status':
            path = project / '.work/maintainer/state.sqlite3'
            if not path.exists() and not path.is_symlink():
                value = dict(status='not-started', policy=policy.policy_document(), model_runs=0)
            else:
                state = State(path)
                try:
                    value = dict(status='recorded', policy=policy.policy_document(), **state.summary(policy.day_key(now)), source_errors=json.loads(state.meta('source_errors', '[]')))
                finally:
                    state.close()
        elif args.command == 'install-service':
            value = service.install(project, published_sha=args.published_sha, python=args.python, activate=args.approve)
        elif args.command == 'service-status':
            value = service.status(project)
        else:
            value = service.uninstall(project, approve=args.approve)
        print(json.dumps(value, indent=2, ensure_ascii=False))
        return 2 if value.get('status') in ('blocked', 'partial', 'source-check-partial') else 0
    except (MaintenanceBlocked, policy.PolicyError, StateError, AgentError, GitHubError, collector.CollectionError, service.ServiceError, OSError, subprocess.SubprocessError) as exc:
        print('AIC maintenance: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
