"""
Tests for release.dataset.attach_metadata.
"""

import pytest
from release.dataset.attach_metadata import condition_for, ra_condition_for, block_meta


class TestPrimaryVsRA:
    """Test primary vs secondary RA condition labels."""

    def test_condition_for_subject_4_is_E(self):
        """Subject 4 is in the published cohort as E."""
        assert condition_for(4) == "E"

    def test_ra_condition_for_subject_4_is_oracle(self):
        """Subject 4 has RA override to Oracle (unresolved)."""
        assert ra_condition_for(4) == "Oracle"

    def test_condition_for_subject_5_is_IE(self):
        """Subject 5 is in the published cohort as IE."""
        assert condition_for(5) == "IE"

    def test_ra_condition_for_subject_5_is_control(self):
        """Subject 5 has RA override to Control (unresolved)."""
        assert ra_condition_for(5) == "Control"

    def test_condition_for_unknown_subject(self):
        """Unknown subject should return 'unknown'."""
        assert condition_for(9999) == "unknown"

    def test_ra_condition_for_unknown_subject(self):
        """Unknown subject should return None."""
        assert ra_condition_for(9999) is None

    def test_ra_condition_for_subject_without_override(self):
        """Subject in cohort but without RA override should return published label."""
        # Find a subject in the cohort that doesn't have an RA override.
        # From condition_corrections, subject 20 is IE but has no override.
        assert ra_condition_for(20) == "IE"


class TestBlockMeta:
    """Test block metadata reading."""

    def test_block_meta_missing_subject(self):
        """Non-existent subject should return default difficulty and block_marker."""
        result = block_meta(9999, "us2", 0)
        assert result == {"difficulty": -1, "block_marker": -1}

    def test_block_meta_missing_block(self):
        """Non-existent block should return default difficulty and block_marker."""
        result = block_meta(4, "us99", 999)
        assert result == {"difficulty": -1, "block_marker": -1}

    def test_block_meta_existing_block(self):
        """Existing block should return its difficulty and block_marker (if available)."""
        # Subject 4 has us1/us2/us3 data; try us1 block 0 which should exist.
        result = block_meta(4, "us1", 0)
        assert isinstance(result, dict)
        assert "difficulty" in result
        assert "block_marker" in result
        assert isinstance(result["difficulty"], int)
        assert isinstance(result["block_marker"], int)

    def test_block_meta_session_subdir(self):
        """Session-subdir blocks should be found and return correct metadata.

        P5/us1 has session subdirs (0, 1); block 33 is a SpaceShooter block
        (block_marker=10) with difficulty>=0 in session 0.
        """
        result = block_meta(5, "us1", 33)
        assert isinstance(result, dict)
        assert "difficulty" in result
        assert "block_marker" in result
        assert result["difficulty"] >= 0, "SpaceShooter block should have difficulty >= 0"
        assert result["block_marker"] == 10, "SpaceShooter blocks have block_marker == 10"
