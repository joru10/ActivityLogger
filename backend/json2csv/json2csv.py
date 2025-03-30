#!/usr/bin/env python3

import json
import csv
import os
from typing import Dict, List, Any, Union
from pathlib import Path

class JSON2CSV:
    def __init__(self):
        self.fieldnames: List[str] = []

    def _extract_fields(self, data: Union[List[Dict], Dict]) -> List[str]:
        """Extract all unique field names from the JSON data"""
        fields = set()

        def process_item(item: Dict):
            for key, value in item.items():
                if isinstance(value, (str, int, float, bool)) or value is None:
                    fields.add(key)

        if isinstance(data, dict):
            process_item(data)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    process_item(item)

        return sorted(list(fields))

    def _flatten_data(self, data: Union[List[Dict], Dict]) -> List[Dict]:
        """Convert JSON data into a flat list of dictionaries"""
        flattened = []

        def flatten_item(item: Dict) -> Dict:
            return {k: v for k, v in item.items() 
                   if isinstance(v, (str, int, float, bool)) or v is None}

        if isinstance(data, dict):
            flattened.append(flatten_item(data))
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    flattened.append(flatten_item(item))

        return flattened

    def convert_file(self, input_file: str, output_file: str = None) -> str:
        """Convert a JSON file to CSV format

        Args:
            input_file: Path to the input JSON file
            output_file: Optional path to the output CSV file. If not provided,
                        will use the same name as input file with .csv extension

        Returns:
            Path to the created CSV file
        """
        if not output_file:
            output_file = str(Path(input_file).with_suffix('.csv'))

        try:
            # Read JSON data
            with open(input_file, 'r') as f:
                data = json.load(f)

            # Extract fields and flatten data
            self.fieldnames = self._extract_fields(data)
            flattened_data = self._flatten_data(data)

            # Write CSV file
            with open(output_file, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames)
                writer.writeheader()
                writer.writerows(flattened_data)

            return output_file

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in {input_file}: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Error converting {input_file}: {str(e)}")

    def convert_session_buddy_export(self, input_file: str, output_file: str = None) -> str:
        """Convert a Session Buddy export JSON file to CSV format

        Args:
            input_file: Path to the Session Buddy JSON export file
            output_file: Optional path to the output CSV file

        Returns:
            Path to the created CSV file
        """
        if not output_file:
            output_file = str(Path(input_file).with_suffix('.csv'))

        try:
            # Read JSON data
            with open(input_file, 'r') as f:
                data = json.load(f)

            # Write CSV file
            with open(output_file, 'w', newline='') as f:
                writer = csv.writer(f)

                # Write header
                writer.writerow(["CollectionID", "FolderID", "FolderCreated", 
                               "FolderUpdated", "LinkID", "TabTitle", "TabURL", "FavIconURL"])

                # Write data rows
                for collection in data['collections']:
                    for folder in collection['folders']:
                        for link in folder.get('links', []):
                            writer.writerow([
                                collection['id'],
                                folder['id'],
                                collection['created'],
                                collection['updated'],
                                link['id'],
                                link['title'],
                                link['url'],
                                link.get('favIconUrl', '')
                            ])

            return output_file

        except Exception as e:
            raise RuntimeError(f"Error converting Session Buddy export: {str(e)}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Convert JSON files to CSV format')
    parser.add_argument('input', help='Input JSON file')
    parser.add_argument('-o', '--output', help='Output CSV file (optional)')
    parser.add_argument('--session-buddy', action='store_true', 
                        help='Process as Session Buddy export format')
    args = parser.parse_args()

    converter = JSON2CSV()

    try:
        if args.session_buddy:
            output = converter.convert_session_buddy_export(args.input, args.output)
        else:
            output = converter.convert_file(args.input, args.output)
        print(f"Successfully converted {args.input} to {output}")
        return 0

    except Exception as e:
        print(f"Error: {str(e)}")
        return 1

if __name__ == '__main__':
    exit(main())