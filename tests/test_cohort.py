from release.common.cohort import COHORT_IE, COHORT_E, RELEASE_SUBJECTS, PUBLISHED_SUBJECTS, AS_PUBLISHED_COND, US3_DROP, PTARGET_SEED

def test_cohort_sizes():
    assert len(COHORT_IE) == 14 and len(COHORT_E) == 13
    assert set(RELEASE_SUBJECTS) == set(COHORT_IE) | set(COHORT_E)
    assert len(RELEASE_SUBJECTS) == 27

def test_condition_map_matches_cohort():
    assert {p for p,c in AS_PUBLISHED_COND.items() if c=='IE'} == set(COHORT_IE)
    assert {p for p,c in AS_PUBLISHED_COND.items() if c=='E'}  == set(COHORT_E)

def test_constants():
    assert US3_DROP == {18,39} and PTARGET_SEED == 12345

def test_published_cohort_excludes_empties():
    assert 61 not in PUBLISHED_SUBJECTS and 63 not in PUBLISHED_SUBJECTS and len(PUBLISHED_SUBJECTS) == 25
