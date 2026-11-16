"""Issue a short-lived PRAXIS JWT for local or administrative use."""

from __future__ import annotations

import argparse
from datetime import timedelta

from app.auth import AuthSettings, issue_access_token


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True, help="ID de usuario")
    parser.add_argument("--company-id", required=True, help="UUID de la empresa")
    parser.add_argument(
        "--role",
        required=True,
        choices=[
            "owner",
            "admin",
            "manager",
            "viewer",
            "employee",
            "association_admin",
        ],
    )
    parser.add_argument(
        "--scope",
        action="append",
        default=[],
        help="Scope concedido; repetir para varios",
    )
    parser.add_argument(
        "--minutes",
        type=int,
        default=None,
        help="Vida del token; nunca superior al máximo configurado",
    )
    return parser


def main() -> None:
    parser = _parser()
    args = parser.parse_args()
    if not args.scope:
        parser.error("Indica al menos un --scope")
    try:
        settings = AuthSettings.from_env()
        token = issue_access_token(
            subject=args.subject,
            company_id=args.company_id,
            role=args.role,
            scopes=args.scope,
            settings=settings,
            expires_in=timedelta(minutes=args.minutes) if args.minutes else None,
        )
    except ValueError as error:
        parser.error(str(error))
    print(token)


if __name__ == "__main__":
    main()
