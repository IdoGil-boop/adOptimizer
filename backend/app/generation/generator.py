"""Ad copy generation with OpenAI and RSA constraints."""

import logging
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI

from app.config import get_settings
from app.models import Ad

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class RSAConstraints:
    """Google Responsive Search Ad (RSA) constraints."""

    max_headline_length: int = 30
    max_description_length: int = 90
    min_headlines: int = 3
    max_headlines: int = 15
    min_descriptions: int = 2
    max_descriptions: int = 4
    require_unique: bool = True  # Headlines and descriptions must be unique


@dataclass
class GeneratedRSA:
    """Generated RSA with metadata."""

    headlines: list[str]
    descriptions: list[str]
    prompt_version: str
    model_used: str
    exemplar_ids: list[int]
    similarity_scores: list[float]
    valid: bool = True
    validation_errors: list[str] = None

    def __post_init__(self):
        if self.validation_errors is None:
            self.validation_errors = []


class RSAGenerator:
    """Generate RSA-compliant ad copy using OpenAI with exemplar bias."""

    PROMPT_VERSION = "v1.0"

    def __init__(self):
        """Initialize OpenAI client."""
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model = "gpt-4o-mini"  # Fast and cost-effective
        self.constraints = RSAConstraints()

    def generate_suggestions(
        self,
        target_ad: Ad,
        exemplar_ads: list[tuple[Ad, float]],
        num_variants: int = 3,
    ) -> list[GeneratedRSA]:
        """
        Generate RSA suggestions for a target ad based on exemplar ads.

        Args:
            target_ad: The ad to improve
            exemplar_ads: List of (exemplar_ad, similarity_score) tuples
            num_variants: Number of variants to generate

        Returns:
            List of GeneratedRSA objects with suggestions
        """
        if not exemplar_ads:
            logger.warning(f"No exemplars provided for ad {target_ad.id}")
            return []

        # Build prompt with exemplars
        prompt = self._build_prompt(target_ad, exemplar_ads, num_variants)

        try:
            # Generate suggestions
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert Google Ads copywriter specializing in Responsive Search Ads. "
                        "Your goal is to create compelling, conversion-focused ad copy that follows RSA best practices.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.8,  # More creative
                max_tokens=1500,
                n=1,
            )

            # Parse response
            generated_text = response.choices[0].message.content
            suggestions = self._parse_response(
                generated_text, exemplar_ads, num_variants
            )

            # Validate each suggestion
            for suggestion in suggestions:
                self._validate_rsa(suggestion)

            logger.info(
                f"Generated {len(suggestions)} suggestions for ad {target_ad.id}"
            )
            return suggestions

        except Exception as e:
            logger.error(f"Failed to generate suggestions for ad {target_ad.id}: {e}")
            return []

    def _build_prompt(
        self,
        target_ad: Ad,
        exemplar_ads: list[tuple[Ad, float]],
        num_variants: int,
    ) -> str:
        """Build prompt with exemplars and constraints."""
        # Extract current ad copy
        current_headlines = []
        current_descriptions = []

        if target_ad.headlines:
            current_headlines = [
                h.get("text", "") for h in target_ad.headlines if isinstance(h, dict)
            ]
        if target_ad.descriptions:
            current_descriptions = [
                d.get("text", "") for d in target_ad.descriptions if isinstance(d, dict)
            ]

        # Extract exemplar copy
        exemplar_texts = []
        for i, (ad, score) in enumerate(exemplar_ads[:5], 1):
            ex_headlines = []
            ex_descriptions = []

            if ad.headlines:
                ex_headlines = [
                    h.get("text", "") for h in ad.headlines if isinstance(h, dict)
                ]
            if ad.descriptions:
                ex_descriptions = [
                    d.get("text", "") for d in ad.descriptions if isinstance(d, dict)
                ]

            exemplar_texts.append(
                f"High-Performing Example {i} (similarity: {score:.2f}):\n"
                f"Headlines: {', '.join(ex_headlines[:5])}\n"
                f"Descriptions: {', '.join(ex_descriptions[:2])}"
            )

        exemplars_section = "\n\n".join(exemplar_texts)

        prompt = f"""
I need to improve a low-performing Google Responsive Search Ad (RSA). Below is the current ad copy, followed by examples of high-performing ads from the same account.

**Current Ad (Needs Improvement):**
Headlines: {', '.join(current_headlines) if current_headlines else 'None'}
Descriptions: {', '.join(current_descriptions) if current_descriptions else 'None'}

**High-Performing Ads (Learn from these):**
{exemplars_section}

**Task:**
Generate {num_variants} improved RSA variants that:
1. Learn from the patterns and messaging in high-performing examples
2. Maintain similar tone, value propositions, and keyword usage
3. Improve upon the current ad's weaknesses
4. Follow RSA best practices (clear CTA, benefits-focused, specific)

**Strict Constraints:**
- Each headline: maximum {self.constraints.max_headline_length} characters
- Each description: maximum {self.constraints.max_description_length} characters
- Provide {self.constraints.min_headlines}-{self.constraints.max_headlines} headlines per variant
- Provide {self.constraints.min_descriptions}-{self.constraints.max_descriptions} descriptions per variant
- All headlines must be unique (no duplicates)
- All descriptions must be unique (no duplicates)

**Output Format:**
For each variant, output exactly like this:

VARIANT 1
HEADLINES:
- [Headline 1]
- [Headline 2]
- [Headline 3]
...
DESCRIPTIONS:
- [Description 1]
- [Description 2]
...

VARIANT 2
...

Be specific, compelling, and ensure all constraints are met.
"""
        return prompt

    def _parse_response(
        self,
        generated_text: str,
        exemplar_ads: list[tuple[Ad, float]],
        expected_variants: int,
    ) -> list[GeneratedRSA]:
        """Parse OpenAI response into structured RSA objects."""
        suggestions = []
        lines = generated_text.strip().split("\n")

        current_variant = None
        current_section = None  # 'headlines' or 'descriptions'

        for line in lines:
            line = line.strip()

            if not line:
                continue

            # Detect variant start
            if line.upper().startswith("VARIANT"):
                if current_variant:
                    suggestions.append(current_variant)

                current_variant = GeneratedRSA(
                    headlines=[],
                    descriptions=[],
                    prompt_version=self.PROMPT_VERSION,
                    model_used=self.model,
                    exemplar_ids=[ad.id for ad, _ in exemplar_ads],
                    similarity_scores=[score for _, score in exemplar_ads],
                )
                current_section = None
                continue

            # Detect section headers
            if line.upper().startswith("HEADLINES"):
                current_section = "headlines"
                continue
            if line.upper().startswith("DESCRIPTIONS"):
                current_section = "descriptions"
                continue

            # Parse content lines
            if current_variant and line.startswith("-"):
                text = line[1:].strip()
                if current_section == "headlines":
                    current_variant.headlines.append(text)
                elif current_section == "descriptions":
                    current_variant.descriptions.append(text)

        # Add last variant
        if current_variant:
            suggestions.append(current_variant)

        logger.info(
            f"Parsed {len(suggestions)} variants from OpenAI response (expected {expected_variants})"
        )
        return suggestions

    def _validate_rsa(self, rsa: GeneratedRSA) -> None:
        """Validate RSA against constraints and update valid flag."""
        errors = []

        # Check headline count
        if len(rsa.headlines) < self.constraints.min_headlines:
            errors.append(
                f"Too few headlines: {len(rsa.headlines)} < {self.constraints.min_headlines}"
            )
        if len(rsa.headlines) > self.constraints.max_headlines:
            errors.append(
                f"Too many headlines: {len(rsa.headlines)} > {self.constraints.max_headlines}"
            )

        # Check description count
        if len(rsa.descriptions) < self.constraints.min_descriptions:
            errors.append(
                f"Too few descriptions: {len(rsa.descriptions)} < {self.constraints.min_descriptions}"
            )
        if len(rsa.descriptions) > self.constraints.max_descriptions:
            errors.append(
                f"Too many descriptions: {len(rsa.descriptions)} > {self.constraints.max_descriptions}"
            )

        # Check headline lengths
        for i, headline in enumerate(rsa.headlines):
            if len(headline) > self.constraints.max_headline_length:
                errors.append(
                    f"Headline {i+1} too long: {len(headline)} > {self.constraints.max_headline_length}"
                )
                # Truncate
                rsa.headlines[i] = headline[: self.constraints.max_headline_length]

        # Check description lengths
        for i, desc in enumerate(rsa.descriptions):
            if len(desc) > self.constraints.max_description_length:
                errors.append(
                    f"Description {i+1} too long: {len(desc)} > {self.constraints.max_description_length}"
                )
                # Truncate
                rsa.descriptions[i] = desc[: self.constraints.max_description_length]

        # Check uniqueness
        if self.constraints.require_unique:
            if len(rsa.headlines) != len(set(rsa.headlines)):
                errors.append("Headlines contain duplicates")
            if len(rsa.descriptions) != len(set(rsa.descriptions)):
                errors.append("Descriptions contain duplicates")

        rsa.validation_errors = errors
        rsa.valid = len(errors) == 0

        if errors:
            logger.warning(f"RSA validation errors: {errors}")


def generate_suggestions_for_ad(
    target_ad: Ad, exemplar_ads: list[tuple[Ad, float]], num_variants: int = 3
) -> list[GeneratedRSA]:
    """Convenience function to generate suggestions for a single ad."""
    generator = RSAGenerator()
    return generator.generate_suggestions(target_ad, exemplar_ads, num_variants)
