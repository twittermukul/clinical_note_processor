import openai
import os
import json
from typing import Dict, List
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class MedicalEntityExtractor:
    """
    Extract medical entities from clinical notes using OpenAI API and UMLS semantic types.
    """

    def __init__(self, api_key: str = None):
        """Initialize the extractor with OpenAI API key."""
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key not found. Set OPENAI_API_KEY environment variable.")

        self.client = openai.OpenAI(api_key=self.api_key)

    def extract_entities(self, medical_note: str, model: str = "gpt-4o") -> Dict:
        """
        Extract medical entities from a clinical note using UMLS semantic types.

        Args:
            medical_note: The clinical note text
            model: OpenAI model to use (default: gpt-4o)

        Returns:
            Dictionary containing extracted entities organized by UMLS semantic types
        """

        system_prompt = """You are a medical entity extraction system trained to identify clinical entities based on UMLS (Unified Medical Language System) semantic types.

Extract ALL relevant medical entities from the clinical note and categorize them according to these UMLS semantic types:

1. **Disorders/Diseases**: Medical conditions, diagnoses, syndromes
2. **Signs and Symptoms**: Clinical findings, symptoms, vital signs
3. **Procedures**: Medical procedures, surgeries, therapeutic interventions
4. **Medications/Drugs**: Pharmaceuticals, drugs, medications
5. **Anatomy**: Body parts, organs, anatomical structures
6. **Laboratory Results**: Lab values, test results, measurements
7. **Medical Devices**: Equipment, devices, implants
8. **Organisms**: Bacteria, viruses, microorganisms
9. **Substances**: Chemical substances, biological substances
10. **Temporal Information**: Dates, durations, frequencies

Return your response as a valid JSON object with this structure:
{
  "disorders": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "signs_symptoms": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "procedures": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "medications": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "anatomy": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "lab_results": [{"text": "entity text", "value": "value if present", "context": "brief context"}],
  "devices": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "organisms": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "substances": [{"text": "entity text", "cui": "UMLS CUI if known", "context": "brief context"}],
  "temporal": [{"text": "entity text", "context": "brief context"}]
}

If a CUI is not confidently known, use null. Provide brief context showing how the entity appears in the note."""

        user_prompt = f"""Extract all medical entities from this clinical note:

{medical_note}

Return only the JSON object, no additional text."""

        try:
            # Reasoning models (o1, o3) only support temperature=1 (default)
            reasoning_models = ['o1', 'o1-mini', 'o1-preview', 'o3-mini']
            use_default_temp = any(rm in model.lower() for rm in reasoning_models)

            api_params = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "response_format": {"type": "json_object"}
            }

            # Only add temperature for non-reasoning models
            if not use_default_temp:
                api_params["temperature"] = 0.1

            response = self.client.chat.completions.create(**api_params)

            extracted_data = json.loads(response.choices[0].message.content)
            return extracted_data

        except Exception as e:
            raise Exception(f"Error extracting entities: {str(e)}")

    def format_output(self, entities: Dict) -> str:
        """Format extracted entities for readable display."""
        output = []
        output.append("=" * 80)
        output.append("MEDICAL ENTITY EXTRACTION RESULTS")
        output.append("=" * 80)

        category_names = {
            "disorders": "Disorders/Diseases",
            "signs_symptoms": "Signs & Symptoms",
            "procedures": "Procedures",
            "medications": "Medications/Drugs",
            "anatomy": "Anatomical Structures",
            "lab_results": "Laboratory Results",
            "devices": "Medical Devices",
            "organisms": "Organisms",
            "substances": "Substances",
            "temporal": "Temporal Information"
        }

        for key, name in category_names.items():
            if key in entities and entities[key]:
                output.append(f"\n{name}:")
                output.append("-" * 80)
                for entity in entities[key]:
                    output.append(f"  • {entity.get('text', 'N/A')}")
                    if entity.get('cui'):
                        output.append(f"    CUI: {entity['cui']}")
                    if entity.get('value'):
                        output.append(f"    Value: {entity['value']}")
                    if entity.get('context'):
                        output.append(f"    Context: {entity['context']}")
                    output.append("")

        return "\n".join(output)
