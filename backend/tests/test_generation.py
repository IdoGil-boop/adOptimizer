"""Tests for RSA generation and validation."""

import pytest

from app.generation.generator import RSAGenerator, RSAConstraints, GeneratedRSA
from app.models import Ad


class TestRSAConstraints:
    """Test RSA constraint validation."""

    @pytest.fixture
    def generator(self):
        """Create RSA generator."""
        return RSAGenerator()

    @pytest.fixture
    def valid_rsa(self):
        """Valid RSA variant."""
        return GeneratedRSA(
            headlines=[
                "Best Phone System 2024",
                "Top VoIP Provider",
                "Get Started Free",
            ],
            descriptions=[
                "Cloud-based business phone with advanced features. Try risk-free today!",
                "Trusted by 50,000+ businesses. 24/7 support included. Cancel anytime.",
            ],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1, 2, 3],
            similarity_scores=[0.9, 0.85, 0.8],
        )

    def test_valid_rsa_passes_validation(self, generator, valid_rsa):
        """Valid RSA should pass all constraints."""
        generator._validate_rsa(valid_rsa)

        assert valid_rsa.valid
        assert len(valid_rsa.validation_errors) == 0

    def test_too_few_headlines_fails(self, generator):
        """RSA with < 3 headlines should fail."""
        rsa = GeneratedRSA(
            headlines=["Only One", "Only Two"],  # Need minimum 3
            descriptions=["Description 1", "Description 2"],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        assert not rsa.valid
        assert any("Too few headlines" in err for err in rsa.validation_errors)

    def test_too_many_headlines_fails(self, generator):
        """RSA with > 15 headlines should fail."""
        rsa = GeneratedRSA(
            headlines=[f"Headline {i}" for i in range(20)],  # Max is 15
            descriptions=["Description 1", "Description 2"],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        assert not rsa.valid
        assert any("Too many headlines" in err for err in rsa.validation_errors)

    def test_headline_too_long_gets_truncated(self, generator):
        """Headline > 30 chars should be truncated."""
        long_headline = "This is a very long headline that exceeds thirty characters"

        rsa = GeneratedRSA(
            headlines=[long_headline, "Normal", "Good"],
            descriptions=["Description 1", "Description 2"],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        # Should truncate
        assert len(rsa.headlines[0]) <= 30
        assert not rsa.valid  # But mark as invalid due to error
        assert any("too long" in err for err in rsa.validation_errors)

    def test_description_too_long_gets_truncated(self, generator):
        """Description > 90 chars should be truncated."""
        long_desc = (
            "This is an extremely long description that goes well beyond "
            "the ninety character limit for Google Ads responsive search ads"
        )

        rsa = GeneratedRSA(
            headlines=["One", "Two", "Three"],
            descriptions=[long_desc, "Normal description"],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        assert len(rsa.descriptions[0]) <= 90
        assert not rsa.valid

    def test_duplicate_headlines_fail(self, generator):
        """Duplicate headlines should fail uniqueness check."""
        rsa = GeneratedRSA(
            headlines=["Same Headline", "Same Headline", "Different"],
            descriptions=["Description 1", "Description 2"],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        assert not rsa.valid
        assert any("duplicates" in err.lower() for err in rsa.validation_errors)

    def test_duplicate_descriptions_fail(self, generator):
        """Duplicate descriptions should fail uniqueness check."""
        rsa = GeneratedRSA(
            headlines=["One", "Two", "Three"],
            descriptions=["Same description", "Same description"],
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        assert not rsa.valid
        assert any("duplicates" in err.lower() for err in rsa.validation_errors)

    def test_minimum_requirements_met(self, generator):
        """Minimum 3 headlines and 2 descriptions."""
        rsa = GeneratedRSA(
            headlines=["One", "Two", "Three"],  # Exactly minimum
            descriptions=["Description 1", "Description 2"],  # Exactly minimum
            prompt_version="v1.0",
            model_used="gpt-4o-mini",
            exemplar_ids=[1],
            similarity_scores=[0.9],
        )

        generator._validate_rsa(rsa)

        assert rsa.valid
        assert len(rsa.validation_errors) == 0


class TestRSAPromptBuilder:
    """Test prompt construction."""

    @pytest.fixture
    def generator(self):
        """Create RSA generator."""
        return RSAGenerator()

    @pytest.fixture
    def target_ad(self):
        """Target ad for improvement."""
        return Ad(
            id=1,
            ad_id="123",
            ad_type="RESPONSIVE_SEARCH_AD",
            status="ENABLED",
            headlines=[
                {"text": "Old Headline 1"},
                {"text": "Old Headline 2"},
                {"text": "Old Headline 3"},
            ],
            descriptions=[
                {"text": "Old description number one."},
                {"text": "Old description number two."},
            ],
        )

    @pytest.fixture
    def exemplar_ads(self):
        """High-performing exemplar ads."""
        ad1 = Ad(
            id=10,
            ad_id="ex1",
            ad_type="RSA",
            status="ENABLED",
            headlines=[
                {"text": "Best Phone System"},
                {"text": "Top VoIP Solution"},
                {"text": "Try Free Today"},
            ],
            descriptions=[
                {"text": "Cloud-based business phone. 24/7 support included."},
            ],
        )

        ad2 = Ad(
            id=11,
            ad_id="ex2",
            ad_type="RSA",
            status="ENABLED",
            headlines=[
                {"text": "Get Started Free"},
                {"text": "No Setup Fees"},
            ],
            descriptions=[
                {"text": "Trusted by 50,000+ businesses worldwide."},
            ],
        )

        return [(ad1, 0.92), (ad2, 0.87)]

    def test_prompt_includes_current_ad(self, generator, target_ad, exemplar_ads):
        """Prompt should include current ad copy."""
        prompt = generator._build_prompt(target_ad, exemplar_ads, num_variants=3)

        assert "Old Headline 1" in prompt
        assert "Old description number one" in prompt

    def test_prompt_includes_exemplars(self, generator, target_ad, exemplar_ads):
        """Prompt should include exemplar ad copy."""
        prompt = generator._build_prompt(target_ad, exemplar_ads, num_variants=3)

        assert "Best Phone System" in prompt
        assert "similarity: 0.92" in prompt
        assert "Get Started Free" in prompt

    def test_prompt_includes_constraints(self, generator, target_ad, exemplar_ads):
        """Prompt should specify RSA constraints."""
        prompt = generator._build_prompt(target_ad, exemplar_ads, num_variants=3)

        assert "30 characters" in prompt.lower() or "30-char" in prompt.lower()
        assert "90 characters" in prompt.lower() or "90-char" in prompt.lower()
        assert "unique" in prompt.lower()

    def test_prompt_specifies_variant_count(self, generator, target_ad, exemplar_ads):
        """Prompt should request correct number of variants."""
        prompt = generator._build_prompt(target_ad, exemplar_ads, num_variants=5)

        assert "5" in prompt or "five" in prompt.lower()
