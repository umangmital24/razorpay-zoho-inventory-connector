from __future__ import annotations

import argparse
import asyncio
import json
from typing import Any

from zoho_inventory_connector.client import ZohoInventoryClient
from zoho_inventory_connector.config import get_settings
from zoho_inventory_connector.service import ZohoInventoryService


def print_json(value: Any) -> None:
    print(json.dumps(value, indent=2, default=str))


async def run(args: argparse.Namespace) -> None:
    settings = get_settings()

    async with ZohoInventoryClient(settings) as client:
        service = ZohoInventoryService(client, settings)

        if args.command == "organizations":
            print_json(await service.list_organizations())
        elif args.command == "items":
            if args.search:
                print_json(await service.search_items(args.search))
            else:
                print_json(await service.list_items())
        elif args.command == "low-stock":
            print_json(
                await service.list_low_stock_items(
                    threshold_override=args.threshold,
                )
            )
        elif args.command == "orders":
            print_json(await service.list_sales_orders())
        elif args.command == "order-search":
            print_json(
                await service.search_sales_orders(
                    query=args.query,
                    status=args.status,
                )
            )
        elif args.command == "risk":
            print_json(
                await service.find_open_orders_for_low_stock(
                    threshold_override=args.threshold,
                )
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Zoho Inventory connector demo")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("organizations")

    items = sub.add_parser("items")
    items.add_argument("--search")

    low_stock = sub.add_parser("low-stock")
    low_stock.add_argument("--threshold", type=float)

    sub.add_parser("orders")

    order_search = sub.add_parser("order-search")
    order_search.add_argument("--query")
    order_search.add_argument("--status")

    risk = sub.add_parser("risk")
    risk.add_argument("--threshold", type=float)

    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
