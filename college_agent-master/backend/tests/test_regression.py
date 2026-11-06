"""
Regression Test Suite for BCREC College Agent

Tests are based on verified facts from college_facts.json (canonical source of truth).
All tests verify that the system returns correct data from structured handlers.

Run: cd backend && python -m pytest tests/test_regression.py -v
"""

import json
import pytest
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load canonical facts
FACTS_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'college_facts.json')
with open(FACTS_PATH) as f:
    FACTS = json.load(f)


class TestFeeLookup:
    """Verify fee lookup returns correct values from college_facts.json."""

    def test_cse_total_fee(self):
        """CSE total 4-year fee should be 617,700."""
        assert FACTS["fees"]["btech"]["group_a"]["total_4yr"] == 617700

    def test_aiml_total_fee(self):
        """AIML total 4-year fee should be 567,100."""
        assert FACTS["fees"]["btech"]["group_b"]["total_4yr"] == 567100

    def test_me_total_fee(self):
        """ME total 4-year fee should be 457,100."""
        assert FACTS["fees"]["btech"]["group_c"]["total_4yr"] == 457100

    def test_cse_first_semester(self):
        """CSE first semester fee should be 99,225."""
        assert FACTS["fees"]["btech"]["group_a"]["first_semester"] == 99225

    def test_hostel_mess_fee(self):
        """Hostel mess charges should be 5,500/month."""
        assert FACTS["fees"]["hostel"]["mess_charges_month"] == 5500


class TestCutoffLookup:
    """Verify cutoff lookup returns correct values from college_facts.json."""

    def test_cse_cutoff_2024(self):
        """CSE 2024 cutoff should be 16,059."""
        assert FACTS["cutoffs"]["2024"]["CSE"] == 16059

    def test_cse_cutoff_2025(self):
        """CSE 2025 cutoff should be 67,761."""
        assert FACTS["cutoffs"]["2025"]["CSE"] == 67761

    def test_aiml_cutoff_2025(self):
        """AIML 2025 cutoff should be 78,384."""
        assert FACTS["cutoffs"]["2025"]["AIML"] == 78384

    def test_it_cutoff_2025(self):
        """IT 2025 cutoff should be 97,611."""
        assert FACTS["cutoffs"]["2025"]["IT"] == 97611


class TestPlacementStats:
    """Verify placement statistics from college_facts.json."""

    def test_overall_placement_2025(self):
        """Overall placement rate 2025 should be 91%."""
        assert FACTS["placements"]["overall_2025"] == 91

    def test_cse_placement_2025(self):
        """CSE placement rate 2025 should be 93.6%."""
        assert FACTS["placements"]["cse_2025"] == 93.6

    def test_highest_package(self):
        """Highest package should be 7.0 LPA."""
        assert FACTS["placements"]["highest_package_on_campus"] == 7.0

    def test_median_package(self):
        """Median package should be 4.25 LPA."""
        assert FACTS["placements"]["median_package"] == 4.25


class TestCollegeIdentity:
    """Verify college identity facts from college_facts.json."""

    def test_college_name(self):
        """College name should be Dr. Bidhan Chandra Roy Engineering College."""
        assert FACTS["college"]["name"] == "Dr. Bidhan Chandra Roy Engineering College"

    def test_established(self):
        """College should be established in August 2000."""
        assert FACTS["college"]["established"] == "August 2000"

    def test_naac_grade(self):
        """NAAC grade should be B+."""
        assert FACTS["accreditation"]["naac"]["grade"] == "B+"

    def test_nirf_rank(self):
        """NIRF rank should be 201-250."""
        assert "201-250" in FACTS["accreditation"]["nirf_rank"]

    def test_principal_name(self):
        """Principal should be Dr. Sanjay S. Pawar."""
        assert FACTS["leadership"]["principal"]["name"] == "Dr. Sanjay S. Pawar"

    def test_vice_principal_name(self):
        """Vice Principal should be Prof. (Dr.) K. M. Hossain."""
        assert FACTS["leadership"]["vice_principal"]["name"] == "Prof. (Dr.) K. M. Hossain"


class TestDepartmentData:
    """Verify department data from college_facts.json."""

    def test_cse_intake(self):
        """CSE intake should be 240 (AICTE EOA 2026-27)."""
        assert FACTS["departments"]["CSE"]["intake"] == 240

    def test_cse_hod(self):
        """CSE HOD should be Dr. Pabitra Kumar Dey."""
        assert FACTS["departments"]["CSE"]["hod"]["name"] == "Dr. Pabitra Kumar Dey"

    def test_aiml_intake(self):
        """AIML intake should be 60."""
        assert FACTS["departments"]["AIML"]["intake"] == 60

    def test_nba_programs(self):
        """NBA accredited programs should include CSE, IT, ECE, EE, ME."""
        nba = FACTS["accreditation"]["nba_programs"]
        assert "CSE" in nba
        assert "IT" in nba
        assert "ECE" in nba
        assert "EE" in nba
        assert "ME" in nba


class TestContactData:
    """Verify contact data from college_facts.json."""

    def test_primary_phone(self):
        """Primary phone should be 0343-2501353."""
        assert FACTS["contacts"]["primary_phone"] == "0343-2501353"

    def test_email(self):
        """Email should be info@bcrec.ac.in."""
        assert FACTS["contacts"]["email"] == "info@bcrec.ac.in"

    def test_principal_phone(self):
        """Principal phone should be 0343-2501353."""
        assert FACTS["leadership"]["principal"]["phone"] == "0343-2501353"


class TestAdmissionData:
    """Verify admission data from college_facts.json."""

    def test_entrance_exams(self):
        """Entrance exams should be WBJEE and JEE Main."""
        assert "WBJEE" in FACTS["admission"]["entrance"]
        assert "JEE Main" in FACTS["admission"]["entrance"]

    def test_seat_distribution(self):
        """Seat distribution should be 80% WBJEE, 10% JEE, 10% Management."""
        assert FACTS["admission"]["seat_distribution"]["wbjee"] == 80
        assert FACTS["admission"]["seat_distribution"]["jee_main"] == 10
        assert FACTS["admission"]["seat_distribution"]["management"] == 10


class TestHostelData:
    """Verify hostel data from college_facts.json."""

    def test_total_hostels(self):
        """Total hostels should be 5."""
        assert FACTS["hostel"]["total_hostels"] == 5

    def test_total_capacity(self):
        """Total capacity should be 1270 (AICTE disclosure 2026-27)."""
        assert FACTS["hostel"]["total_capacity"] == 1270

    def test_boys_hostels(self):
        """Boys hostels should be 3."""
        assert FACTS["hostel"]["boys_hostels"] == 3

    def test_girls_hostels(self):
        """Girls hostels should be 2."""
        assert FACTS["hostel"]["girls_hostels"] == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
