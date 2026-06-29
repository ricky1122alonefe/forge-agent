"""`forge-agent datasets` — Dataset management: list, show, create, delete."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def add(sub: argparse._SubParsersAction) -> None:
    p = sub.add_parser("datasets", help="Dataset management")
    sub_p = p.add_subparsers(dest="datasets_cmd", required=True)

    # list
    p_list = sub_p.add_parser("list", help="List all datasets")
    p_list.set_defaults(func=_list)

    # show
    p_show = sub_p.add_parser("show", help="Show dataset details")
    p_show.add_argument("name", help="Dataset name")
    p_show.add_argument("--items", "-i", action="store_true", help="Show items")
    p_show.set_defaults(func=_show)

    # create
    p_create = sub_p.add_parser("create", help="Create a new dataset")
    p_create.add_argument("name", help="Dataset name")
    p_create.add_argument("--description", "-d", default="", help="Dataset description")
    p_create.add_argument("--tags", "-t", nargs="*", default=[], help="Dataset tags")
    p_create.set_defaults(func=_create)

    # delete
    p_delete = sub_p.add_parser("delete", help="Delete a dataset")
    p_delete.add_argument("name", help="Dataset name")
    p_delete.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p_delete.set_defaults(func=_delete)

    # add-item
    p_add = sub_p.add_parser("add-item", help="Add an item to a dataset")
    p_add.add_argument("name", help="Dataset name")
    p_add.add_argument("--input", "-i", required=True, help="Input data (JSON string)")
    p_add.add_argument("--output", "-o", required=True, help="Output data (JSON string)")
    p_add.add_argument("--metadata", "-m", default="{}", help="Metadata (JSON string)")
    p_add.set_defaults(func=_add_item)


def _get_store(args: argparse.Namespace):
    """Get the dataset store from project root."""
    from forge_agent.datasets.store import LocalDatasetStore

    project_root = Path(args.project) if hasattr(args, "project") else Path.cwd()
    datasets_dir = project_root / "datasets"
    datasets_dir.mkdir(exist_ok=True)
    return LocalDatasetStore(datasets_dir)


def _list(args: argparse.Namespace) -> int:
    """List all datasets."""

    store = _get_store(args)
    names = store.list()

    if not names:
        print("No datasets found.")
        return 0

    print(f"{'NAME':<30} {'ITEMS':<10} {'TAGS':<40}")
    print("-" * 80)

    for name in sorted(names):
        ds = store.load(name)
        if ds is not None:
            items_count = len(ds.items)
            tags_str = ", ".join(ds.tags) if ds.tags else "-"
            print(f"{name:<30} {items_count:<10} {tags_str:<40}")

    return 0


def _show(args: argparse.Namespace) -> int:
    """Show dataset details."""
    store = _get_store(args)
    ds = store.load(args.name)

    if not ds:
        print(f"Dataset '{args.name}' not found.")
        return 1

    print(f"Name:        {ds.name}")
    print(f"Description: {ds.description or '-'}")
    print(f"Tags:        {', '.join(ds.tags) if ds.tags else '-'}")
    print(f"Items:       {len(ds.items)}")
    print(f"Created:     {ds.created_at}")
    print(f"Updated:     {ds.updated_at}")

    if args.items and ds.items:
        print("\nItems:")
        for i, item in enumerate(ds.items, 1):
            print(f"\n  [{i}] ID: {item.id}")
            print(f"      Input:  {json.dumps(item.input, ensure_ascii=False)[:100]}")
            print(f"      Output: {json.dumps(item.output, ensure_ascii=False)[:100]}")
            if item.metadata:
                print(f"      Meta:   {json.dumps(item.metadata, ensure_ascii=False)[:100]}")

    return 0


def _create(args: argparse.Namespace) -> int:
    """Create a new dataset."""
    from forge_agent.datasets import Dataset

    store = _get_store(args)

    if store.exists(args.name):
        print(f"Dataset '{args.name}' already exists.")
        return 1

    ds = Dataset(
        name=args.name,
        description=args.description,
        tags=args.tags,
    )
    store.save(ds)
    print(f"✓ Created dataset '{args.name}'")
    return 0


def _delete(args: argparse.Namespace) -> int:
    """Delete a dataset."""
    store = _get_store(args)

    if not store.exists(args.name):
        print(f"Dataset '{args.name}' not found.")
        return 1

    if not args.yes:
        response = input(f"Delete dataset '{args.name}'? [y/N] ")
        if response.lower() != "y":
            print("Cancelled.")
            return 0

    store.delete(args.name)
    print(f"✓ Deleted dataset '{args.name}'")
    return 0


def _add_item(args: argparse.Namespace) -> int:
    """Add an item to a dataset."""
    from forge_agent.datasets import DatasetItem

    store = _get_store(args)
    ds = store.load(args.name)

    if ds is None:
        print(f"Dataset '{args.name}' not found.")
        return 1

    try:
        input_data = json.loads(args.input)
        output_data = json.loads(args.output)
        metadata = json.loads(args.metadata)
    except json.JSONDecodeError as e:
        print(f"Invalid JSON: {e}")
        return 1

    item = DatasetItem(
        input=input_data,
        output=output_data,
        metadata=metadata,
    )
    ds.add_item(item)
    store.save(ds)

    print(f"✓ Added item to dataset '{args.name}' (ID: {item.id})")
    return 0
