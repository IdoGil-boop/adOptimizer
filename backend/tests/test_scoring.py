"""Tests for ad performance scoring logic."""

import pytest
from datetime import datetime

from app.analysis.scoring import compute_ad_score, ScoringConfig, AdBucket
from app.models import Ad, AdMetrics90d


class TestAdScoring:
    """Test suite for ad scoring algorithm."""

    @pytest.fixture
    def config(self):
        """Default scoring config."""
        return ScoringConfig(
            min_impressions=100,
            min_clicks=10,
        )

    @pytest.fixture
    def high_performing_ad(self):
        """Create a high-performing ad with metrics."""
        ad = Ad(
            id=1,
            ad_id="123",
            ad_type="RESPONSIVE_SEARCH_AD",
            status="ENABLED",
        )

        metrics = AdMetrics90d(
            ad_id=1,
            impressions=10000,
            clicks=500,
            cost_micros=5000000,  # $5
            conversions=50.0,
            all_conversions=55.0,
            ctr=5.0,  # 5%
            average_cpc=0.01,  # $0.01
            conversion_rate=10.0,  # 10%
            cost_per_conversion=0.10,  # $0.10
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        return ad, metrics

    @pytest.fixture
    def low_performing_ad(self):
        """Create a low-performing ad with metrics."""
        ad = Ad(
            id=2,
            ad_id="456",
            ad_type="RESPONSIVE_SEARCH_AD",
            status="ENABLED",
        )

        metrics = AdMetrics90d(
            ad_id=2,
            impressions=1000,
            clicks=20,
            cost_micros=500000,  # $0.50
            conversions=1.0,
            all_conversions=1.0,
            ctr=2.0,  # 2%
            average_cpc=0.025,  # $0.025
            conversion_rate=5.0,  # 5%
            cost_per_conversion=0.50,  # $0.50
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        return ad, metrics

    def test_high_performing_ad_scores_high(self, high_performing_ad, config):
        """High-performing ad should have high composite score."""
        ad, metrics = high_performing_ad
        score = compute_ad_score(ad, metrics, config)

        assert score is not None
        assert score.score > 0.5  # Should be in upper half
        assert score.bucket == AdBucket.UNKNOWN  # Bucket set later
        assert "CTR" in score.explanation
        assert "CVR" in score.explanation

    def test_low_performing_ad_scores_low(self, low_performing_ad, config):
        """Low-performing ad should have lower composite score."""
        ad, metrics = low_performing_ad
        score = compute_ad_score(ad, metrics, config)

        assert score is not None
        assert score.score < 0.5  # Should be in lower half

    def test_insufficient_impressions_returns_unknown(self, config):
        """Ad below minimum impressions threshold should be UNKNOWN."""
        ad = Ad(id=3, ad_id="789", ad_type="RSA", status="ENABLED")
        metrics = AdMetrics90d(
            ad_id=3,
            impressions=50,  # Below min_impressions=100
            clicks=5,
            cost_micros=10000,
            conversions=0.0,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        score = compute_ad_score(ad, metrics, config)

        assert score.bucket == AdBucket.UNKNOWN
        assert score.score == 0.0
        assert "Insufficient impressions" in score.explanation

    def test_insufficient_clicks_returns_unknown(self, config):
        """Ad below minimum clicks threshold should be UNKNOWN."""
        ad = Ad(id=4, ad_id="101", ad_type="RSA", status="ENABLED")
        metrics = AdMetrics90d(
            ad_id=4,
            impressions=1000,  # Enough impressions
            clicks=5,  # Below min_clicks=10
            cost_micros=10000,
            conversions=0.0,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        score = compute_ad_score(ad, metrics, config)

        assert score.bucket == AdBucket.UNKNOWN
        assert "Insufficient clicks" in score.explanation

    def test_zero_conversions_handles_gracefully(self, config):
        """Ad with 0 conversions should not crash."""
        ad = Ad(id=5, ad_id="102", ad_type="RSA", status="ENABLED")
        metrics = AdMetrics90d(
            ad_id=5,
            impressions=1000,
            clicks=50,
            cost_micros=100000,
            conversions=0.0,  # Zero conversions
            all_conversions=0.0,
            conversion_rate=0.0,
            cost_per_conversion=None,  # No CPA
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        score = compute_ad_score(ad, metrics, config)

        assert score is not None
        assert score.score >= 0.0  # Should handle gracefully
        # CPA score component should be 0 (no conversions)

    def test_volume_score_rewards_high_impressions(self, config):
        """Higher impression volume should increase score."""
        ad1 = Ad(id=6, ad_id="200", ad_type="RSA", status="ENABLED")
        metrics1 = AdMetrics90d(
            ad_id=6,
            impressions=1000,  # Lower volume
            clicks=50,
            ctr=5.0,
            conversion_rate=10.0,
            cost_per_conversion=0.50,
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        ad2 = Ad(id=7, ad_id="201", ad_type="RSA", status="ENABLED")
        metrics2 = AdMetrics90d(
            ad_id=7,
            impressions=100000,  # Much higher volume
            clicks=5000,
            ctr=5.0,  # Same CTR
            conversion_rate=10.0,  # Same CVR
            cost_per_conversion=0.50,  # Same CPA
            period_start=datetime(2024, 1, 1),
            period_end=datetime(2024, 3, 31),
        )

        score1 = compute_ad_score(ad1, metrics1, config)
        score2 = compute_ad_score(ad2, metrics2, config)

        # Ad2 should score higher due to volume component
        assert score2.score > score1.score

    def test_scoring_weights_sum_to_one(self, config):
        """Scoring weights should sum to 1.0."""
        total_weight = (
            config.weight_ctr
            + config.weight_conversion_rate
            + config.weight_cost_per_conversion
            + config.weight_volume
        )
        assert abs(total_weight - 1.0) < 0.001  # Floating point tolerance
