"""
USCDI v6 compliant medical data extractor using OpenAI API
"""

import openai
import os
import json
import asyncio
from typing import Dict, Optional, List
from pathlib import Path
from dotenv import load_dotenv
from concurrent.futures import ThreadPoolExecutor

# Load environment variables
load_dotenv()


class USCDIExtractor:
    """
    Extract structured clinical data according to USCDI v6 standard.
    """

    def __init__(self, api_key: str = None):
        """Initialize the extractor with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        self.client = openai.OpenAI(api_key=self.api_key)

        # Load USCDI prompts metadata
        prompts_path = Path(__file__).parent / "uscdi_prompts.json"
        with open(prompts_path, 'r') as f:
            self.uscdi_metadata = json.load(f)

    def _get_api_params(self, model: str, system_prompt: str, user_prompt: str) -> dict:
        """Get API parameters with appropriate temperature based on model."""
        # Reasoning models (o1, o3) only support temperature=1 (default)
        reasoning_models = ['o1', 'o1-mini', 'o1-preview', 'o3-mini']
        use_default_temp = any(rm in model.lower() for rm in reasoning_models)

        params = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "response_format": {"type": "json_object"}
        }

        # Only add temperature for non-reasoning models
        if not use_default_temp:
            params["temperature"] = 0.1

        return params

    def extract_uscdi_data(self, clinical_note: str, model: str = "gpt-4o") -> Dict:
        """
        Extract USCDI v6 compliant data from a clinical note.

        Args:
            clinical_note: The clinical note text
            model: OpenAI model to use (default: gpt-4o)

        Returns:
            Dictionary containing extracted USCDI data elements organized by data classes
        """

        # Build comprehensive USCDI extraction prompt
        system_prompt = self._build_uscdi_system_prompt()
        user_prompt = f"""Extract all USCDI v6 data elements from this clinical note:

{clinical_note}

Return a comprehensive JSON object with all relevant USCDI data classes and elements found in the note."""

        try:
            api_params = self._get_api_params(model, system_prompt, user_prompt)
            response = self.client.chat.completions.create(**api_params)

            extracted_data = json.loads(response.choices[0].message.content)

            # Add metadata
            extracted_data["_metadata"] = {
                "uscdi_version": self.uscdi_metadata["version"],
                "extraction_model": model,
                "data_classes_extracted": list(extracted_data.keys())
            }

            return extracted_data

        except Exception as e:
            raise Exception(f"Error extracting USCDI data: {str(e)}")

    def extract_uscdi_data_parallel(self, clinical_note: str, model: str = "gpt-4o", add_umls_cui: bool = True) -> Dict:
        """
        Extract USCDI v6 data using parallel API calls for faster extraction.
        Optionally enriches extracted concepts with UMLS CUI codes.

        Args:
            clinical_note: The clinical note text
            model: OpenAI model to use (default: gpt-4o)
            add_umls_cui: Whether to add UMLS concept IDs (default: True)

        Returns:
            Dictionary containing extracted USCDI data elements organized by data classes
        """
        # Group data classes into logical batches for parallel extraction
        data_class_groups = [
            ["patient_demographics", "encounter_information", "facility_information"],
            ["problems", "medications", "allergies_and_intolerances"],
            ["vital_signs", "laboratory", "clinical_tests"],
            ["procedures", "diagnostic_imaging", "orders"],
            ["care_plan", "immunizations", "family_health_history"],
            ["care_team_members", "provenance", "health_insurance_information"],
            ["goals_and_preferences", "health_status_assessments", "clinical_notes"],
            ["medical_devices"]
        ]

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for group in data_class_groups:
                future = executor.submit(self._extract_class_group, clinical_note, group, model)
                futures.append(future)

            # Collect results and normalize keys
            combined_data = {}
            for future in futures:
                try:
                    group_data = future.result()
                    # Normalize keys to snake_case
                    normalized_data = self._normalize_keys(group_data)
                    combined_data.update(normalized_data)
                except Exception as e:
                    print(f"Error in parallel extraction: {str(e)}")
                    continue

        # Add UMLS CUI codes if requested
        if add_umls_cui:
            combined_data = self._enrich_with_umls(combined_data, model)

        # Add metadata
        combined_data["_metadata"] = {
            "uscdi_version": self.uscdi_metadata["version"],
            "extraction_model": model,
            "extraction_method": "parallel",
            "umls_enrichment": add_umls_cui,
            "data_classes_extracted": [k for k in combined_data.keys() if not k.startswith('_')]
        }

        return combined_data

    def _normalize_keys(self, data: Dict) -> Dict:
        """Normalize dictionary keys to snake_case."""
        normalized = {}
        for key, value in data.items():
            # Convert "Patient Demographics" -> "patient_demographics"
            normalized_key = key.lower().replace(' ', '_').replace('-', '_')
            normalized[normalized_key] = value
        return normalized

    def _extract_class_group(self, clinical_note: str, class_names: List[str], model: str) -> Dict:
        """Extract a group of data classes in a single API call."""
        classes_str = ", ".join([cn.replace('_', ' ').title() for cn in class_names])

        system_prompt = f"""You are a clinical data extraction system. Extract only the following USCDI v6 data classes: {classes_str}.

Extract all relevant information for these classes only. Return valid JSON with these class names as keys.

IMPORTANT: For each clinical entity, always include a "name" or "text" field with the primary clinical term."""

        user_prompt = f"""Extract {classes_str} from this clinical note:

{clinical_note}

Return JSON with only these data classes populated. Each item should have a "name" field containing the primary term."""

        try:
            api_params = self._get_api_params(model, system_prompt, user_prompt)
            response = self.client.chat.completions.create(**api_params)
            extracted_data = json.loads(response.choices[0].message.content)
            return extracted_data
        except Exception as e:
            print(f"Error extracting {classes_str}: {str(e)}")
            return {}

    def _enrich_with_umls(self, uscdi_data: Dict, model: str) -> Dict:
        """Enrich extracted USCDI data with UMLS CUI codes."""
        import logging
        logger = logging.getLogger(__name__)

        # Classes that benefit from UMLS mapping
        clinical_classes = ["problems", "medications", "allergies_and_intolerances",
                          "procedures", "laboratory", "vital_signs", "diagnostic_imaging",
                          "immunizations", "clinical_tests", "family_health_history"]

        logger.info(f"Starting UMLS enrichment for {len(uscdi_data)} data classes")

        for class_name in clinical_classes:
            if class_name not in uscdi_data:
                logger.info(f"Class '{class_name}' not in extracted data")
                continue

            if not uscdi_data[class_name]:
                logger.info(f"Class '{class_name}' is empty")
                continue

            data = uscdi_data[class_name]
            logger.info(f"Enriching {class_name}: {type(data)} with {len(data) if isinstance(data, list) else 1} items")

            if isinstance(data, list):
                enriched_items = []
                for idx, item in enumerate(data):
                    logger.info(f"  Processing item {idx+1}/{len(data)} in {class_name}")
                    enriched_item = self._add_umls_cui_to_item(item, class_name, model)
                    enriched_items.append(enriched_item)
                uscdi_data[class_name] = enriched_items
            elif isinstance(data, dict):
                uscdi_data[class_name] = self._add_umls_cui_to_item(data, class_name, model)

        logger.info("UMLS enrichment completed")
        return uscdi_data

    def _add_umls_cui_to_item(self, item: Dict, class_name: str, model: str) -> Dict:
        """Add UMLS CUI to a single item."""
        import logging
        logger = logging.getLogger(__name__)

        if not isinstance(item, dict):
            return item

        # Extract the main clinical term from the item
        term_fields = ["name", "text", "medication", "substance", "allergen", "problem",
                      "procedure", "test", "measurement", "condition", "diagnosis",
                      "vaccine", "device", "imaging_type", "type", "description", "term", "drug"]

        clinical_term = None
        term_field_used = None
        for field in term_fields:
            if field in item and item[field] and isinstance(item[field], str):
                clinical_term = item[field]
                term_field_used = field
                logger.info(f"    Found term '{clinical_term}' in field '{field}'")
                break

        # If no term found, try to get the first string value
        if not clinical_term:
            for key, value in item.items():
                if isinstance(value, str) and len(value.strip()) > 2 and not key.startswith('_'):
                    clinical_term = value
                    term_field_used = key
                    logger.info(f"    Found term '{clinical_term}' in fallback field '{key}'")
                    break

        if not clinical_term:
            logger.info(f"    No clinical term found in item: {list(item.keys())}")
            return item

        # Use OpenAI to get UMLS CUI
        logger.info(f"    Getting CUI for '{clinical_term}'")
        cui = self._get_umls_cui(clinical_term, class_name, model)
        if cui and cui != "null":
            item["umls_cui"] = cui
            item["_cui_mapped_from"] = term_field_used
            logger.info(f"    Added CUI: {cui}")
        else:
            logger.info(f"    No CUI found for '{clinical_term}'")

        return item

    def _get_umls_cui(self, term: str, category: str, model: str) -> Optional[str]:
        """Get UMLS CUI for a clinical term using OpenAI."""
        system_prompt = """You are a medical terminology expert. Given a clinical term, return its UMLS Concept Unique Identifier (CUI).

Return ONLY the CUI code (e.g., C0011849) in JSON format: {"cui": "C0011849"}
If no CUI exists, return: {"cui": null}"""

        user_prompt = f"""Clinical term: "{term}"
Category: {category.replace('_', ' ')}

Return the UMLS CUI code."""

        try:
            api_params = self._get_api_params(model, system_prompt, user_prompt)
            response = self.client.chat.completions.create(**api_params)
            result = json.loads(response.choices[0].message.content)
            return result.get("cui")
        except Exception as e:
            return None

    def _build_uscdi_system_prompt(self) -> str:
        """Build comprehensive system prompt for USCDI extraction."""

        # Start with master system prompt if available
        prompt = ""
        if "master_system_prompt" in self.uscdi_metadata:
            prompt += self.uscdi_metadata["master_system_prompt"] + "\n\n"

        # Add global upgrades if available
        if "global_upgrades" in self.uscdi_metadata:
            prompt += "## GLOBAL UPGRADES\n" + self.uscdi_metadata["global_upgrades"] + "\n\n"

        prompt += f"""You are a clinical data extraction system specialized in extracting structured data according to the {self.uscdi_metadata['version']} (United States Core Data for Interoperability) standard.

Your task is to extract clinical information from medical notes and organize it into the following USCDI data classes:

"""

        # Add each data class with its elements and extraction instructions
        for class_name, class_info in self.uscdi_metadata["data_classes"].items():
            prompt += f"\n## {class_name.replace('_', ' ').title()}\n"

            if "description" in class_info:
                prompt += f"{class_info['description']}\n"

            if "elements" in class_info:
                prompt += "Elements to extract:\n"
                for element, description in class_info["elements"].items():
                    prompt += f"  - {element}: {description}\n"

            if "subtypes" in class_info:
                prompt += "Subtypes:\n"
                for subtype, description in class_info["subtypes"].items():
                    prompt += f"  - {subtype}: {description}\n"

            prompt += f"\nExtraction guidance: {class_info['prompt']}\n"

        # Add general instructions
        general_instructions = self.uscdi_metadata["extraction_instructions"]

        prompt += f"""

## General Instructions:
- {general_instructions['general']}"""

        if "output_format" in general_instructions:
            prompt += f"\n- Output format: {general_instructions['output_format']}"
        if "handle_missing_data" in general_instructions:
            prompt += f"\n- Missing data: {general_instructions['handle_missing_data']}"
        if "date_format" in general_instructions:
            prompt += f"\n- Date format: {general_instructions['date_format']}"

        # Add coreference resolution if available
        if "coreference_resolution" in general_instructions:
            prompt += f"\n\n## Coreference Resolution:\n{general_instructions['coreference_resolution']}"

        # Add negation detection if available
        if "negation_detection" in general_instructions:
            prompt += f"\n\n## Negation Detection:\n{general_instructions['negation_detection']}"

        # Add gotchas if available
        if "gotchas" in general_instructions:
            prompt += "\n\n## Important Gotchas:\n"
            for gotcha in general_instructions["gotchas"]:
                prompt += f"- {gotcha}\n"

        # Add coding systems if available
        if "coding_systems" in general_instructions:
            prompt += "\n\n## Standard Coding Systems:\n"
            for data_type, coding_system in general_instructions["coding_systems"].items():
                prompt += f"- {data_type.title()}: {coding_system}\n"

        prompt += """

Return a JSON object with the following structure:
{
  "patient_demographics": {...},
  "allergies_and_intolerances": [...],
  "medications": [...],
  "problems": [...],
  "procedures": [...],
  "vital_signs": [...],
  "laboratory_results": [...],
  "immunizations": [...],
  "clinical_notes": {...},
  "encounter_information": {...},
  "assessment_and_plan_of_treatment": {...},
  ... (include all other relevant USCDI data classes)
}

Only include data classes and elements that are present in the clinical note. Use standard medical codes when possible."""

        return prompt

    def extract_specific_class(
        self,
        clinical_note: str,
        data_class: str,
        model: str = "gpt-4o"
    ) -> Dict:
        """
        Extract data for a specific USCDI data class.

        Args:
            clinical_note: The clinical note text
            data_class: USCDI data class to extract (e.g., 'medications', 'vital_signs')
            model: OpenAI model to use

        Returns:
            Dictionary containing extracted data for the specified class
        """

        if data_class not in self.uscdi_metadata["data_classes"]:
            raise ValueError(f"Invalid data class: {data_class}. Must be one of: {list(self.uscdi_metadata['data_classes'].keys())}")

        class_info = self.uscdi_metadata["data_classes"][data_class]

        system_prompt = f"""You are a clinical data extraction system. Extract {class_info['description'].lower()} from clinical notes according to USCDI v6 standard.

{class_info['prompt']}

"""

        if "elements" in class_info:
            system_prompt += "\nExtract the following elements:\n"
            for element, description in class_info["elements"].items():
                system_prompt += f"- {element}: {description}\n"

        system_prompt += "\nReturn your response as a valid JSON object."

        user_prompt = f"""Extract {data_class.replace('_', ' ')} from this clinical note:

{clinical_note}"""

        try:
            api_params = self._get_api_params(model, system_prompt, user_prompt)
            response = self.client.chat.completions.create(**api_params)

            extracted_data = json.loads(response.choices[0].message.content)
            return extracted_data

        except Exception as e:
            raise Exception(f"Error extracting {data_class}: {str(e)}")

    def get_available_data_classes(self) -> Dict[str, str]:
        """Get list of available USCDI data classes with descriptions."""
        return {
            class_name: class_info["description"]
            for class_name, class_info in self.uscdi_metadata["data_classes"].items()
        }

    def format_uscdi_output(self, uscdi_data: Dict) -> str:
        """Format USCDI extracted data for readable display."""
        output = []
        output.append("=" * 80)
        output.append(f"USCDI {uscdi_data.get('_metadata', {}).get('uscdi_version', 'v6')} DATA EXTRACTION")
        output.append("=" * 80)

        # Remove metadata for display
        display_data = {k: v for k, v in uscdi_data.items() if not k.startswith('_')}

        for class_name, class_data in display_data.items():
            if not class_data:
                continue

            output.append(f"\n{class_name.replace('_', ' ').upper()}")
            output.append("-" * 80)

            if isinstance(class_data, list):
                for item in class_data:
                    output.append(json.dumps(item, indent=2))
                    output.append("")
            elif isinstance(class_data, dict):
                output.append(json.dumps(class_data, indent=2))
                output.append("")

        return "\n".join(output)
