#!/usr/bin/env python3
"""
Medical Entity Extraction - Main Script
Extracts UMLS-based medical entities from clinical notes using OpenAI API
"""

import argparse
import json
import sys
from pathlib import Path
from medical_entity_extractor import MedicalEntityExtractor


def main():
    parser = argparse.ArgumentParser(
        description="Extract medical entities from clinical notes using UMLS and OpenAI API"
    )
    parser.add_argument(
        "input_file",
        type=str,
        help="Path to the medical note text file"
    )
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="Output JSON file path (optional)"
    )
    parser.add_argument(
        "--model",
        "-m",
        type=str,
        default="gpt-4o",
        help="OpenAI model to use (default: gpt-4o)"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        help="OpenAI API key (optional, can use OPENAI_API_KEY env variable)"
    )

    args = parser.parse_args()

    # Read the medical note
    try:
        input_path = Path(args.input_file)
        if not input_path.exists():
            print(f"Error: File not found: {args.input_file}")
            sys.exit(1)

        with open(input_path, 'r', encoding='utf-8') as f:
            medical_note = f.read()

        if not medical_note.strip():
            print("Error: Input file is empty")
            sys.exit(1)

    except Exception as e:
        print(f"Error reading input file: {str(e)}")
        sys.exit(1)

    # Initialize extractor
    try:
        extractor = MedicalEntityExtractor(api_key=args.api_key)
    except ValueError as e:
        print(f"Error: {str(e)}")
        print("\nPlease set your OpenAI API key:")
        print("1. Create a .env file with: OPENAI_API_KEY=your_key")
        print("2. Or use --api-key argument")
        sys.exit(1)

    # Extract entities
    print("Extracting medical entities...")
    print(f"Using model: {args.model}\n")

    try:
        entities = extractor.extract_entities(medical_note, model=args.model)

        # Display formatted output
        formatted_output = extractor.format_output(entities)
        print(formatted_output)

        # Save to JSON if output file specified
        if args.output:
            output_path = Path(args.output)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(entities, f, indent=2, ensure_ascii=False)
            print(f"\n\nJSON output saved to: {output_path}")

        # Print summary statistics
        total_entities = sum(len(v) if isinstance(v, list) else 0 for v in entities.values())
        print(f"\n\nTotal entities extracted: {total_entities}")

    except Exception as e:
        print(f"Error during extraction: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
